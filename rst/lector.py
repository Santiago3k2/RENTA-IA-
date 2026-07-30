# -*- coding: utf-8 -*-
"""Lee el consolidado de facturación electrónica de la DIAN y devuelve datos
limpios para la liquidación del SIMPLE.

Dos cuidados que no son opcionales:

* El archivo se abre SIEMPRE con ``read_only=True`` y se corta por la primera
  fila vacía, nunca por ``max_row``. El consolidado declara 1.048.576 filas
  (el máximo de Excel) por formato fantasma, pero solo trae ~300 con datos:
  leído así, un archivo de 63 MB se abre en centésimas de segundo.
* Las columnas se localizan por NOMBRE de encabezado, no por posición. En
  ``F.VENTA`` conviven ``Rete IVA`` (viene en cero) y ``RETEIVA`` (la buena):
  distinguirlas mal deja la declaración sin retenciones.
"""
import datetime
import re

import openpyxl

# Tipos de documento del reporte de emitidos que NO son ingreso.
# «Documento soporte con no obligados a facturar» (prefijo DSE) son COMPRAS a
# personas naturales; contarlos como ventas infla la base del anticipo.
NO_SON_INGRESO = ('documento soporte', 'application response', 'nomina', 'nómina')

NOTA_CREDITO = 'nota crédito'
NOTA_DEBITO = 'nota débito'


class ErrorLectura(Exception):
    """El archivo no es el consolidado esperado."""


# ---------------------------------------------------------------- utilidades

def _norm(txt):
    """Encabezado normalizado para comparar: sin tildes, sin espacios dobles."""
    if txt is None:
        return ''
    t = str(txt).strip().lower()
    for a, b in (('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u'), ('ñ', 'n')):
        t = t.replace(a, b)
    return re.sub(r'\s+', ' ', t)


def _num(v):
    """Número tolerante: acepta 1.234,56 (colombiano), $1,234 y flotantes.

    El consolidado trae residuos de coma flotante como -5.82e-11 en columnas
    que deberían ser cero; se limpian aquí para que no contaminen los totales.
    """
    if v is None or v == '':
        return 0.0
    if isinstance(v, (int, float)):
        x = float(v)
        return 0.0 if abs(x) < 1e-6 else x
    t = str(v).strip().replace('$', '').replace(' ', '')
    if t in ('', '-', '.', ','):
        return 0.0
    if ',' in t and '.' in t:
        # el separador decimal es el último que aparezca
        t = t.replace('.', '') if t.rfind(',') > t.rfind('.') else t.replace(',', '')
        t = t.replace(',', '.')
    elif ',' in t:
        ent, _, dec = t.partition(',')
        t = ent.replace('.', '') + ('.' + dec if len(dec) in (1, 2) else dec)
    else:
        # solo puntos: separador de miles si no deja 1 o 2 decimales
        ent, _, dec = t.rpartition('.')
        if ent and len(dec) not in (1, 2):
            t = ent.replace('.', '') + dec
    try:
        x = float(t)
    except ValueError:
        return 0.0
    return 0.0 if abs(x) < 1e-6 else x


def _fecha(v):
    """dd-mm-aaaa, dd/mm/aaaa o datetime → date. None si no se entiende."""
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    if v is None:
        return None
    t = str(v).strip()[:10]
    for fmt in ('%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(t, fmt).date()
        except ValueError:
            pass
    return None


def _indices(encabezado):
    """{nombre normalizado: índice}. Conserva la primera aparición."""
    idx = {}
    for i, c in enumerate(encabezado):
        n = _norm(c)
        if n and n not in idx:
            idx[n] = i
    return idx


def _filas(ws, minimo=2):
    """Filas con datos, cortando en la primera vacía. Nunca usa max_row."""
    out = []
    for fila in ws.iter_rows(min_row=minimo, values_only=True):
        if all(c is None or str(c).strip() == '' for c in fila):
            break
        out.append(fila)
    return out


def _hoja(wb, nombre):
    for n in wb.sheetnames:
        if _norm(n) == _norm(nombre):
            return wb[n]
    return None


def _hoja_prefijo(wb, prefijo):
    """Las hojas Rp_Doc_<fecha> llevan la fecha de descarga en el nombre."""
    p = _norm(prefijo)
    for n in wb.sheetnames:
        if _norm(n).startswith(p):
            return wb[n]
    return None


# ------------------------------------------------------------------ lectores

def _leer_ventas(ws, avisos):
    enc = next(ws.iter_rows(max_row=1, values_only=True))
    idx = _indices(enc)
    faltan = [c for c in ('ing gravados', 'ing.no gravado', 'iva', 'total') if c not in idx]
    if faltan:
        raise ErrorLectura('La hoja F.VENTA no trae las columnas %s' % ', '.join(faltan))
    # «RETEIVA» es la buena; «Rete IVA» (con espacio) viene en cero.
    i_rete = None
    for i, c in enumerate(enc):
        if str(c or '').strip().upper().replace(' ', '') == 'RETEIVA' and str(c).strip() != 'Rete IVA':
            i_rete = i
    if i_rete is None:
        i_rete = idx.get('reteiva')
    if i_rete is None:
        avisos.append('F.VENTA no trae columna RETEIVA: las retenciones quedan en cero.')

    ventas, descartadas, cola = [], 0, []
    for f in _filas(ws):
        tipo = str(f[idx.get('tipo de documento', 0)] or '')
        tn = _norm(tipo)
        if not tn:
            cola.append(f)          # filas de totales al pie del reporte
            continue
        if any(tn.startswith(x) for x in NO_SON_INGRESO):
            descartadas += 1
            continue
        signo = -1 if NOTA_CREDITO in tn else 1
        ventas.append({
            'tipo': tipo,
            'fecha': _fecha(f[idx['fecha emision']] if 'fecha emision' in idx else None),
            'prefijo': str(f[idx.get('prefijo', 3)] or '').strip(),
            'folio': str(f[idx.get('folio', 2)] or '').strip(),
            'nit': str(f[idx.get('nit receptor', 11)] or '').strip(),
            'tercero': str(f[idx.get('nombre receptor', 12)] or '').strip(),
            'gravado': signo * _num(f[idx['ing gravados']]),
            'no_gravado': signo * _num(f[idx['ing.no gravado']]),
            'iva': signo * _num(f[idx['iva']]),
            'reteiva': signo * _num(f[i_rete]) if i_rete is not None else 0.0,
            'total': signo * _num(f[idx['total']]),
            'estado': str(f[idx.get('estado', -2)] or '').strip(),
        })
    if descartadas:
        avisos.append('F.VENTA: se excluyeron %d documentos que no son ingreso '
                      '(documentos soporte con no obligados, acuses o nómina).' % descartadas)
    totales = _totales_al_pie(cola, {
        'no_gravado': idx['ing.no gravado'], 'gravado': idx['ing gravados'],
        'iva': idx['iva'], 'reteiva': i_rete, 'total': idx['total'],
    })
    return ventas, totales


def _totales_al_pie(cola, columnas):
    """Las filas sin tipo de documento al pie del reporte traen los totales ya
    calculados por quien armó el consolidado. Son la señal de autoverificación
    del módulo: si nuestra suma no los reproduce, algo se leyó de más o de
    menos. La primera fila numérica es la de totales por columna; un número
    suelto en una fila posterior es el gran total de la base.
    """
    tot = {}
    suelto = None
    for f in cola:
        valores = {k: _num(f[i]) for k, i in columnas.items()
                   if i is not None and i < len(f) and isinstance(f[i], (int, float))}
        if not valores:
            continue
        if not tot:
            tot = valores
        elif len(valores) == 1 and suelto is None:
            suelto = list(valores.values())[0]
    if suelto is not None:
        tot['base'] = suelto
    return tot


def _leer_compras(ws, avisos):
    enc = list(next(ws.iter_rows(max_row=1, values_only=True)))
    idx = _indices(enc)
    if 'iva' not in idx or 'total' not in idx:
        raise ErrorLectura('La hoja F.COMPRA no trae las columnas IVA y Total.')
    # La base gravable viene en la columna sin encabezado que precede a «Total».
    i_total = idx['total']
    i_base = i_total - 1 if i_total > 0 and _norm(enc[i_total - 1]) == '' else None
    if i_base is None:
        avisos.append('F.COMPRA no trae la columna de base gravable: se deduce '
                      'dividiendo el IVA entre la tarifa general.')

    compras, cola = [], []
    for f in _filas(ws):
        tn = _norm(str(f[idx.get('tipo de documento', 0)] or ''))
        if not tn:
            cola.append(f)
            continue
        if tn.startswith('application response'):
            continue
        signo = -1 if NOTA_CREDITO in tn else 1
        iva = signo * _num(f[idx['iva']])
        base = signo * _num(f[i_base]) if i_base is not None else 0.0
        compras.append({
            'fecha': _fecha(f[idx.get('fecha emision')] if 'fecha emision' in idx else None),
            'nit': str(f[idx.get('nit emisor', 9)] or '').strip(),
            'proveedor': str(f[idx.get('nombre emisor', 10)] or '').strip(),
            'prefijo': str(f[idx.get('prefijo', 3)] or '').strip(),
            'folio': str(f[idx.get('folio', 2)] or '').strip(),
            'base': base,
            'iva': iva,
            'total': signo * _num(f[idx['total']]),
        })
    cols = {'iva': idx['iva'], 'total': i_total}
    if i_base is not None:
        cols['base'] = i_base
    return compras, _totales_al_pie(cola, cols)


def _leer_reteiva(ws, avisos):
    """Certificados de los agentes retenedores. Maquetación libre: la tabla
    empieza donde aparece el encabezado con «Nit» y «Base»."""
    filas = list(ws.iter_rows(values_only=True))
    inicio = None
    for i, f in enumerate(filas):
        nn = [_norm(c) for c in f]
        if 'nit' in nn and 'base' in nn:
            inicio = i
            idx = _indices(f)
            break
    if inicio is None:
        avisos.append('La hoja RETEIVA no tiene un encabezado reconocible; '
                      'no se pudo conciliar contra los certificados.')
        return []

    agentes = []
    for f in filas[inicio + 1:]:
        if all(c is None or str(c).strip() == '' for c in f):
            break
        etiqueta = _norm(f[idx.get('no.', 0)])
        if etiqueta.startswith('total') or etiqueta == 'ok':
            break
        if not etiqueta:
            continue
        agentes.append({
            'nit': str(f[idx['nit']] or '').strip(),
            'tercero': str(f[idx.get('tercero', 2)] or '').strip(),
            'base': _num(f[idx['base']]),
            'contabilidad': _num(f[idx.get('contabilidad')]) if 'contabilidad' in idx else 0.0,
            'certificado': _num(f[idx.get('certificado')]) if 'certificado' in idx else 0.0,
            'diferencia': _num(f[idx.get('diferencias')]) if 'diferencias' in idx else 0.0,
        })
    return agentes


def _leer_seg_social(ws, avisos):
    """Reporte de PILA con maquetación libre: bloques de encabezado + una fila
    de planilla + una de total, repetidos por administradora."""
    filas = list(ws.iter_rows(values_only=True))
    planillas = []
    idx = None
    for f in filas:
        nn = [_norm(c) for c in f]
        if 'periodo' in nn and 'nombre administradora' in nn:
            idx = _indices(f)
            continue
        if idx is None:
            continue
        periodo = f[idx['periodo']] if idx['periodo'] < len(f) else None
        if periodo is None or _norm(periodo).startswith('total'):
            continue
        admin = f[idx['nombre administradora']] if idx['nombre administradora'] < len(f) else None
        if not admin:
            continue
        planillas.append({
            'periodo': str(periodo).strip(),
            'administradora': str(admin).strip(),
            'fecha_pago': _fecha(f[idx['fecha pago']]) if 'fecha pago' in idx else None,
            'planilla': str(f[idx['planilla numero']] or '').strip() if 'planilla numero' in idx else '',
            'trabajadores': int(_num(f[idx['numero trabajadores']])) if 'numero trabajadores' in idx else 0,
            'dias_mora': int(_num(f[idx['dias en mora']])) if 'dias en mora' in idx else 0,
            'aporte': _num(f[idx['valor sin mora']]) if 'valor sin mora' in idx else 0.0,
            'intereses': _num(f[idx['valor intereses']]) if 'valor intereses' in idx else 0.0,
            'total': _num(f[idx['total pagado']]) if 'total pagado' in idx else 0.0,
        })
    if not planillas:
        avisos.append('No se encontraron planillas de seguridad social: el descuento '
                      'por aportes a pensión queda en cero y hay que capturarlo a mano.')
    return planillas


# ------------------------------------------------------------------- fachada

def leer(ruta):
    """Consolidado → dict con ventas, compras, reteiva, seg_social y avisos."""
    avisos = []
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    try:
        hv = _hoja(wb, 'F.VENTA')
        hc = _hoja(wb, 'F.COMPRA')
        if hv is None:
            raise ErrorLectura(
                'El archivo no tiene la hoja F.VENTA. Hojas encontradas: %s'
                % ', '.join(wb.sheetnames))
        ventas, tot_ventas = _leer_ventas(hv, avisos)
        if hc is not None:
            compras, tot_compras = _leer_compras(hc, avisos)
        else:
            compras, tot_compras = [], {}
            avisos.append('El archivo no trae hoja F.COMPRA: el IVA descontable queda en cero.')
        hr = _hoja(wb, 'RETEIVA')
        reteiva = _leer_reteiva(hr, avisos) if hr is not None else []
        if hr is None:
            avisos.append('El archivo no trae hoja RETEIVA: no hay conciliación de certificados.')
        hs = _hoja(wb, 'S.SOCIAL')
        seg = _leer_seg_social(hs, avisos) if hs is not None else []
        if hs is None:
            avisos.append('El archivo no trae hoja S.SOCIAL: sin descuento por aportes a pensión.')

        emitidos = _hoja_prefijo(wb, 'Rp_Doc_')
        n_emitidos = len(_filas(emitidos)) if emitidos is not None else 0
        recibidos = _hoja(wb, 'Rp_Docpras')
        n_recibidos = len(_filas(recibidos)) if recibidos is not None else 0
    finally:
        wb.close()

    return {
        'ventas': ventas,
        'compras': compras,
        'reteiva': reteiva,
        'seg_social': seg,
        'totales_declarados': {'ventas': tot_ventas, 'compras': tot_compras},
        'conteo_reportes': {'emitidos': n_emitidos, 'recibidos': n_recibidos},
        'avisos': avisos,
    }
