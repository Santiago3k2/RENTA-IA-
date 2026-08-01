# -*- coding: utf-8 -*-
r"""Regresión del apartado RST del sitio publicado.

    python -m rst.pruebas_web

Levanta `api\index.py` —el mismo código que corre en Vercel— en un puerto libre
y lo recorre con cookies, como un navegador. La base es la de verdad.

Comprueba lo que solo se descubre en producción: que sin sesión no se entra al
apartado, que el testigo anti-CSRF se exige, que un cliente no puede mover el
estado de un recibo y que la ficha del formulario se valida antes de tocar el
archivo. Las cuentas «zzrst…» que crea se borran al terminar, también si algo
falla.
"""
import http.cookiejar
import os
import re
import secrets
import socket
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(BASE)
for sub in (RAIZ, os.path.join(RAIZ, 'generador'), os.path.join(RAIZ, 'web'),
            os.path.join(RAIZ, 'api')):
    if sub not in sys.path:
        sys.path.insert(0, sub)

import cuentas                      # noqa: E402
import db                           # noqa: E402
import index as sitio               # noqa: E402

from rst import nube as rst_nube    # noqa: E402

CLAVE = 'ladera verde 73 agosto'
fallos = []
hechas = 0


def revisar(condicion, titulo, extra=''):
    global hechas
    hechas += 1
    if condicion:
        print(f'  ok   {titulo}')
    else:
        print(f'  FALLA {titulo}' + (f' — {extra}' if extra else ''))
        fallos.append(titulo)


class _SinRedirigir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Navegador:
    def __init__(self, base):
        self.base = base
        self.abridor = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
            _SinRedirigir())

    def _pedir(self, metodo, ruta, datos=None):
        cuerpo = urllib.parse.urlencode(datos).encode() if datos is not None else None
        pet = urllib.request.Request(self.base + ruta, data=cuerpo, method=metodo)
        if cuerpo is not None:
            pet.add_header('Content-Type', 'application/x-www-form-urlencoded')
        try:
            with self.abridor.open(pet, timeout=60) as r:
                return r.status, r.read().decode('utf-8', 'replace'), dict(r.headers)
        except urllib.error.HTTPError as ex:
            return ex.code, ex.read().decode('utf-8', 'replace'), dict(ex.headers)

    def get(self, ruta):
        return self._pedir('GET', ruta)

    def post(self, ruta, datos):
        return self._pedir('POST', ruta, datos)

    def subir(self, ruta, campos, nombre_archivo, contenido):
        """Envío multipart, que es como llega el consolidado de verdad."""
        borde = '----rstprueba' + secrets.token_hex(8)
        partes = []
        for k, v in campos.items():
            partes.append(
                f'--{borde}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
                .encode())
        partes.append(
            (f'--{borde}\r\nContent-Disposition: form-data; name="archivo"; '
             f'filename="{nombre_archivo}"\r\n'
             f'Content-Type: application/octet-stream\r\n\r\n').encode())
        partes.append(contenido)
        partes.append(f'\r\n--{borde}--\r\n'.encode())
        cuerpo = b''.join(partes)
        pet = urllib.request.Request(self.base + ruta, data=cuerpo, method='POST')
        pet.add_header('Content-Type', 'multipart/form-data; boundary=' + borde)
        try:
            with self.abridor.open(pet, timeout=120) as r:
                return r.status, r.read().decode('utf-8', 'replace'), dict(r.headers)
        except urllib.error.HTTPError as ex:
            return ex.code, ex.read().decode('utf-8', 'replace'), dict(ex.headers)


def puerto_libre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def testigo(html):
    m = re.search(r'name="_t" value="([^"]+)"', html)
    return m.group(1) if m else ''


def main():
    print('═' * 66)
    print('  RENTA IA · RST — regresión del apartado publicado')
    print('═' * 66)
    faltan = sitio.hay_configuracion()
    if faltan:
        print('\nFalta configurar: ' + ', '.join(faltan))
        return 1

    c = cuentas.Cuentas(db.Supabase.desde_env())
    s = db.Supabase.desde_env()
    puerto = puerto_libre()
    base = f'http://localhost:{puerto}'
    servidor = ThreadingHTTPServer(('127.0.0.1', puerto), sitio.handler)
    servidor.daemon_threads = True
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    print(f'\nSitio levantado en {base}\n')

    ids = []
    try:
        # ── sin sesión ────────────────────────────────────────────────
        anon = Navegador(base)
        code, _, _ = anon.get('/rst')
        revisar(code in (401, 302, 303), 'sin sesión el apartado RST no se abre',
                f'dio {code}')

        # ── el contador ───────────────────────────────────────────────
        ua = 'zzrst' + secrets.token_hex(4)
        ids.append(c.crear(ua, 'Contador De Ensayo', CLAVE, rol='admin',
                           estado='activo', creado_por='pruebas')['id'])
        nav = Navegador(base)
        code, _, _ = nav.post('/entrar', {'usuario': ua, 'clave': CLAVE})
        revisar(code == 303, 'el contador entra', f'dio {code}')

        code, html, _ = nav.get('/')
        revisar(code == 200 and '>RST<' in html,
                'la bandeja de Renta ofrece la pestaña del RST')

        code, html, _ = nav.get('/rst')
        revisar(code == 200 and 'FORMULARIO 2593' in html,
                'el apartado RST carga', f'dio {code}')
        revisar('Procesar un bimestre del SIMPLE' in html,
                'el apartado ofrece el formulario de carga')
        t = testigo(html)
        revisar(bool(t), 'el formulario trae el testigo anti-CSRF')
        # El bimestre lo pone el archivo, no el usuario: dejarlo preseleccionado
        # en 1 hacía que un consolidado de mayo-junio se liquidara como
        # enero-febrero y saliera un libro entero en ceros.
        revisar('Detectar del archivo' in html,
                'el bimestre se puede dejar en «detectar del archivo»')
        revisar('Elija el grupo' in html,
                'el grupo de actividad no viene preseleccionado: define la tarifa')

        # ── un recibo ya cargado ──────────────────────────────────────
        lista = rst_nube.listar(s)
        if lista:
            ref = lista[0]['ref']
            code, html, _ = nav.get('/rst/' + ref)
            revisar(code == 200 and 'Casillas del Formulario 2593' in html,
                    'el detalle de un recibo carga', f'dio {code}')
            revisar('Comprobaciones automáticas' in html,
                    'el detalle muestra las comprobaciones del semáforo')
            code, _, cab = nav.get('/rst/libro/' + ref)
            revisar(code == 302 and 'supabase' in cab.get('Location', ''),
                    'el libro se sirve con URL firmada, no con enlace público',
                    f'dio {code}')
            code, _, _ = nav.post(f'/rst/{ref}/estado',
                                  {'estado': 'en_revision', '_t': 'testigo falso'})
            revisar(code == 400, 'sin el testigo correcto no se mueve el estado',
                    f'dio {code}')
        else:
            print('  (no hay recibos cargados: se omiten las pruebas de detalle)')

        code, html, _ = nav.get('/rst/no-existe')
        revisar(code in (400, 404, 502), 'un recibo inexistente no revienta el sitio',
                f'dio {code}')

        # ── la ficha se valida antes de tocar el archivo ───────────────
        malos = {'_t': t, 'nombre': 'ENSAYO SAS', 'nit': '900000000', 'ano': '2026',
                 'bimestre': '9', 'grupo': '3', 'municipio': 'Bucaramanga',
                 'tarifa_ica': '12,5'}
        code, html, _ = nav.subir('/rst/subir', malos, 'x.xlsx', b'no es un excel')
        revisar('bimestre debe ir de 1 a 6' in html,
                'un bimestre fuera de rango se rechaza con un mensaje claro')

        malos.update({'bimestre': '3', 'tarifa_ica': '900'})
        code, html, _ = nav.subir('/rst/subir', malos, 'x.xlsx', b'no es un excel')
        revisar('tarifa de ICA' in html,
                'una tarifa de ICA absurda se rechaza antes de leer el archivo')

        malos.update({'tarifa_ica': '12,5', 'ano': '2099'})
        code, html, _ = nav.subir('/rst/subir', malos, 'x.xlsx', b'no es un excel')
        revisar('UVT' in html, 'un año sin UVT cargada se rechaza y lo dice')

        # El grupo sí es obligatorio: define la tarifa y puede duplicar el
        # impuesto, así que no hay valor por defecto que valga.
        malos.update({'ano': '2026', 'grupo': ''})
        code, html, _ = nav.subir('/rst/subir', malos, 'x.xlsx', b'no es un excel')
        revisar('grupo de actividad' in html,
                'sin grupo de actividad no se procesa')

        # El bimestre en blanco NO es un error: significa «detectar del
        # archivo». Tiene que pasar la validación de la ficha y morir después,
        # al leer el .xlsx falso.
        malos.update({'grupo': '3', 'bimestre': ''})
        code, html, _ = nav.subir('/rst/subir', malos, 'x.xlsx', b'no es un excel')
        revisar('bimestre debe ir de 1 a 6' not in html,
                'el bimestre en blanco se acepta: se detecta del archivo')

        # ── un cliente no manda ───────────────────────────────────────
        uc = 'zzrst' + secrets.token_hex(4)
        ids.append(c.crear(uc, 'Cliente De Ensayo', CLAVE, rol='cliente',
                           estado='activo', cupo=1, creado_por='pruebas')['id'])
        cli = Navegador(base)
        cli.post('/entrar', {'usuario': uc, 'clave': CLAVE})
        code, html, _ = cli.get('/rst')
        revisar(code == 403, 'el apartado RST está cerrado para quien no es admin',
                f'dio {code}')
        code, html, _ = cli.get('/')
        revisar('/rst' not in html, 'al cliente no se le ofrece la pestaña del RST')
        if lista:
            code, _, _ = cli.get('/rst/' + lista[0]['ref'])
            revisar(code == 403, 'el cliente no puede abrir un recibo ni con la '
                                 'dirección a mano', f'dio {code}')
            # 400 y no 403: el testigo anti-CSRF se comprueba antes que el rol,
            # así que el envío se cae aún antes de mirar permisos. Lo que importa
            # es que no pase.
            code, _, _ = cli.post(f'/rst/{lista[0]["ref"]}/estado',
                                  {'estado': 'liberada', '_t': 'x'})
            revisar(code in (400, 403), 'el cliente no puede liberar un recibo',
                    f'dio {code}')
        code, _, _ = cli.subir('/rst/subir', {'_t': 'x'}, 'x.xlsx', b'x')
        revisar(code == 403, 'el cliente no puede subir un consolidado', f'dio {code}')
    finally:
        servidor.shutdown()
        for i in ids:
            try:
                s.borrar('usuarios', id='eq.' + i)
            except Exception as ex:
                print(f'  (no se pudo borrar la cuenta de ensayo {i}: {ex})')

    print()
    if fallos:
        print(f'FALLARON {len(fallos)} de {hechas} COMPROBACIONES:')
        for f in fallos:
            print('  · ' + f)
        return 1
    print(f'TODAS LAS PRUEBAS PASAN ({hechas} comprobaciones)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
