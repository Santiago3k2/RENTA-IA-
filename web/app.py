# -*- coding: utf-8 -*-
r"""RENTA IA — bandeja del contador, versión de escritorio.

Sin dependencias externas: solo la librería estándar. Descubre los casos en
..\\clientes\\<Contribuyente>\\AG<año>\\datos.py, calcula sus cifras con el
validador, les asigna semáforo, permite descargar el libro y sincronizar todo
con Supabase.

El HTML vive en render.py, compartido con la web publicada en Vercel.

Uso:  python app.py        →  http://localhost:8765
"""
import os
import sys
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

BASE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(BASE)
sys.path.insert(0, os.path.join(RAIZ, 'generador'))
sys.path.insert(0, BASE)

import autogen
import casos as casos_mod
import clasificador
import config
import db
import multipart
import render
import sincronizar
from render import e

PUERTO = int(os.environ.get('PUERTO') or 8765)
SUBIDAS = os.path.join(RAIZ, 'subidas')
os.makedirs(SUBIDAS, exist_ok=True)


def casos():
    """Los casos de disco, numerados para las rutas /caso/<n> y /libro/<n>."""
    lista = casos_mod.listar(RAIZ)
    for i, c in enumerate(lista):
        c['ref'] = str(i)
    return lista


def estado_nube():
    """Qué le falta a la copia en la nube para funcionar. Nunca se conecta."""
    problemas = config.revisar()
    return {'listo': not problemas, 'problemas': problemas}


def bloque_nube(mensaje='', total=0):
    """Franja de respaldo en la nube: estado, acción y qué falta configurar."""
    est = estado_nube()
    if est['listo']:
        cuerpo = (f'<p>Los {total} caso(s) de este equipo se copian a Supabase: '
                  'quedan respaldados y visibles en la web publicada. '
                  'Es idempotente — subirlos otra vez actualiza, no duplica. '
                  'El estado de revisión que ya tengan en la nube no se pisa.</p>'
                  '<form method="post" action="/sincronizar" id="fs">'
                  '<button type="submit" id="bs">Sincronizar con la nube</button></form>'
                  '<script>document.getElementById("fs").addEventListener("submit",'
                  'function(){var b=document.getElementById("bs");'
                  'b.disabled=true;b.textContent="Sincronizando…";});</script>')
    else:
        faltas = ''.join(f'<li>{e(p)}</li>' for p in est['problemas'])
        cuerpo = ('<p>El respaldo en la nube está apagado hasta completar el '
                  'archivo <b>.env</b> de la carpeta del proyecto:</p>'
                  f'<ul style="margin:8px 0 0 20px;font-size:12.8px;color:#5C4A15">{faltas}</ul>')
    aviso = f'<div class="err">{e(mensaje)}</div>' if mensaje.startswith('✗') else (
        f'<div class="ok-msg">{e(mensaje)}</div>' if mensaje else '')
    return f'<div class="subir nube"><h2>Respaldo en la nube</h2>{aviso}{cuerpo}</div>'


def bandeja(lista, error='', nube=''):
    return render.vista_bandeja(lista, error=error,
                                extra=bloque_nube(nube, len(lista)))


class Handler(BaseHTTPRequestHandler):
    server_version = 'RentaIA/1.0'

    def _html(self, contenido, code=200):
        datos = contenido.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        ruta = urllib.parse.urlparse(self.path).path
        try:
            if ruta in ('/', ''):
                return self._html(bandeja(casos()))
            if ruta.startswith('/caso/'):
                caso = casos()[int(ruta.split('/')[2])]
                if 'error' in caso:
                    return self._html(render.pagina(
                        'Error', f'<div class="err">{e(caso["error"])}</div>'
                                 '<p><a href="/">&larr; Volver</a></p>'), 500)
                return self._html(render.vista_caso(caso, clasificador.tolerancia))
            if ruta.startswith('/libro/'):
                caso = casos()[int(ruta.split('/')[2])]
                with open(os.path.join(caso['dir'], caso['libro']), 'rb') as f:
                    datos = f.read()
                self.send_response(200)
                self.send_header('Content-Type',
                                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                self.send_header('Content-Disposition',
                                 "attachment; filename*=UTF-8''" + urllib.parse.quote(caso['libro']))
                self.send_header('Content-Length', str(len(datos)))
                self.end_headers()
                self.wfile.write(datos)
                return
            self._html(render.pagina('No encontrado',
                                     '<div class="vacio">Esa página no existe. '
                                     '<a href="/">Volver a la bandeja</a></div>'), 404)
        except Exception as ex:
            self._html(render.pagina('Error', f'<div class="err">{e(ex)}</div>'
                                              '<p><a href="/">&larr; Volver</a></p>'), 500)

    def do_POST(self):
        ruta = urllib.parse.urlparse(self.path).path
        if ruta == '/sincronizar':
            return self._sincronizar()
        if ruta != '/subir':
            return self._html(render.pagina('No encontrado',
                                            '<p><a href="/">&larr; Volver</a></p>'), 404)
        try:
            largo = int(self.headers.get('Content-Length') or 0)
            if largo <= 0:
                raise ValueError('El envío llegó vacío.')
            if largo > 25 * 1024 * 1024:
                raise ValueError('El archivo supera los 25 MB.')
            nombre, datos = multipart.extraer_archivo(self.rfile.read(largo),
                                                      self.headers.get('Content-Type'))
            if not nombre.lower().endswith('.xlsx'):
                raise ValueError(
                    f'«{nombre}» no es un .xlsx. Si el reporte está en el formato .xls antiguo, '
                    'ábralo en Excel y guárdelo como «Libro de Excel (.xlsx)».')
            destino = os.path.join(SUBIDAS, nombre)
            with open(destino, 'wb') as f:
                f.write(datos)
            res = autogen.procesar_archivo(destino)
            if not res['generado']:
                raise ValueError('El caso se clasificó pero el libro no se pudo generar: '
                                 + res['salida'][-400:])
            ano = f"AG{res['caso']['ident']['ano']}"
            for i, c in enumerate(casos()):
                if c['persona'] == res['carpeta'] and c['ano'] == ano:
                    self.send_response(303)
                    self.send_header('Location', f'/caso/{i}')
                    self.end_headers()
                    return
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
        except Exception as ex:
            self._html(bandeja(casos(), f'No se pudo procesar el archivo: {ex}'), 400)

    def _sincronizar(self):
        """Sube todos los casos a Supabase y vuelve a la bandeja con el parte."""
        renglones = []
        try:
            ok, fallos = sincronizar.sincronizar(log=renglones.append)
            detalle = '\n'.join(r.strip() for r in renglones if r.strip())
            resumen = (f'✗ {ok} caso(s) subidos, {fallos} con problemas.\n{detalle}'
                       if fallos else f'{ok} caso(s) al día en la nube.\n{detalle}')
        except db.ErrorSupabase as ex:
            resumen = f'✗ {ex}'
        except Exception as ex:                      # nunca tumbar la bandeja
            resumen = f'✗ Error inesperado al sincronizar: {ex}'
        self._html(bandeja(casos(), nube=resumen))

    def log_message(self, fmt, *args):
        pass


if __name__ == '__main__':
    servidor = ThreadingHTTPServer(('127.0.0.1', PUERTO), Handler)
    servidor.daemon_threads = True
    print(f'{render.MARCA} → http://localhost:{PUERTO}')
    servidor.serve_forever()
