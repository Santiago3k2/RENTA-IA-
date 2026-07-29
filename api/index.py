# -*- coding: utf-8 -*-
r"""RENTA IA en Vercel — la misma bandeja, sobre funciones sin estado.

Diferencias con la versión de escritorio, todas por el entorno:

  · No hay disco persistente. El caso se procesa en memoria y se guarda en
    Supabase (tablas + buckets privados); el .xlsx recibido solo pasa por /tmp,
    que es efímero.
  · Todo pide usuario y contraseña. Aquí viajan declaraciones de personas
    reales, sujetas a la reserva del art. 583 E.T.
  · Cada usuario ve lo suyo: el piloto no ve la cartera del contador.

Variables de entorno necesarias (Vercel → Settings → Environment Variables):

    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY   las mismas del .env local
    RENTA_IA_CLAVE_ADMIN                      contraseña del usuario «admin»
    RENTA_IA_CLAVE_PILOTO                     contraseña de «pruebapiloto2026»
    RENTA_IA_CUPO_PILOTO                      opcional; por defecto 5

Sin las contraseñas configuradas el sitio no sirve nada: preferible fuera de
servicio que abierto.
"""
import base64
import hmac
import os
import sys
import tempfile
import urllib.parse
from http.server import BaseHTTPRequestHandler

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('generador', 'web'):
    ruta = os.path.join(RAIZ, sub)
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

import autogen
import calculos
import clasificador
import db
import multipart
import nube
import render
from render import e

def env(nombre, defecto=''):
    """Variable de entorno limpia.

    Al pegarlas en el panel o cargarlas desde la consola se cuelan espacios,
    saltos de línea y hasta el BOM invisible de Windows (\\ufeff). Con la
    contraseña eso solo impide entrar, pero con el cupo tumbaba el módulo
    entero: más vale limpiar aquí que depender de cómo se escribió el valor.
    """
    return (os.environ.get(nombre) or defecto).strip().lstrip('﻿').strip()


ADMIN = 'admin'
PILOTO = 'pruebapiloto2026'
try:
    CUPO_PILOTO = int(env('RENTA_IA_CUPO_PILOTO') or 5)
except ValueError:
    CUPO_PILOTO = 5
TIPO_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

# El piloto ve y procesa lo suyo; el contador ve toda la cartera.
PERFILES = {
    ADMIN:  {'clave_env': 'RENTA_IA_CLAVE_ADMIN',  'cupo': None, 'solo_suyo': False},
    PILOTO: {'clave_env': 'RENTA_IA_CLAVE_PILOTO', 'cupo': CUPO_PILOTO, 'solo_suyo': True},
}


def credencial(usuario):
    return env(PERFILES[usuario]['clave_env']) if usuario in PERFILES else ''


def hay_configuracion():
    """Faltantes de configuración; si hay alguno, el sitio no atiende."""
    faltan = [p['clave_env'] for p in PERFILES.values() if not env(p['clave_env'])]
    for k in ('SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY'):
        if not env(k):
            faltan.append(k)
    return faltan


def autenticar(cabecera):
    """Devuelve el usuario de un encabezado Basic válido, o None."""
    if not cabecera or not cabecera.lower().startswith('basic '):
        return None
    try:
        crudo = base64.b64decode(cabecera.split(' ', 1)[1]).decode('utf-8')
    except Exception:
        return None
    usuario, _, clave = crudo.partition(':')
    esperada = credencial(usuario)
    # compare_digest evita filtrar la contraseña por el tiempo de respuesta.
    if esperada and hmac.compare_digest(clave, esperada):
        return usuario
    return None


class handler(BaseHTTPRequestHandler):
    server_version = 'RentaIA/1.0'

    # ── salida ──────────────────────────────────────────────────────
    def _html(self, contenido, code=200, cabeceras=None):
        datos = contenido.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(datos)))
        self.send_header('Cache-Control', 'no-store')          # datos reservados
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        for k, v in (cabeceras or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(datos)

    def _pedir_clave(self, mensaje=''):
        cuerpo = ('<div class="vacio">Esta bandeja contiene declaraciones de '
                  'personas reales. Ingrese con el usuario y la contraseña que le '
                  'entregó el contador.' + (f'<p>{e(mensaje)}</p>' if mensaje else '')
                  + '</div>')
        self._html(render.pagina('Acceso restringido', cuerpo, pie=render.PIE_NUBE),
                   401, {'WWW-Authenticate': 'Basic realm="RENTA IA", charset="UTF-8"'})

    def _error(self, mensaje, code=500):
        self._html(render.pagina('Error', f'<div class="err">{e(mensaje)}</div>'
                                          '<p><a href="/">&larr; Volver</a></p>',
                                 pie=render.PIE_NUBE), code)

    # ── contexto de la sesión ───────────────────────────────────────
    def _sesion(self):
        faltan = hay_configuracion()
        if faltan:
            self._error('El sitio no está configurado todavía. Faltan estas '
                        'variables de entorno en Vercel: ' + ', '.join(faltan), 503)
            return None
        usuario = autenticar(self.headers.get('Authorization'))
        if not usuario:
            self._pedir_clave()
            return None
        perfil = PERFILES[usuario]
        return {'usuario': usuario,
                'solo_de': usuario if perfil['solo_suyo'] else None,
                'cupo': perfil['cupo']}

    def _bandeja(self, ses, error='', s=None):
        s = s or db.Supabase.desde_env()
        lista = nube.listar(s, solo_de=ses['solo_de'])
        cupo = None
        if ses['cupo'] is not None:
            cupo = (nube.cuantas_lleva(ses['usuario'], s), ses['cupo'])
        sub = ('BANDEJA DEL CONTADOR &nbsp;&middot;&nbsp; CADA CASO SE VALIDA CONTRA '
               'LOS TOPES DE LA DIAN' if not ses['solo_de'] else
               'ACCESO DE PRUEBA &nbsp;&middot;&nbsp; USTED VE ÚNICAMENTE LAS '
               'DECLARACIONES QUE HA CARGADO')
        return render.vista_bandeja(lista, error=error, usuario=ses['usuario'],
                                    cupo=cupo, pie=render.PIE_NUBE,
                                    mostrar_estado=True, sub=sub)

    # ── GET ─────────────────────────────────────────────────────────
    def do_GET(self):
        ruta = urllib.parse.urlparse(self.path).path.rstrip('/') or '/'
        if ruta == '/salir':
            return self._pedir_clave('Sesión cerrada.')
        ses = self._sesion()
        if not ses:
            return
        try:
            s = db.Supabase.desde_env()
            if ruta == '/':
                return self._html(self._bandeja(ses, s=s))

            if ruta.startswith('/caso/'):
                caso = nube.buscar(ruta.split('/')[2], s, solo_de=ses['solo_de'])
                if not caso:
                    return self._error('Ese caso no existe o no es suyo.', 404)
                if 'error' in caso:
                    return self._error(caso['error'])
                return self._html(render.vista_caso(caso, clasificador.tolerancia,
                                                    usuario=ses['usuario'],
                                                    pie=render.PIE_NUBE,
                                                    mostrar_estado=True))

            if ruta.startswith('/libro/'):
                caso = nube.buscar(ruta.split('/')[2], s, solo_de=ses['solo_de'])
                if not caso or not caso.get('libro_path'):
                    return self._error('Ese libro no existe o no es suyo.', 404)
                # URL firmada de vigencia corta: el bucket nunca se hace público.
                url = s.url_firmada(db.BUCKET_LIBROS, caso['libro_path'], 120)
                self.send_response(302)
                self.send_header('Location', url)
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                return

            self._html(render.pagina('No encontrado',
                                     '<div class="vacio">Esa página no existe. '
                                     '<a href="/">Volver a la bandeja</a></div>',
                                     usuario=ses['usuario'], pie=render.PIE_NUBE), 404)
        except db.ErrorSupabase as ex:
            self._error(str(ex), 502)
        except Exception as ex:
            self._error(f'Error inesperado: {ex}')

    # ── POST ────────────────────────────────────────────────────────
    def do_POST(self):
        ruta = urllib.parse.urlparse(self.path).path.rstrip('/') or '/'
        ses = self._sesion()
        if not ses:
            return
        if ruta != '/subir':
            return self._error('Esa acción no existe.', 404)
        try:
            s = db.Supabase.desde_env()
            if ses['cupo'] is not None:
                usadas = nube.cuantas_lleva(ses['usuario'], s)
                if usadas >= ses['cupo']:
                    return self._html(self._bandeja(
                        ses, f'Su cupo de prueba está completo: {usadas} de '
                             f'{ses["cupo"]} declaraciones. Puede seguir consultando '
                             f'las que ya cargó.', s), 403)

            largo = int(self.headers.get('Content-Length') or 0)
            if largo <= 0:
                raise ValueError('El envío llegó vacío.')
            if largo > 4 * 1024 * 1024:
                raise ValueError('El archivo supera los 4 MB que admite el servidor. '
                                 'Procéselo desde el equipo del contador.')
            nombre, datos = multipart.extraer_archivo(self.rfile.read(largo),
                                                      self.headers.get('Content-Type'))
            if not nombre.lower().endswith('.xlsx'):
                raise ValueError(
                    f'«{nombre}» no es un .xlsx. Si su reporte está en el formato '
                    '.xls antiguo, ábralo en Excel y guárdelo como «Libro de Excel (.xlsx)».')

            # /tmp es lo único escribible aquí, y se borra con la función.
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                tmp.write(datos)
                temporal = tmp.name
            try:
                res = autogen.procesar_en_memoria(temporal, nombre_original=nombre)
            finally:
                try:
                    os.unlink(temporal)
                except OSError:
                    pass

            calc = calculos.calcular_dict(res['cliente'], res['textos'])
            decl = s.guardar_caso(calc, creada_por=ses['usuario'],
                                  libro_bytes=res['libro_bytes'],
                                  nombre_libro=res['nombre_libro'],
                                  exogena_bytes=datos, nombre_exogena=nombre,
                                  solo_si_dueno=ses['solo_de'])
            self.send_response(303)
            self.send_header('Location', '/caso/' + decl['id'])
            self.end_headers()
        except db.ErrorPermiso as ex:
            self._html(self._bandeja(ses, str(ex)), 403)
        except db.ErrorSupabase as ex:
            self._html(self._bandeja(ses, str(ex)), 502)
        except Exception as ex:
            try:
                self._html(self._bandeja(ses, f'No se pudo procesar el archivo: {ex}'), 400)
            except Exception:
                self._error(f'No se pudo procesar el archivo: {ex}', 400)

    def log_message(self, fmt, *args):
        pass
