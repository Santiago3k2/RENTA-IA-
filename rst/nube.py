# -*- coding: utf-8 -*-
r"""Persistencia del módulo RST en Supabase.

Tablas propias (`recibos_rst`, `alertas_rst`) porque la clave del caso es
(contribuyente, año, **bimestre**), no (contribuyente, año). `contribuyentes`
sí se comparte con el módulo de renta: un mismo cliente puede estar en los dos
regímenes y debe verse como una sola ficha en la cartera.

Reutiliza la clase `db.Supabase` del motor de renta —misma clave de servicio,
mismos buckets, mismo manejo de errores— para no tener dos formas de hablar
con la base.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(RAIZ, 'generador')
if GEN not in sys.path:
    sys.path.insert(0, GEN)

import db as db_renta                     # noqa: E402  (necesita el sys.path de arriba)

from . import parametros as P             # noqa: E402

TABLA = 'recibos_rst'
TABLA_ALERTAS = 'alertas_rst'
BUCKET_LIBROS = db_renta.BUCKET_LIBROS
BUCKET_CONSOLIDADOS = 'consolidados'

ErrorSupabase = db_renta.ErrorSupabase
ErrorPermiso = db_renta.ErrorPermiso


def _int(x):
    return int(round(float(x or 0)))


def _cifras(liq):
    """Las columnas planas: sirven para pintar la bandeja sin abrir el jsonb."""
    ica = liq['filas_ica'][0] if liq['filas_ica'] else {}
    return {
        'uvt': liq['uvt'],
        'grupo': liq['grupo'],
        'tarifa': round(liq['tarifa'], 4),
        'municipio': ica.get('nombre'),
        'cod_dane': ica.get('codigo'),
        'tarifa_ica': ica.get('tarifa'),
        'n_facturas': len(liq['facturas']),
        'n_compras': len(liq['compras_gravadas']) + len(liq['compras_excluidas']),
        'ingresos_gravados': _int(liq['ingresos_gravados']),
        'ingresos_no_gravados': _int(liq['ingresos_no_gravados']),
        'base': _int(liq['base']),
        'base_uvt': round(liq['base_uvt'], 2),
        'anticipo_consolidado': _int(liq['anticipo_consolidado']),
        'ica': _int(liq['ica']),
        'descuento_pension': _int(liq['descuento_pension']),
        'anticipo_neto': _int(liq['anticipo_neto']),
        'iva_generado': round(liq['iva_generado'], 2),
        'iva_descontable': round(liq['iva_descontable'], 2),
        'reteiva': round(liq['reteiva'], 2),
        'iva_pagar': round(liq['iva_pagar'], 2),
        'total_pagar': _int(liq['total_mil']),
    }


def _liquidacion_serializable(liq):
    """El detalle completo, con las fechas ya en texto para que entre en jsonb."""
    def limpio(v):
        if isinstance(v, dict):
            return {k: limpio(x) for k, x in v.items()}
        if isinstance(v, list):
            return [limpio(x) for x in v]
        if hasattr(v, 'isoformat'):
            return v.isoformat()
        return v
    fuera = {'facturas', 'compras_gravadas', 'compras_excluidas', 'agentes_reteiva',
             'planillas', 'por_mes', 'filas_ica', 'validaciones', 'alertas',
             'facturas_fuera_periodo', 'totales_declarados'}
    datos = {k: limpio(v) for k, v in liq.items() if k not in fuera}
    for k in ('por_mes', 'filas_ica', 'planillas', 'agentes_reteiva',
              'totales_declarados'):
        datos[k] = limpio(liq.get(k))
    datos['n_facturas'] = len(liq['facturas'])
    datos['detalle_facturas'] = limpio(liq['facturas'])
    datos['detalle_compras'] = limpio(liq['compras_gravadas'] + liq['compras_excluidas'])
    return datos


def guardar_recibo(s, ficha, liq, libro_bytes=None, nombre_libro=None,
                   consolidado_bytes=None, nombre_consolidado=None,
                   creada_por=None, estado=None, solo_si_dueno=None):
    """Persiste un recibo ya liquidado. Devuelve la fila de `recibos_rst`.

    Reemplaza por completo las alertas: son un derivado del motor, no notas del
    contador. La revisión humana (estado, liberación) se conserva salvo que se
    pase `estado` explícitamente.
    """
    identificacion = str(ficha['nit']).replace('.', '').replace('-', '').strip()
    nombre = ficha['nombre']
    contribuyente = s.insertar('contribuyentes', {
        'identificacion': identificacion,
        'tipo_documento': ficha.get('tipo_documento', 'NIT'),
        'nombre': nombre,
        'nombre_titulo': ficha.get('nombre_titulo', nombre.title()),
    }, conflicto='identificacion')[0]

    fila = {
        'contribuyente_id': contribuyente['id'],
        'ano_gravable': str(liq['ano']),
        'bimestre': liq['bimestre'],
        'semaforo': liq['semaforo'],
        'ficha': ficha,
        'liquidacion': _liquidacion_serializable(liq),
        'validaciones': liq['validaciones'],
    }
    fila.update(_cifras(liq))
    if estado:
        fila['estado'] = estado

    previa = s.seleccionar(TABLA, select='id,creada_por',
                           contribuyente_id='eq.' + fila['contribuyente_id'],
                           ano_gravable='eq.' + fila['ano_gravable'],
                           bimestre='eq.%d' % fila['bimestre'])
    if creada_por and not previa:
        fila['creada_por'] = creada_por
    if solo_si_dueno and previa and previa[0].get('creada_por') != solo_si_dueno:
        raise ErrorPermiso(
            'Ese recibo (%s · bimestre %d de %s) ya existe y lo cargó otra '
            'persona. No se puede sobrescribir desde este usuario: pida al '
            'contador que lo revise.' % (nombre, liq['bimestre'], liq['ano']))

    carpeta = '%s/RST-%s-B%d' % (fila['contribuyente_id'], fila['ano_gravable'],
                                 fila['bimestre'])
    if libro_bytes is not None:
        fila['libro_path'] = s.subir_bytes(
            BUCKET_LIBROS, '%s/%s' % (carpeta, nombre_libro or 'libro.xlsx'), libro_bytes)
    if consolidado_bytes is not None:
        fila['consolidado_path'] = s.subir_bytes(
            BUCKET_CONSOLIDADOS,
            '%s/%s' % (carpeta, nombre_consolidado or 'consolidado.xlsx'),
            consolidado_bytes)

    recibo = s.insertar(TABLA, fila,
                        conflicto='contribuyente_id,ano_gravable,bimestre')[0]

    s.borrar(TABLA_ALERTAS, recibo_id='eq.' + recibo['id'])
    alertas = [{'recibo_id': recibo['id'], 'orden': i, 'prioridad': a['prioridad'],
                'tema': a['tema'], 'texto': a['texto']}
               for i, a in enumerate(liq['alertas'], 1)]
    if alertas:
        s.insertar(TABLA_ALERTAS, alertas)
    return recibo


def _adaptar(fila, contribuyentes):
    """Fila de la base → el diccionario que espera la vista."""
    c = contribuyentes.get(fila['contribuyente_id'], {})
    return {
        'ref': fila['id'],
        'persona': c.get('nombre_titulo') or c.get('nombre') or '—',
        'identificacion': c.get('identificacion', '—'),
        'ano': fila['ano_gravable'],
        'bimestre': fila['bimestre'],
        'periodo': 'Bim %d · %s' % (fila['bimestre'],
                                    P.nombre_bimestre(fila['bimestre'])),
        'semaforo': fila.get('semaforo'),
        'estado': fila.get('estado'),
        'creada_por': fila.get('creada_por'),
        'creado_en': fila.get('creado_en'),
        'fila': fila,
    }


def listar(s, solo_de=None, limite=400):
    """Los recibos de la cartera, del más reciente al más antiguo."""
    filtros = {'select': '*', 'order': 'ano_gravable.desc,bimestre.desc,creado_en.desc',
               'limit': str(limite)}
    if solo_de:
        filtros['creada_por'] = 'eq.' + solo_de
    filas = s.seleccionar(TABLA, **filtros)
    if not filas:
        return []
    ids = sorted({f['contribuyente_id'] for f in filas})
    personas = s.seleccionar('contribuyentes', select='*',
                             id='in.(%s)' % ','.join(ids))
    mapa = {p['id']: p for p in personas}
    return [_adaptar(f, mapa) for f in filas]


def buscar(s, ref, solo_de=None):
    """Un recibo por su id, con sus alertas. None si no existe o no es suyo."""
    filtros = {'select': '*', 'id': 'eq.' + str(ref)}
    if solo_de:
        filtros['creada_por'] = 'eq.' + solo_de
    filas = s.seleccionar(TABLA, **filtros)
    if not filas:
        return None
    fila = filas[0]
    personas = s.seleccionar('contribuyentes', select='*',
                             id='eq.' + fila['contribuyente_id'])
    caso = _adaptar(fila, {fila['contribuyente_id']: personas[0] if personas else {}})
    caso['alertas'] = s.seleccionar(TABLA_ALERTAS, select='*',
                                    recibo_id='eq.' + fila['id'], order='orden.asc')
    return caso


def cuantos_lleva(s, usuario):
    return s.contar(TABLA, creada_por='eq.' + usuario)


def cambiar_estado(s, recibo_id, estado, por=None):
    import datetime
    cambios = {'estado': estado}
    if estado == 'liberada':
        cambios['liberada_en'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cambios['liberada_por'] = por
    return s.actualizar(TABLA, cambios, id='eq.' + str(recibo_id))


def eliminar(s, recibo_id):
    """Borra el recibo y sus archivos. Solo desde borrador y por su dueño."""
    filas = s.seleccionar(TABLA, select='*', id='eq.' + str(recibo_id))
    if not filas:
        return False
    fila = filas[0]
    for bucket, ruta in ((BUCKET_LIBROS, fila.get('libro_path')),
                         (BUCKET_CONSOLIDADOS, fila.get('consolidado_path'))):
        if ruta:
            try:
                s.borrar_objeto(bucket, ruta)
            except ErrorSupabase:
                pass          # el archivo ya no está; la fila sí debe irse
    s.borrar(TABLA, id='eq.' + str(recibo_id))
    return True
