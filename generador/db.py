# -*- coding: utf-8 -*-
r"""Acceso a Supabase para RENTA IA — solo librería estándar (urllib).

Toda la escritura pasa por la clave de servicio: las tablas tienen RLS activa y
sin políticas, así que nadie más entra. Nunca se expone esta clave al navegador.

    import db
    s = db.Supabase.desde_env()
    s.guardar_caso(calc, libro=ruta_xlsx, exogena=ruta_xlsx_fuente)

Los archivos van a dos buckets privados (`libros`, `exogenas`) y se sirven con
URL firmada de vigencia corta, jamás con enlace público: son datos tributarios
de personas reales.
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import config

BUCKET_LIBROS = 'libros'
BUCKET_EXOGENAS = 'exogenas'
TIPO_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class ErrorSupabase(Exception):
    """Falla de comunicación con Supabase, ya traducida al español."""


class ErrorPermiso(ErrorSupabase):
    """El usuario no tiene derecho a hacer eso. No es una falla del sistema."""


def _traducir(codigo, cuerpo, url):
    if codigo == 401:
        return ('Supabase rechazó la clave (401). Si la acaba de crear o rotar, '
                'espere unos minutos y reintente: la clave tarda en propagarse y '
                'mientras tanto responde 401. Si persiste, la '
                'SUPABASE_SERVICE_ROLE_KEY del .env está revocada, incompleta o '
                'es de otro proyecto; genere una nueva en Project Settings → '
                'API Keys → «Create new secret key».')
    if codigo == 403:
        return ('Supabase respondió 403: la clave no tiene permiso. Debe ser la '
                'clave SECRETA (service role), no la publicable.')
    if codigo == 404:
        return (f'Supabase respondió 404 en {url}. Verifique que el esquema esté '
                'aplicado (db/esquema.sql) y que la URL del proyecto sea la correcta.')
    return f'Supabase respondió {codigo}: {cuerpo[:300]}'


class Supabase:
    def __init__(self, url, clave):
        self.url = (url or '').rstrip('/')
        self.clave = clave or ''

    # ── construcción ────────────────────────────────────────────────
    @classmethod
    def desde_env(cls, exigir=True):
        a = config.ajustes()
        fallas = config.revisar(a)
        if exigir and fallas:
            raise ErrorSupabase('Configuración incompleta:\n  · ' + '\n  · '.join(fallas))
        return cls(a.get('SUPABASE_URL'), a.get('SUPABASE_SERVICE_ROLE_KEY'))

    @property
    def configurado(self):
        return bool(self.url and self.clave)

    # ── transporte ──────────────────────────────────────────────────
    def _pedir(self, metodo, ruta, cuerpo=None, cabeceras=None, binario=None,
               tipo='application/json'):
        url = self.url + ruta
        datos = binario if binario is not None else (
            json.dumps(cuerpo, ensure_ascii=False).encode('utf-8') if cuerpo is not None else None)
        cab = {'apikey': self.clave, 'Authorization': 'Bearer ' + self.clave}
        if datos is not None:
            cab['Content-Type'] = tipo
        cab.update(cabeceras or {})
        req = urllib.request.Request(url, data=datos, headers=cab, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                crudo = r.read()
        except urllib.error.HTTPError as ex:
            cuerpo_err = ex.read().decode('utf-8', 'replace')
            raise ErrorSupabase(_traducir(ex.code, cuerpo_err, url)) from None
        except urllib.error.URLError as ex:
            raise ErrorSupabase(f'No se pudo conectar con Supabase: {ex.reason}') from None
        if not crudo:
            return None
        try:
            return json.loads(crudo.decode('utf-8'))
        except ValueError:
            return crudo

    # ── tablas ──────────────────────────────────────────────────────
    def seleccionar(self, tabla, **filtros):
        params = {'select': filtros.pop('select', '*')}
        orden = filtros.pop('order', None)
        if orden:
            params['order'] = orden
        params.update({k: v for k, v in filtros.items()})
        return self._pedir('GET', f'/rest/v1/{tabla}?' + urllib.parse.urlencode(params)) or []

    def insertar(self, tabla, filas, conflicto=None):
        """Inserta o actualiza (upsert) y devuelve las filas resultantes."""
        filas = filas if isinstance(filas, list) else [filas]
        if not filas:
            return []
        ruta = f'/rest/v1/{tabla}'
        prefer = 'return=representation'
        if conflicto:
            ruta += '?on_conflict=' + urllib.parse.quote(conflicto)
            prefer = 'resolution=merge-duplicates,' + prefer
        return self._pedir('POST', ruta, filas, {'Prefer': prefer}) or []

    def actualizar(self, tabla, cambios, **filtros):
        ruta = f'/rest/v1/{tabla}?' + urllib.parse.urlencode(filtros)
        return self._pedir('PATCH', ruta, cambios,
                           {'Prefer': 'return=representation'}) or []

    def borrar(self, tabla, **filtros):
        ruta = f'/rest/v1/{tabla}?' + urllib.parse.urlencode(filtros)
        return self._pedir('DELETE', ruta, cabeceras={'Prefer': 'return=minimal'})

    def ping(self):
        """Comprueba credenciales y esquema. Devuelve texto de diagnóstico."""
        self.seleccionar('declaraciones', select='id', limit='1')
        return 'Conexión correcta: las tablas responden con la clave de servicio.'

    # ── almacenamiento ──────────────────────────────────────────────
    def asegurar_buckets(self):
        """Crea los buckets privados si faltan. Idempotente."""
        creados = []
        existentes = {b.get('name') for b in (self._pedir('GET', '/storage/v1/bucket') or [])}
        for nombre in (BUCKET_LIBROS, BUCKET_EXOGENAS):
            if nombre in existentes:
                continue
            self._pedir('POST', '/storage/v1/bucket',
                        {'id': nombre, 'name': nombre, 'public': False})
            creados.append(nombre)
        return creados

    def subir_bytes(self, bucket, ruta_destino, contenido, tipo=TIPO_XLSX):
        """Sube (o reemplaza) contenido en memoria; devuelve la ruta en el bucket."""
        destino = urllib.parse.quote(ruta_destino)
        self._pedir('POST', f'/storage/v1/object/{bucket}/{destino}',
                    binario=contenido, tipo=tipo, cabeceras={'x-upsert': 'true'})
        return ruta_destino

    def subir(self, bucket, ruta_destino, ruta_local, tipo=TIPO_XLSX):
        """Sube (o reemplaza) un archivo del disco."""
        with open(ruta_local, 'rb') as f:
            return self.subir_bytes(bucket, ruta_destino, f.read(), tipo)

    def url_firmada(self, bucket, ruta_destino, segundos=3600):
        """URL temporal de descarga. Vence sola: nunca se publica el bucket."""
        r = self._pedir('POST',
                        f'/storage/v1/object/sign/{bucket}/{urllib.parse.quote(ruta_destino)}',
                        {'expiresIn': segundos})
        firmada = (r or {}).get('signedURL', '')
        # Supabase devuelve la ruta con los espacios del nombre del libro sin
        # codificar; así como viene, la descarga falla.
        ruta, sep, consulta = firmada.partition('?')
        return self.url + '/storage/v1' + urllib.parse.quote(ruta, safe='/') + sep + consulta

    # ── el caso completo ────────────────────────────────────────────
    def guardar_caso(self, calc, libro=None, exogena=None, estado=None,
                     creada_por=None, libro_bytes=None, exogena_bytes=None,
                     nombre_libro=None, nombre_exogena=None, solo_si_dueno=None):
        """Persiste un caso ya calculado. Devuelve la fila de `declaraciones`.

        Los archivos entran por ruta (modo escritorio) o por bytes (funciones
        sin disco). Reemplaza por completo las alertas del caso: son un derivado
        del clasificador, no notas del contador. La revisión humana (estado,
        liberación) sí se conserva: solo se pisa si se pasa `estado`.

        `creada_por` solo se escribe al crear: quien cargó el caso la primera
        vez sigue siendo su dueño aunque después lo actualice el contador.
        """
        C = calc['cliente']
        contribuyente = self.insertar('contribuyentes', {
            'identificacion': str(C['identificacion']).replace('.', '').strip(),
            'nombre': C['nombre'],
            'nombre_titulo': C['nombre_titulo'],
        }, conflicto='identificacion')[0]

        fila = {
            'contribuyente_id': contribuyente['id'],
            'ano_gravable': str(C['ano_gravable']),
            'semaforo': calc['semaforo'],
            'uvt': C.get('uvt'),
            'fuente': C.get('fuente'),
            'n_registros': C.get('registros'),
            'ingresos': int(calc['ingresos']),
            'impuesto': int(calc['impuesto']),
            'saldo': int(calc['saldo']),
            'patrimonio_bruto': int(calc['pat_bruto']),
            'patrimonio_liquido': int(calc['pat_liquido']),
            'retenciones': int(calc['retenciones']),
            'datos': C,
            'topes_dian': calc['topes_dian'],
            'difs_topes': calc['difs_topes'],
        }
        if estado:
            fila['estado'] = estado

        previa = self.seleccionar(
            'declaraciones', select='id,creada_por',
            contribuyente_id='eq.' + fila['contribuyente_id'],
            ano_gravable='eq.' + fila['ano_gravable'])
        if creada_por and not previa:
            fila['creada_por'] = creada_por
        # Un usuario restringido no puede pisar el caso de otro: el año gravable
        # de un contribuyente es único, así que reprocesarlo sobrescribiría el
        # trabajo del contador.
        if solo_si_dueno and previa and previa[0].get('creada_por') != solo_si_dueno:
            raise ErrorPermiso(
                f'Esa declaración ({C["nombre_titulo"]} · AG {C["ano_gravable"]}) '
                'ya existe y la cargó otra persona. No se puede sobrescribir '
                'desde este usuario: pida al contador que la revise.')

        carpeta = f"{fila['contribuyente_id']}/AG{fila['ano_gravable']}"
        if libro_bytes is not None:
            fila['libro_path'] = self.subir_bytes(
                BUCKET_LIBROS, f'{carpeta}/{nombre_libro or "libro.xlsx"}', libro_bytes)
        elif libro and os.path.isfile(libro):
            fila['libro_path'] = self.subir(
                BUCKET_LIBROS, f'{carpeta}/{os.path.basename(libro)}', libro)
        if exogena_bytes is not None:
            fila['exogena_path'] = self.subir_bytes(
                BUCKET_EXOGENAS, f'{carpeta}/{nombre_exogena or "exogena.xlsx"}', exogena_bytes)
        elif exogena and os.path.isfile(exogena):
            fila['exogena_path'] = self.subir(
                BUCKET_EXOGENAS, f'{carpeta}/{os.path.basename(exogena)}', exogena)

        decl = self.insertar('declaraciones', fila,
                             conflicto='contribuyente_id,ano_gravable')[0]

        self.borrar('alertas', declaracion_id='eq.' + decl['id'])
        alertas = [{'declaracion_id': decl['id'], 'codigo': a[0], 'severidad': a[1],
                    'hallazgo': a[2], 'detalle': a[3], 'accion': a[4]}
                   for a in C.get('alertas', [])]
        if alertas:
            self.insertar('alertas', alertas)
        return decl

    def liberar(self, declaracion_id, por):
        """Marca el caso como liberado. Solo lo hace el contador, nunca el motor."""
        ahora = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return self.actualizar('declaraciones',
                               {'estado': 'liberada', 'liberada_por': por,
                                'liberada_en': ahora},
                               id='eq.' + str(declaracion_id))


if __name__ == '__main__':
    try:
        s = Supabase.desde_env()
        print(s.ping())
        creados = s.asegurar_buckets()
        print('Buckets creados: ' + ', '.join(creados) if creados
              else 'Buckets `libros` y `exogenas` ya existen.')
    except ErrorSupabase as ex:
        print('✗ ' + str(ex))
        sys.exit(1)
