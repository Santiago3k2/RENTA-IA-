# -*- coding: utf-8 -*-
r"""RENTA IA en Vercel — la bandeja y el panel, sobre funciones sin estado.

Diferencias con la versión de escritorio, todas por el entorno:

  · No hay disco persistente. El caso se procesa en memoria y se guarda en
    Supabase (tablas + buckets privados); el .xlsx recibido solo pasa por /tmp,
    que es efímero.
  · Todo pide usuario y contraseña. Aquí viajan declaraciones de personas
    reales, sujetas a la reserva del art. 583 E.T.
  · Cada quien ve lo suyo: el cliente no ve la cartera del contador.

Este archivo decide **quién puede hacer qué**. Las reglas de las cuentas viven
en `generador\cuentas.py` y el HTML en `web\`; aquí solo se enruta y se manda.

Variables de entorno (Vercel → Settings → Environment Variables):

    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY   obligatorias
    RENTA_IA_CLAVE_ADMIN                      contraseña del primer «admin»
    RENTA_IA_SECRETO                          firma de las sesiones (recomendada)

Sin Supabase configurado el sitio no sirve nada: preferible fuera de servicio
que abierto. `RENTA_IA_CLAVE_ADMIN` es el seguro contra quedarse fuera — mientras
esté puesta, si la tabla de usuarios se quedara sin ningún administrador, el
primer acceso lo vuelve a crear.
"""
import base64
import datetime
import hashlib
import hmac
import os
import sys
import tempfile
import time
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# La raíz va también: el módulo RST es un paquete (`rst.…`) precisamente para
# que sus módulos —que se llaman igual que los del motor de renta— no se pisen
# con ellos dentro de este mismo proceso.
for sub in ('generador', 'web', ''):
    ruta = os.path.join(RAIZ, sub) if sub else RAIZ
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

import admin as vista_admin
import autogen
import calculos
import clasificador
import config
import cuentas as mod_cuentas
import db
import login
import multipart
import nube
import render
import rst_vista
from render import e

from rst import generar as rst_generar
from rst import libro as rst_libro
from rst import nube as rst_nube
from rst import parametros as rst_parametros


def env(nombre, defecto=''):
    """Variable de entorno limpia.

    En Vercel las variables vienen del entorno; en el equipo, del archivo .env
    de la raíz. Se miran las dos fuentes para que arrancar el sitio en local sea
    exactamente lo mismo que verlo publicado.

    Al pegarlas en el panel o cargarlas desde la consola se cuelan espacios,
    saltos de línea y hasta el BOM invisible de Windows (\\ufeff). Con la
    contraseña eso solo impide entrar, pero con un número tumbaba el módulo
    entero: más vale limpiar aquí que depender de cómo se escribió el valor.
    """
    valor = os.environ.get(nombre)
    if not valor:
        try:
            valor = config.ajustes().get(nombre)
        except Exception:
            valor = None
    return (valor or defecto).strip().lstrip('﻿').strip()


ADMIN = 'admin'
PILOTO = 'pruebapiloto2026'
LIMITE_SUBIDA = 4 * 1024 * 1024      # lo que admite una función de Vercel

# El apartado RST queda restringido al administrador mientras se decide cómo se
# habilita a las demás cuentas. Se comprueba en el servidor, no solo ocultando
# la pestaña: quien escriba la dirección a mano tampoco entra.
NO_HAY_RST = ('El apartado del Régimen Simple todavía no está habilitado para su '
              'cuenta. Escriba al contador si necesita acceso.')
LIMITE_FORMULARIO = 16 * 1024        # ningún formulario de estos pesa más

COOKIE = 'rentaia_sesion'
DURACION = 12 * 3600                 # una jornada de trabajo
DURACION_LARGA = 30 * 24 * 3600      # con «Recordarme» marcado

# Mensajes de confirmación. Se pasan por la URL como código, nunca como texto:
# así lo que se muestra sale siempre de aquí y no de lo que escriba nadie.
AVISOS = {
    'estado': 'Estado de la cuenta actualizado.',
    'rol': 'Rol actualizado.',
    'cupo': 'Cupo actualizado.',
    'datos': 'Datos de la cuenta guardados.',
    'sesiones': 'Se cerraron todas las sesiones de esa cuenta.',
    'desbloqueada': 'Se levantó el bloqueo por intentos fallidos.',
    'creada': 'Cuenta creada.',
    'eliminada': 'Cuenta eliminada.',
    'decl_estado': 'Estado de la declaración actualizado.',
    'ajustes': 'Ajustes guardados.',
    'clave': 'Su contraseña quedó cambiada.',
}


def hay_configuracion():
    """Faltantes de configuración; si hay alguno, el sitio no atiende."""
    return [k for k in ('SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY') if not env(k)]


def _cupo_piloto():
    """El cupo con el que se migra el usuario de prueba heredado."""
    try:
        return int(env('RENTA_IA_CUPO_PILOTO') or 5)
    except ValueError:
        return 5


# ── sesión en cookie firmada ────────────────────────────────────────────
def _secreto():
    """Clave con la que se firman las sesiones y los testigos anti-CSRF.

    Lo suyo es fijar RENTA_IA_SECRETO. Si no está, se deriva de la clave de
    servicio de Supabase: ya es secreta, ya es obligatoria y es estable, así que
    las sesiones sobreviven a los despliegues. Rotar esa clave cierra todas las
    sesiones abiertas, que es exactamente lo que uno quiere al rotarla.
    """
    base = env('RENTA_IA_SECRETO') or env('SUPABASE_SERVICE_ROLE_KEY')
    return hashlib.sha256(('renta-ia:' + base).encode('utf-8')).digest()


def _firma(mensaje):
    return hmac.new(_secreto(), mensaje.encode('utf-8'), hashlib.sha256).hexdigest()[:32]


def firmar(usuario, emitida, vence):
    crudo = f'{usuario}|{emitida}|{vence}|{_firma(f"{usuario}|{emitida}|{vence}")}'
    return base64.urlsafe_b64encode(crudo.encode('utf-8')).decode('ascii').rstrip('=')


def leer_cookie(cabecera_cookie):
    """(usuario, emitida) de una cookie vigente y bien firmada, o None.

    Aquí solo se comprueba la firma y la vigencia. Que la cuenta siga existiendo
    y siga activa se mira contra la base en `_sesion`: si no, inhabilitar a
    alguien no lo echaría hasta que venciera su cookie.
    """
    if not cabecera_cookie:
        return None
    try:
        galletas = SimpleCookie()
        galletas.load(cabecera_cookie)
        if COOKIE not in galletas:
            return None
        valor = galletas[COOKIE].value
        crudo = base64.urlsafe_b64decode(valor + '=' * (-len(valor) % 4)).decode('utf-8')
        usuario, emitida, vence, firma = crudo.split('|')
        emitida, vence = int(emitida), int(vence)
    except Exception:
        return None
    if not hmac.compare_digest(firma, _firma(f'{usuario}|{emitida}|{vence}')):
        return None
    return (usuario, emitida) if vence > time.time() else None


def testigo(usuario, emitida):
    """Testigo anti-CSRF: constante durante la sesión y atado a ella.

    SameSite=Lax ya impide que otro sitio envíe estos formularios, pero el panel
    borra cuentas y declaraciones: una segunda cerradura no sobra.
    """
    return _firma(f'csrf|{usuario}|{emitida}')


class handler(BaseHTTPRequestHandler):
    server_version = 'RentaIA'

    # ── petición ────────────────────────────────────────────────────
    def _ruta(self):
        """La ruta que pidió el navegador.

        Vercel reescribe todo a /api/index, así que `self.path` no siempre trae
        la original: el rewrite la reenvía en el parámetro `__ruta` y esa es la
        que manda. Sin esto, un POST a /entrar llegaba como /api/index y el
        formulario de acceso no respondía.
        """
        partes = urllib.parse.urlparse(self.path)
        pedida = urllib.parse.parse_qs(partes.query).get('__ruta', [None])[0]
        ruta = '/' + pedida.lstrip('/') if pedida is not None else partes.path
        if ruta in ('/api/index', '/api/index.py'):
            ruta = '/'
        return ruta.rstrip('/') or '/'

    def _consulta(self):
        """Los parámetros de la URL, sin el `__ruta` que mete el rewrite."""
        partes = urllib.parse.urlparse(self.path)
        c = {k: v[0] for k, v in urllib.parse.parse_qs(partes.query).items()}
        c.pop('__ruta', None)
        return c

    def _campos(self):
        """Los campos de un formulario normal (no el de subir archivos)."""
        largo = int(self.headers.get('Content-Length') or 0)
        if largo <= 0:
            return {}
        crudo = self.rfile.read(min(largo, LIMITE_FORMULARIO)).decode('utf-8', 'replace')
        return {k: v[0] for k, v in
                urllib.parse.parse_qs(crudo, keep_blank_values=True).items()}

    def _ip(self):
        """De dónde vino. Detrás del proxy de Vercel, la primera de la lista."""
        reenviada = self.headers.get('X-Forwarded-For') or ''
        return reenviada.split(',')[0].strip() or (self.client_address[0]
                                                   if self.client_address else '')

    def _por_https(self):
        """Si la conexión es segura. En local no lo es, y marcar la cookie como
        Secure allí impediría entrar para probar."""
        proto = (self.headers.get('X-Forwarded-Proto') or '').lower()
        if proto:
            return proto == 'https'
        anfitrion = (self.headers.get('Host') or '').lower()
        return not (anfitrion.startswith('localhost') or anfitrion.startswith('127.0.0.1'))

    # ── salida ──────────────────────────────────────────────────────
    def _html(self, contenido, code=200, cabeceras=None):
        datos = contenido.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(datos)))
        self.send_header('Cache-Control', 'no-store')          # datos reservados
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        for k, v in (cabeceras or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(datos)

    def _ir(self, destino):
        self.send_response(303)
        self.send_header('Location', destino)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()

    def _error(self, mensaje, code=500):
        self._html(render.pagina('Error', f'<div class="err">{e(mensaje)}</div>'
                                          '<p><a href="/">&larr; Volver</a></p>',
                                 pie=render.PIE_NUBE), code)

    def _no_configurado(self, faltan):
        self._error('El sitio no está configurado todavía. Faltan estas variables '
                    'de entorno en Vercel: ' + ', '.join(faltan), 503)

    # ── sesión ──────────────────────────────────────────────────────
    def _abrir_sesion(self, usuario, recordar=False, destino='/'):
        dura = DURACION_LARGA if recordar else DURACION
        ahora = int(time.time())
        # HttpOnly: el JavaScript de la página no puede leerla.
        # Secure + SameSite=Lax: no viaja fuera de HTTPS ni en peticiones que
        # nazcan en otro sitio, que es la defensa de fondo contra el CSRF.
        seguro = '; Secure' if self._por_https() else ''
        galleta = (f'{COOKIE}={firmar(usuario, ahora, ahora + dura)}; Path=/; '
                   f'HttpOnly{seguro}; SameSite=Lax; Max-Age={dura}')
        self.send_response(303)
        self.send_header('Location', destino)
        self.send_header('Set-Cookie', galleta)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()

    def _cerrar_sesion(self):
        seguro = '; Secure' if self._por_https() else ''
        self.send_response(303)
        self.send_header('Location', '/entrar')
        self.send_header('Set-Cookie',
                         f'{COOKIE}=; Path=/; HttpOnly{seguro}; SameSite=Lax; Max-Age=0')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()

    def _sesion(self, exigir_clave_al_dia=True):
        """El contexto del usuario, o None (y ya respondió lo que tocaba).

        Cada petición vuelve a leer la cuenta de la base. Cuesta una consulta y
        compra que inhabilitar a alguien lo eche en el acto, en lugar de dejarlo
        dentro hasta que su cookie venza.
        """
        faltan = hay_configuracion()
        if faltan:
            self._no_configurado(faltan)
            return None
        galleta = leer_cookie(self.headers.get('Cookie'))
        if not galleta:
            self._pantalla_acceso()
            return None
        nombre, emitida = galleta
        try:
            c = mod_cuentas.Cuentas(db.Supabase.desde_env())
            fila = c.buscar(nombre)
        except db.ErrorSupabase as ex:
            self._error(str(ex), 502)
            return None

        if not fila or fila['estado'] != 'activo':
            # La cuenta se eliminó o se inhabilitó con la sesión abierta.
            return self._expulsar('Su cuenta ya no tiene acceso. Consulte con el contador.')
        nacida = mod_cuentas.desde_iso(fila.get('sesiones_desde'))
        # La holgura de cinco segundos absorbe el desfase entre el reloj de la
        # base y el del servidor web. Sin ella, cerrar sesiones o cambiar la
        # contraseña podría invalidar la cookie que se acaba de emitir.
        if nacida and emitida < nacida.timestamp() - 5:
            return self._expulsar('Su sesión se cerró. Vuelva a entrar.')

        ses = {'usuario': fila['usuario'], 'rol': fila['rol'], 'fila': fila,
               'cuentas': c, 's': c.s, 'emitida': emitida,
               'testigo': testigo(fila['usuario'], emitida),
               'es_admin': fila['rol'] == 'admin',
               've_todo': fila['rol'] in ('admin', 'contador'),
               'solo_de': fila['usuario'] if fila['rol'] == 'cliente' else None,
               'cupo': fila['cupo']}
        if exigir_clave_al_dia and fila.get('debe_cambiar_clave'):
            # Ni una página más hasta que elija una contraseña que solo sepa él.
            self._ir('/clave')
            return None
        return ses

    def _expulsar(self, motivo):
        seguro = '; Secure' if self._por_https() else ''
        self._html(login.pagina(motivo), 401, {
            'Set-Cookie': f'{COOKIE}=; Path=/; HttpOnly{seguro}; SameSite=Lax; Max-Age=0'})
        return None

    def _pantalla_acceso(self, mensaje='', usuario='', code=401, hecho=''):
        abierto = False
        try:
            abierto = mod_cuentas.Cuentas(db.Supabase.desde_env()).ajuste_bool(
                'registro_abierto', True)
        except Exception:
            pass
        self._html(login.pagina(mensaje, usuario, abierto, hecho), code)

    def _testigo_ok(self, campos, ses):
        return hmac.compare_digest(str(campos.get('_t', '')), ses['testigo'])

    def _nav(self, ses, activo='bandeja'):
        return vista_admin.nav(activo, ses['rol'])

    # ══ GET ═════════════════════════════════════════════════════════
    def do_GET(self):
        ruta = self._ruta()
        try:
            if ruta == '/salir':
                return self._cerrar_sesion()
            if ruta == '/entrar':
                return self._get_entrar()
            if ruta == '/registrarse':
                return self._get_registro()

            ses = self._sesion(exigir_clave_al_dia=(ruta != '/clave'))
            if not ses:
                return
            if ruta == '/clave':
                return self._html(login.pagina_clave(
                    ses['usuario'], ses['testigo'], min_clave=mod_cuentas.MIN_CLAVE))
            if ruta == '/':
                return self._html(self._bandeja(ses))
            if ruta == '/cuenta':
                return self._get_mi_cuenta(ses)
            if ruta.startswith('/caso/'):
                return self._get_caso(ses, ruta.split('/')[2])
            if ruta.startswith('/libro/'):
                return self._get_libro(ses, ruta.split('/')[2])
            if ruta.startswith('/rst'):
                if not ses['es_admin']:
                    return self._error(NO_HAY_RST, 403)
            if ruta == '/rst':
                return self._html(self._bandeja_rst(ses))
            if ruta.startswith('/rst/libro/'):
                return self._get_libro_rst(ses, ruta.split('/')[3])
            if ruta.endswith('/eliminar') and ruta.startswith('/rst/'):
                return self._eliminar_rst(ses, ruta.split('/')[2])
            if ruta.startswith('/rst/'):
                return self._get_recibo_rst(ses, ruta.split('/')[2])
            if ruta.startswith('/admin'):
                if not ses['es_admin']:
                    return self._error('Esta sección es solo del administrador.', 403)
                return self._get_admin(ses, ruta)

            self._html(render.pagina('No encontrado',
                                     '<div class="vacio">Esa página no existe. '
                                     '<a href="/">Volver a la bandeja</a></div>',
                                     usuario=ses['usuario'], pie=render.PIE_NUBE,
                                     nav=self._nav(ses)), 404)
        except db.ErrorSupabase as ex:
            self._error(str(ex), 502)
        except Exception as ex:
            self._error(f'Error inesperado: {ex}')

    def _get_entrar(self):
        faltan = hay_configuracion()
        if faltan:
            return self._no_configurado(faltan)
        if leer_cookie(self.headers.get('Cookie')):
            return self._ir('/')
        consulta = self._consulta()
        hecho = ''
        if consulta.get('nueva') == '1':
            hecho = 'Su cuenta quedó creada. Ya puede entrar.'
        elif consulta.get('nueva') == 'pendiente':
            hecho = ('Su cuenta quedó creada y está a la espera de aprobación. '
                     'Le avisaremos por correo cuando pueda entrar.')
        self._pantalla_acceso(code=200, hecho=hecho)

    def _get_registro(self):
        faltan = hay_configuracion()
        if faltan:
            return self._no_configurado(faltan)
        c = mod_cuentas.Cuentas(db.Supabase.desde_env())
        if not c.ajuste_bool('registro_abierto', True):
            return self._pantalla_acceso(
                'El registro de cuentas nuevas está cerrado en este momento. '
                'Escriba al contador para pedir acceso.', code=200)
        self._html(login.pagina_registro(
            min_clave=mod_cuentas.MIN_CLAVE,
            aprobacion=c.ajuste_bool('requiere_aprobacion', False)))

    def _get_mi_cuenta(self, ses):
        c = ses['cuentas']
        datos = {'usadas': c.cuantas_lleva(ses['usuario']),
                 'movimientos': c.bitacora(limite=15, usuario=ses['usuario'])}
        aviso = AVISOS.get(self._consulta().get('ok', ''), '')
        self._html(vista_admin.vista_mi_cuenta(ses['fila'], datos, ses['testigo'],
                                               hecho=aviso))

    def _get_caso(self, ses, ref):
        caso = nube.buscar(ref, ses['s'], solo_de=ses['solo_de'])
        if not caso:
            return self._error('Ese caso no existe o no es suyo.', 404)
        if 'error' in caso:
            return self._error(caso['error'])
        acciones = self._acciones_caso(ses, caso)
        self._html(render.vista_caso(caso, clasificador.tolerancia,
                                     usuario=ses['usuario'], pie=render.PIE_NUBE,
                                     mostrar_estado=True, nav=self._nav(ses),
                                     rol=vista_admin.ROL_NOMBRE.get(ses['rol'], ''),
                                     acciones=acciones,
                                     estilo_extra=vista_admin.ESTILO if acciones else ''))

    def _acciones_caso(self, ses, caso):
        """Los botones del pie del caso: mover el estado y, si procede, borrar."""
        bloques = []
        if ses['ve_todo']:
            botones = []
            for valor, texto in (('borrador', 'Devolver a borrador'),
                                 ('en_revision', 'Marcar en revisión'),
                                 ('liberada', 'Liberar')):
                if valor == caso.get('estado'):
                    continue
                botones.append(
                    f'<form method="post" action="/caso/{e(caso["ref"])}/estado">'
                    f'<input type="hidden" name="_t" value="{e(ses["testigo"])}">'
                    f'<input type="hidden" name="estado" value="{valor}">'
                    f'<button class="mini sec" type="submit">{e(texto)}</button></form>')
            bloques.append(
                '<div class="seccion" style="margin-top:22px"><h2>Revisión</h2>'
                '<div class="cuerpo"><p>Liberar deja constancia de que usted revisó '
                'este caso y lo da por bueno. Es una marca de trabajo, no un envío '
                'a la DIAN.</p><div class="acc-fila" style="justify-content:flex-start">'
                + ''.join(botones) + '</div></div></div>')
        # Una declaración no se elimina desde ninguna parte. El cupo es lo que
        # se vende: si borrar devolviera el cupo, una cuenta de cupo 1 podría
        # procesar sin límite subiendo, borrando y volviendo a subir.
        return ''.join(bloques)

    def _get_libro(self, ses, ref):
        caso = nube.buscar(ref, ses['s'], solo_de=ses['solo_de'])
        if not caso or not caso.get('libro_path'):
            return self._error('Ese libro no existe o no es suyo.', 404)
        ses['cuentas'].anotar('libro_descargado', ses['usuario'], rol=ses['rol'],
                              objeto=f"{caso['persona']} · {caso['ano']}", ip=self._ip())
        # URL firmada de vigencia corta: el bucket nunca se hace público.
        url = ses['s'].url_firmada(db.BUCKET_LIBROS, caso['libro_path'], 120)
        self.send_response(302)
        self.send_header('Location', url)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()

    # ── GET del panel ───────────────────────────────────────────────
    def _get_admin(self, ses, ruta):
        c, consulta = ses['cuentas'], self._consulta()
        ok, err = AVISOS.get(consulta.get('ok', ''), ''), consulta.get('err', '')
        partes = ruta.strip('/').split('/')          # ['admin', ...]

        if ruta == '/admin':
            return self._html(vista_admin.vista_resumen(
                self._resumen(ses), ses['usuario'], ses['testigo'], err, ok))

        if ruta == '/admin/cuentas':
            filtro = consulta.get('estado', '')
            lista = c.listar(estado=filtro or None)
            usadas = self._usadas_por_cuenta(ses)
            return self._html(vista_admin.vista_cuentas(
                lista, usadas, ses['usuario'], ses['testigo'], filtro, err, ok))

        if ruta == '/admin/cuentas/nueva':
            return self._html(vista_admin.vista_nueva_cuenta(
                ses['usuario'], ses['testigo'], error=err))

        if ruta == '/admin/declaraciones':
            return self._html(vista_admin.vista_declaraciones(
                self._declaraciones(ses), ses['usuario'], ses['testigo'], err, ok))

        if ruta == '/admin/bitacora':
            try:
                limite = max(20, min(1000, int(consulta.get('n', 200))))
            except ValueError:
                limite = 200
            usuario = consulta.get('usuario', '').strip()
            accion = consulta.get('accion', '').strip()
            entradas = c.bitacora(limite=limite, usuario=usuario or None,
                                  accion=accion or None)
            return self._html(vista_admin.vista_bitacora(
                entradas, ses['usuario'], usuario, accion, limite, err))

        if ruta == '/admin/ajustes':
            valores = {
                'registro_abierto': c.ajuste_bool('registro_abierto', True),
                'requiere_aprobacion': c.ajuste_bool('requiere_aprobacion', False),
                'cupo_por_defecto': c.ajuste_int('cupo_por_defecto', 1),
                'mensaje_portada': c.ajuste('mensaje_portada', '') or '',
            }
            return self._html(vista_admin.vista_ajustes(
                valores, ses['usuario'], ses['testigo'], err, ok))

        # /admin/cuenta/<id>[/eliminar]
        if len(partes) >= 3 and partes[1] == 'cuenta':
            u = c.buscar_id(partes[2])
            if not u:
                return self._error('Esa cuenta ya no existe.', 404)
            if len(partes) == 4 and partes[3] == 'eliminar':
                return self._html(vista_admin.vista_confirmar_cuenta(
                    u, c.cuantas_lleva(u['usuario']), ses['usuario'], ses['testigo']))
            datos = {'usadas': c.cuantas_lleva(u['usuario']),
                     'declaraciones': self._declaraciones(ses, de=u['usuario'])}
            return self._html(vista_admin.vista_cuenta(
                u, datos, ses['usuario'], ses['testigo'], err, ok))

        self._error('Esa página del panel no existe.', 404)

    # ── datos para el panel ─────────────────────────────────────────
    def _resumen(self, ses):
        c, s = ses['cuentas'], ses['s']
        lista = c.listar()
        desde = mod_cuentas.iso(mod_cuentas.ahora() - datetime.timedelta(days=1))
        fallidos = s.contar('bitacora', accion='eq.acceso_fallido',
                            ocurrido_en='gte.' + desde)
        ahora = mod_cuentas.ahora()
        bloqueadas = sum(
            1 for u in lista
            if (mod_cuentas.desde_iso(u.get('bloqueado_hasta')) or ahora) > ahora)
        return {
            'cuentas': len(lista),
            'activas': sum(1 for u in lista if u['estado'] == 'activo'),
            'pendientes': sum(1 for u in lista if u['estado'] == 'pendiente'),
            'inhabilitadas': sum(1 for u in lista if u['estado'] == 'inhabilitado'),
            'bloqueadas': bloqueadas,
            'declaraciones': s.contar('declaraciones'),
            'contribuyentes': s.contar('contribuyentes'),
            'liberadas': s.contar('declaraciones', estado='eq.liberada'),
            'fallidos': fallidos,
            'ultimos': c.bitacora(limite=12),
        }

    def _usadas_por_cuenta(self, ses):
        """Cuántas declaraciones lleva cada cuenta, en una sola consulta."""
        usadas = {}
        for d in ses['s'].seleccionar('declaraciones', select='creada_por'):
            usadas[d['creada_por']] = usadas.get(d['creada_por'], 0) + 1
        return usadas

    def _declaraciones(self, ses, de=None):
        filtros = {'select': 'id,ano_gravable,estado,semaforo,creada_por,creado_en,'
                             'libro_path,exogena_path,'
                             'contribuyentes(nombre_titulo,identificacion)',
                   'order': 'creado_en.desc'}
        if de:
            filtros['creada_por'] = 'eq.' + de
        filas = ses['s'].seleccionar('declaraciones', **filtros)
        registrados = {u['usuario'] for u in ses['cuentas'].listar()}
        for f in filas:
            f['dueno_existe'] = f.get('creada_por') in registrados
        return filas

    def _bandeja(self, ses, error='', hecho=''):
        c = ses['cuentas']
        lista = nube.listar(ses['s'], solo_de=ses['solo_de'])
        cupo = c.cupo_de(ses['fila'])
        if ses['ve_todo']:
            sub = ('BANDEJA DEL CONTADOR &nbsp;&middot;&nbsp; CADA CASO SE VALIDA '
                   'CONTRA LOS TOPES DE LA DIAN')
        else:
            sub = ('SUS DECLARACIONES &nbsp;&middot;&nbsp; USTED VE ÚNICAMENTE LAS '
                   'QUE HA CARGADO')
        return render.vista_bandeja(
            lista, error=error, hecho=hecho, usuario=ses['usuario'], cupo=cupo,
            pie=render.PIE_NUBE, mostrar_estado=True, sub=sub, nav=self._nav(ses),
            rol=vista_admin.ROL_NOMBRE.get(ses['rol'], ''), token=ses['testigo'],
            aviso=c.ajuste('mensaje_portada', '') or '')

    # ══ Apartado RST — Régimen Simple ═══════════════════════════════
    # Tablas propias (`recibos_rst`), porque la clave del caso es
    # (contribuyente, año, bimestre). Alcance: solo los anticipos bimestrales
    # del Formulario 2593; la declaración anual del SIMPLE queda fuera.

    def _bandeja_rst(self, ses, error='', hecho=''):
        lista = rst_nube.listar(ses['s'], solo_de=ses['solo_de'])
        cupo = ses['cuentas'].cupo_de(ses['fila'])
        return rst_vista.vista_bandeja(
            lista, error=error, hecho=hecho, usuario=ses['usuario'], cupo=cupo,
            pie=render.PIE_NUBE, mostrar_estado=True, nav=self._nav(ses, 'rst'),
            rol=vista_admin.ROL_NOMBRE.get(ses['rol'], ''), token=ses['testigo'])

    def _get_recibo_rst(self, ses, ref):
        caso = rst_nube.buscar(ses['s'], ref, solo_de=ses['solo_de'])
        if not caso:
            return self._error('Ese recibo no existe o no es suyo.', 404)
        self._html(rst_vista.vista_recibo(
            caso, usuario=ses['usuario'], pie=render.PIE_NUBE, mostrar_estado=True,
            nav=self._nav(ses, 'rst'),
            rol=vista_admin.ROL_NOMBRE.get(ses['rol'], ''),
            acciones=self._acciones_rst(ses, caso),
            estilo_extra=vista_admin.ESTILO + rst_vista.ESTILO))

    def _acciones_rst(self, ses, caso):
        if ses['ve_todo']:
            botones = []
            for valor, texto in (('borrador', 'Devolver a borrador'),
                                 ('en_revision', 'Marcar en revisión'),
                                 ('liberada', 'Liberar')):
                if valor == caso.get('estado'):
                    continue
                botones.append(
                    f'<form method="post" action="/rst/{e(caso["ref"])}/estado">'
                    f'<input type="hidden" name="_t" value="{e(ses["testigo"])}">'
                    f'<input type="hidden" name="estado" value="{valor}">'
                    f'<button class="mini sec" type="submit">{e(texto)}</button></form>')
            return ('<div class="seccion" style="margin-top:22px"><h2>Revisión</h2>'
                    '<div class="cuerpo"><p>Liberar deja constancia de que usted revisó '
                    'este recibo y lo da por bueno. Es una marca de trabajo, no una '
                    'presentación ante la DIAN.</p>'
                    '<div class="acc-fila" style="justify-content:flex-start">'
                    + ''.join(botones) + '</div></div></div>')
        if caso.get('estado') == 'borrador' and caso.get('creada_por') == ses['usuario']:
            return (f'<div class="seccion" style="margin-top:22px">'
                    f'<h2>¿Se equivocó de archivo?</h2><div class="cuerpo">'
                    f'<p>Puede eliminar este recibo mientras siga en borrador. Se borran '
                    f'su libro y el consolidado que subió, y recupera el cupo.</p>'
                    f'<form method="get" action="/rst/{e(caso["ref"])}/eliminar">'
                    f'<button class="mini peligro" type="submit">Eliminar este recibo'
                    f'</button></form></div></div>')
        return ''

    def _get_libro_rst(self, ses, ref):
        caso = rst_nube.buscar(ses['s'], ref, solo_de=ses['solo_de'])
        if not caso or not caso['fila'].get('libro_path'):
            return self._error('Ese libro no existe o no es suyo.', 404)
        ses['cuentas'].anotar('libro_rst_descargado', ses['usuario'], rol=ses['rol'],
                              objeto=f"{caso['persona']} · {caso['periodo']}",
                              ip=self._ip())
        url = ses['s'].url_firmada(db.BUCKET_LIBROS, caso['fila']['libro_path'], 120)
        self.send_response(302)
        self.send_header('Location', url)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()

    def _eliminar_rst(self, ses, ref):
        caso = rst_nube.buscar(ses['s'], ref, solo_de=ses['solo_de'])
        if not caso:
            return self._error('Ese recibo no existe o no es suyo.', 404)
        if not ses['ve_todo'] and (caso.get('estado') != 'borrador'
                                   or caso.get('creada_por') != ses['usuario']):
            return self._error('Solo puede eliminar un recibo suyo que siga en '
                               'borrador.', 403)
        rst_nube.eliminar(ses['s'], ref)
        ses['cuentas'].anotar('recibo_rst_eliminado', ses['usuario'], rol=ses['rol'],
                              objeto=f"{caso['persona']} · {caso['periodo']}",
                              ip=self._ip())
        self._ir('/rst')

    def _ficha_desde_formulario(self, crudo):
        """Los campos del formulario → la ficha del contribuyente.

        Es lo que el consolidado de la DIAN no trae y el motor no puede
        adivinar: el grupo de actividad SIMPLE —que es una decisión de criterio,
        no un dato— y la tarifa consolidada de ICA del municipio.
        """
        def campo(nombre, defecto=''):
            v = multipart.extraer_campo(crudo, nombre)
            return (v or defecto).strip()

        nombre = campo('nombre')
        nit = campo('nit')
        if not nombre or not nit:
            raise ValueError('Faltan la razón social o el NIT del contribuyente.')
        # El bimestre puede venir vacío: significa «detectar del archivo», que
        # es lo normal. Lo resuelve `rst_generar.resolver_periodo` con las
        # fechas de los documentos, y así nadie tiene que acertarlo.
        crudo_bim = campo('bimestre')
        try:
            ano = int(campo('ano') or 0)
            bimestre = int(crudo_bim) if crudo_bim else None
            grupo = int(campo('grupo') or 0)
        except ValueError:
            raise ValueError('El año, el bimestre y el grupo deben ser números.')
        if bimestre is not None and bimestre not in rst_parametros.BIMESTRES:
            raise ValueError('El bimestre debe ir de 1 a 6, o dejarse en blanco para '
                             'detectarlo del archivo.')
        if grupo not in rst_parametros.TARIFAS:
            raise ValueError('Elija el grupo de actividad SIMPLE: define la tarifa y no '
                             'hay un valor por defecto razonable.')
        rst_parametros.uvt(ano)          # falla claro si no está cargada la UVT

        # La tarifa de ICA se pide «por mil» porque así la publican los acuerdos
        # municipales; guardarla como 12,5 en vez de 0,0125 es el error fácil.
        crudo_ica = campo('tarifa_ica').replace(',', '.')
        try:
            por_mil = float(crudo_ica)
        except ValueError:
            raise ValueError('La tarifa de ICA no se entiende: escríbala por mil, '
                             'por ejemplo 12,5.')
        if por_mil > 1:
            tarifa_ica = por_mil / 1000.0
        else:
            tarifa_ica = por_mil          # ya venía en decimal
        if not 0 < tarifa_ica < 0.05:
            raise ValueError('La tarifa de ICA queda fuera de todo rango razonable. '
                             'Escríbala por mil, por ejemplo 12,5.')

        return {
            'nombre': nombre, 'nit': nit, 'dv': campo('dv'),
            'direccion_seccional': campo('direccion_seccional'),
            'ciiu': campo('ciiu'), 'ano': ano, 'bimestre': bimestre, 'grupo': grupo,
            'responsable_iva': campo('responsable_iva', '1') == '1',
            'municipio': campo('municipio'), 'cod_dane': campo('cod_dane'),
            'depto': campo('depto'), 'tarifa_ica': tarifa_ica,
            'incrngo': 0, 'ganancias_ocasionales': 0, 'devoluciones': 0,
            'ingresos_no_gravados_ica': 0, 'retenciones_previas': 0,
            'saldo_favor_iva_anterior': 0, 'inc': 0, 'sanciones': 0,
            'aporte_pension_total': self._num_suelto(campo('aporte_pension_total')),
        }

    @staticmethod
    def _num_suelto(txt):
        """Un número escrito por una persona: '920.200', '920200', '920,200'."""
        t = (txt or '').replace('$', '').replace(' ', '').replace('.', '').replace(',', '.')
        try:
            return float(t) if t else 0.0
        except ValueError:
            raise ValueError('«%s» no es una cifra que se pueda leer.' % txt)

    def _post_subir_rst(self, ses):
        """Recibe el consolidado, liquida el bimestre en memoria y lo guarda."""
        s, c = ses['s'], ses['cuentas']
        try:
            if ses['cupo'] is not None:
                usadas = rst_nube.cuantos_lleva(s, ses['usuario'])
                if usadas >= ses['cupo']:
                    return self._html(self._bandeja_rst(
                        ses, f'Su cupo está completo: {usadas} de {ses["cupo"]}. '
                             f'Para ampliarlo, escriba al contador.'), 403)

            largo = int(self.headers.get('Content-Length') or 0)
            if largo <= 0:
                raise ValueError('El envío llegó vacío.')
            if largo > LIMITE_SUBIDA:
                raise ValueError(
                    'El consolidado supera los 4 MB que admite el servidor. Ábralo en '
                    'Excel, deje solo las hojas F.VENTA, F.COMPRA, RETEIVA y S.SOCIAL, '
                    'guárdelo de nuevo y reintente; o procéselo desde el equipo del '
                    'contador, que no tiene ese tope.')
            crudo = self.rfile.read(largo)

            if not hmac.compare_digest(multipart.extraer_campo(crudo, '_t') or '',
                                       ses['testigo']):
                return self._error('La página caducó. Vuelva al apartado RST y '
                                   'reintente la carga.', 400)

            ficha = self._ficha_desde_formulario(crudo)
            nombre, datos = multipart.extraer_archivo(
                crudo, self.headers.get('Content-Type'))
            if not nombre.lower().endswith('.xlsx'):
                raise ValueError(f'«{nombre}» no es un .xlsx.')

            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                tmp.write(datos)
                temporal = tmp.name
            try:
                liq, wb = rst_generar.procesar(temporal, ficha)
            finally:
                try:
                    os.unlink(temporal)
                except OSError:
                    pass

            recibo = rst_nube.guardar_recibo(
                s, ficha, liq, libro_bytes=rst_libro.a_bytes(wb),
                nombre_libro=rst_generar.nombre_salida(ficha, liq),
                consolidado_bytes=datos, nombre_consolidado=nombre,
                creada_por=ses['usuario'], solo_si_dueno=ses['solo_de'])
            c.anotar('recibo_rst_creado', ses['usuario'], rol=ses['rol'],
                     objeto=f"{ficha['nombre']} · {liq['ano']} bim {liq['bimestre']}",
                     detalle=f"semáforo {liq['semaforo']}", ip=self._ip())
            self._ir('/rst/' + recibo['id'])
        except db.ErrorPermiso as ex:
            self._html(self._bandeja_rst(ses, str(ex)), 403)
        except db.ErrorSupabase as ex:
            self._html(self._bandeja_rst(ses, str(ex)), 502)
        except Exception as ex:
            try:
                self._html(self._bandeja_rst(
                    ses, f'No se pudo procesar el consolidado: {ex}'), 400)
            except Exception:
                self._error(f'No se pudo procesar el consolidado: {ex}', 400)

    def _post_recibo_rst(self, ses, partes, campos):
        """POST /rst/<id>/estado — mover el recibo por el flujo de revisión."""
        ref = partes[2] if len(partes) > 2 else ''
        accion = partes[3] if len(partes) > 3 else ''
        if accion != 'estado':
            return self._error('Esa acción no existe.', 404)
        if not ses['ve_todo']:
            return self._error('Solo el contador mueve el estado de un recibo.', 403)
        estado = (campos or {}).get('estado', '')
        if estado not in ('borrador', 'en_revision', 'liberada'):
            return self._error('Estado desconocido.', 400)
        rst_nube.cambiar_estado(ses['s'], ref, estado, por=ses['usuario'])
        ses['cuentas'].anotar('recibo_rst_' + estado, ses['usuario'], rol=ses['rol'],
                              objeto=ref, ip=self._ip())
        self._ir('/rst/' + ref)

    # ══ POST ════════════════════════════════════════════════════════
    def do_POST(self):
        ruta = self._ruta()
        try:
            if ruta == '/entrar':
                return self._post_entrar()
            if ruta == '/registrarse':
                return self._post_registro()

            ses = self._sesion(exigir_clave_al_dia=(ruta != '/clave'))
            if not ses:
                return
            campos = self._campos() if ruta not in ('/subir', '/rst/subir') else None
            if campos is not None and not self._testigo_ok(campos, ses):
                # Un formulario que no trae el testigo de esta sesión no salió
                # de esta aplicación, o la sesión cambió mientras estaba abierto.
                return self._error('La página caducó o el envío no venía de aquí. '
                                   'Vuelva a intentarlo desde la pantalla.', 400)

            if ruta == '/clave':
                return self._post_clave_forzada(ses, campos)
            if ruta == '/subir':
                return self._post_subir(ses)
            if ruta.startswith('/rst'):
                if not ses['es_admin']:
                    return self._error(NO_HAY_RST, 403)
                if ruta == '/rst/subir':
                    return self._post_subir_rst(ses)
                return self._post_recibo_rst(ses, ruta.split('/'), campos)
            if ruta == '/cuenta/clave':
                return self._post_mi_clave(ses, campos)
            if ruta.startswith('/caso/'):
                return self._post_caso(ses, ruta.split('/'), campos)
            if ruta.startswith('/admin'):
                if not ses['es_admin']:
                    return self._error('Esta sección es solo del administrador.', 403)
                return self._post_admin(ses, ruta, campos)
            self._error('Esa acción no existe.', 404)
        except db.ErrorSupabase as ex:
            self._error(str(ex), 502)
        except Exception as ex:
            self._error(f'Error inesperado: {ex}')

    def _post_entrar(self):
        """Valida el formulario de acceso y abre la sesión."""
        faltan = hay_configuracion()
        if faltan:
            return self._no_configurado(faltan)
        campos = self._campos()
        usuario = campos.get('usuario', '').strip()
        clave = campos.get('clave', '')
        if not usuario or not clave:
            return self._pantalla_acceso('Escriba su usuario y su contraseña.', usuario)

        c = mod_cuentas.Cuentas(db.Supabase.desde_env())
        try:
            # Los dos usuarios que vivían en variables de entorno pasan a la
            # tabla la primera vez que alguien intenta entrar. Solo una vez: si
            # después se elimina alguno desde el panel, no vuelve.
            c.migrar_heredados({
                ADMIN: {'clave': env('RENTA_IA_CLAVE_ADMIN'), 'rol': 'admin',
                        'nombre': 'Administrador', 'cupo': None},
                PILOTO: {'clave': env('RENTA_IA_CLAVE_PILOTO'), 'rol': 'cliente',
                         'nombre': 'Usuario de prueba', 'cupo': _cupo_piloto()},
            })
            # Y este es el seguro permanente contra quedarse fuera: si la tabla
            # se queda sin ningún administrador, se recrea el de arranque.
            c.asegurar_admin(ADMIN, env('RENTA_IA_CLAVE_ADMIN'))
        except Exception:
            pass

        fila, error = c.autenticar(usuario, clave, ip=self._ip())
        if not fila:
            time.sleep(0.7)      # frena el ensayo y error sin castigar al distraído
            return self._pantalla_acceso(error, usuario)
        destino = '/clave' if fila.get('debe_cambiar_clave') else '/'
        self._abrir_sesion(fila['usuario'], bool(campos.get('recordar')), destino)

    def _post_registro(self):
        faltan = hay_configuracion()
        if faltan:
            return self._no_configurado(faltan)
        campos = self._campos()
        c = mod_cuentas.Cuentas(db.Supabase.desde_env())
        aprobacion = c.ajuste_bool('requiere_aprobacion', False)
        valores = {k: campos.get(k, '').strip()
                   for k in ('usuario', 'nombre', 'correo', 'telefono')}

        def volver(mensaje):
            self._html(login.pagina_registro(mensaje, valores,
                                             mod_cuentas.MIN_CLAVE, aprobacion), 400)

        if campos.get('clave', '') != campos.get('repetir', ''):
            return volver('Las dos contraseñas no coinciden.')
        try:
            c.registrar(valores['usuario'], valores['nombre'], campos.get('clave', ''),
                        valores['correo'], valores['telefono'], ip=self._ip())
        except mod_cuentas.ErrorCuenta as ex:
            return volver(str(ex))
        self._ir('/entrar?nueva=' + ('pendiente' if aprobacion else '1'))

    def _post_clave_forzada(self, ses, campos):
        """El cambio obligatorio tras un restablecimiento del administrador."""
        def volver(mensaje):
            self._html(login.pagina_clave(ses['usuario'], ses['testigo'], mensaje,
                                          mod_cuentas.MIN_CLAVE), 400)
        if campos.get('clave', '') != campos.get('repetir', ''):
            return volver('Las dos contraseñas no coinciden.')
        try:
            ses['cuentas'].cambiar_clave(ses['fila']['id'], campos.get('actual', ''),
                                         campos.get('clave', ''))
        except mod_cuentas.ErrorCuenta as ex:
            return volver(str(ex))
        # Cambiar la contraseña invalida las sesiones: hay que emitir una nueva.
        self._abrir_sesion(ses['usuario'], False, '/')

    def _post_mi_clave(self, ses, campos):
        if campos.get('nueva', '') != campos.get('repetir', ''):
            return self._html(self._mi_cuenta_con(ses, 'Las dos contraseñas no coinciden.'), 400)
        try:
            ses['cuentas'].cambiar_clave(ses['fila']['id'], campos.get('actual', ''),
                                         campos.get('nueva', ''))
        except mod_cuentas.ErrorCuenta as ex:
            return self._html(self._mi_cuenta_con(ses, str(ex)), 400)
        self._abrir_sesion(ses['usuario'], False, '/cuenta?ok=clave')

    def _mi_cuenta_con(self, ses, error):
        c = ses['cuentas']
        datos = {'usadas': c.cuantas_lleva(ses['usuario']),
                 'movimientos': c.bitacora(limite=15, usuario=ses['usuario'])}
        return vista_admin.vista_mi_cuenta(ses['fila'], datos, ses['testigo'], error)

    def _post_caso(self, ses, partes, campos):
        ref = partes[2]
        accion = partes[3] if len(partes) > 3 else ''
        caso = nube.buscar(ref, ses['s'], solo_de=ses['solo_de'])
        if not caso:
            return self._error('Ese caso no existe o no es suyo.', 404)

        if accion == 'estado':
            if not ses['ve_todo']:
                return self._error('Solo el contador cambia el estado de un caso.', 403)
            estado = campos.get('estado', '')
            ses['s'].cambiar_estado(ref, estado, por=ses['usuario'])
            ses['cuentas'].anotar('declaracion_estado', ses['usuario'], rol=ses['rol'],
                                  objeto=f"{caso['persona']} · {caso['ano']}",
                                  detalle=f'→ {estado}', ip=self._ip())
            return self._ir(f'/caso/{ref}')

        if accion == 'eliminar':
            return self._error('Las declaraciones de renta no se eliminan: una vez '
                               'procesada, la declaración y el cupo que consumió '
                               'quedan.', 403)
        self._error('Esa acción no existe.', 404)

    def _post_subir(self, ses):
        """Recibe la exógena, la procesa en memoria y guarda el caso."""
        s, c = ses['s'], ses['cuentas']
        try:
            if ses['cupo'] is not None:
                usadas = c.cuantas_lleva(ses['usuario'])
                if usadas >= ses['cupo']:
                    return self._html(self._bandeja(
                        ses, f'Su cupo está completo: {usadas} de {ses["cupo"]} '
                             f'declaraciones. Puede seguir consultando las que ya '
                             f'cargó; para ampliarlo, escriba al contador.'), 403)

            largo = int(self.headers.get('Content-Length') or 0)
            if largo <= 0:
                raise ValueError('El envío llegó vacío.')
            if largo > LIMITE_SUBIDA:
                raise ValueError('El archivo supera los 4 MB que admite el servidor. '
                                 'Procéselo desde el equipo del contador.')
            crudo = self.rfile.read(largo)

            # El testigo viaja como campo del formulario multipart; se comprueba
            # aquí porque el cuerpo no se puede leer dos veces.
            if not hmac.compare_digest(multipart.extraer_campo(crudo, '_t') or '',
                                       ses['testigo']):
                return self._error('La página caducó. Vuelva a la bandeja y '
                                   'reintente la carga.', 400)

            nombre, datos = multipart.extraer_archivo(
                crudo, self.headers.get('Content-Type'))
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
            c.anotar('declaracion_creada', ses['usuario'], rol=ses['rol'],
                     objeto=f"{calc['cliente']['nombre_titulo']} · "
                            f"AG{calc['cliente']['ano_gravable']}",
                     detalle=f"semáforo {calc['semaforo']}", ip=self._ip())
            self._ir('/caso/' + decl['id'])
        except db.ErrorPermiso as ex:
            self._html(self._bandeja(ses, str(ex)), 403)
        except db.ErrorSupabase as ex:
            self._html(self._bandeja(ses, str(ex)), 502)
        except Exception as ex:
            try:
                self._html(self._bandeja(ses, f'No se pudo procesar el archivo: {ex}'), 400)
            except Exception:
                self._error(f'No se pudo procesar el archivo: {ex}', 400)

    # ── POST del panel ──────────────────────────────────────────────
    def _post_admin(self, ses, ruta, campos):
        c = ses['cuentas']
        partes = ruta.strip('/').split('/')

        if ruta == '/admin/ajustes':
            for clave, valor in (
                    ('registro_abierto', '1' if campos.get('registro_abierto') else '0'),
                    ('requiere_aprobacion', '1' if campos.get('requiere_aprobacion') else '0'),
                    ('mensaje_portada', campos.get('mensaje_portada', '').strip()[:500])):
                c.poner_ajuste(clave, valor, por=ses['usuario'])
            try:
                cupo = max(0, min(1000, int(campos.get('cupo_por_defecto', 1) or 0)))
            except ValueError:
                cupo = 1
            c.poner_ajuste('cupo_por_defecto', cupo, por=ses['usuario'])
            return self._ir('/admin/ajustes?ok=ajustes')

        if ruta == '/admin/cuentas/nueva':
            return self._crear_cuenta(ses, campos)

        if len(partes) == 4 and partes[1] == 'cuenta':
            return self._accion_cuenta(ses, partes[2], partes[3], campos)

        self._error('Esa acción del panel no existe.', 404)

    def _crear_cuenta(self, ses, campos):
        c = ses['cuentas']
        valores = {k: campos.get(k, '').strip()
                   for k in ('usuario', 'nombre', 'correo', 'telefono', 'rol', 'cupo')}
        clave = campos.get('clave', '').strip()
        provisional = not clave
        if provisional:
            clave = mod_cuentas.clave_temporal()
        rol = valores['rol'] if valores['rol'] in mod_cuentas.ROLES else 'cliente'
        cupo = None
        if rol == 'cliente' and not campos.get('sin_limite'):
            try:
                cupo = max(0, int(valores['cupo'] or 0))
            except ValueError:
                cupo = c.ajuste_int('cupo_por_defecto', 1)
        try:
            nueva = c.crear(valores['usuario'], valores['nombre'], clave,
                            correo=valores['correo'] or None, rol=rol,
                            estado='activo' if campos.get('activa') else 'pendiente',
                            cupo=cupo, creado_por=ses['usuario'],
                            telefono=valores['telefono'] or None,
                            debe_cambiar_clave=provisional, reservado_ok=True)
        except mod_cuentas.ErrorCuenta as ex:
            return self._html(vista_admin.vista_nueva_cuenta(
                ses['usuario'], ses['testigo'], valores, str(ex)), 400)
        if provisional:
            # Se muestra sin redirigir: la contraseña no puede viajar en la URL,
            # donde quedaría en el historial y en los registros del proxy.
            datos = {'usadas': 0, 'declaraciones': []}
            return self._html(vista_admin.vista_cuenta(
                nueva, datos, ses['usuario'], ses['testigo'],
                hecho='Cuenta creada.', clave_nueva=clave))
        self._ir(f'/admin/cuenta/{nueva["id"]}?ok=creada')

    def _accion_cuenta(self, ses, id_usuario, accion, campos):
        c = ses['cuentas']
        destino = f'/admin/cuenta/{id_usuario}'
        try:
            if accion == 'estado':
                c.cambiar_estado(id_usuario, campos.get('estado', ''), por=ses['usuario'])
                if campos.get('desde') == 'lista':
                    return self._ir('/admin/cuentas?ok=estado')
                return self._ir(destino + '?ok=estado')

            if accion == 'rol':
                if str(ses['fila']['id']) == str(id_usuario):
                    raise mod_cuentas.ErrorCuenta('No puede cambiarse el rol a sí mismo.')
                c.cambiar_rol(id_usuario, campos.get('rol', ''), por=ses['usuario'])
                return self._ir(destino + '?ok=rol')

            if accion == 'cupo':
                cupo = None
                if not campos.get('sin_limite'):
                    try:
                        cupo = int(campos.get('cupo', '') or 0)
                    except ValueError:
                        raise mod_cuentas.ErrorCuenta('El cupo debe ser un número entero.')
                c.cambiar_cupo(id_usuario, cupo, por=ses['usuario'])
                return self._ir(destino + '?ok=cupo')

            if accion == 'datos':
                c.editar(id_usuario, nombre=campos.get('nombre'),
                         correo=campos.get('correo'), telefono=campos.get('telefono'),
                         notas=campos.get('notas'), por=ses['usuario'])
                return self._ir(destino + '?ok=datos')

            if accion == 'clave':
                nueva = c.restablecer_clave(id_usuario, por=ses['usuario'])
                u = c.buscar_id(id_usuario)
                datos = {'usadas': c.cuantas_lleva(u['usuario']),
                         'declaraciones': self._declaraciones(ses, de=u['usuario'])}
                return self._html(vista_admin.vista_cuenta(
                    u, datos, ses['usuario'], ses['testigo'], clave_nueva=nueva))

            if accion == 'sesiones':
                c.cerrar_sesiones(id_usuario, por=ses['usuario'])
                return self._ir(destino + '?ok=sesiones')

            if accion == 'desbloquear':
                c.desbloquear(id_usuario, por=ses['usuario'])
                return self._ir(destino + '?ok=desbloqueada')

            if accion == 'eliminar':
                if str(ses['fila']['id']) == str(id_usuario):
                    raise mod_cuentas.ErrorCuenta('No puede eliminarse a sí mismo.')
                # Nunca con sus declaraciones: borrarlas devolvería el cupo que
                # esa cuenta ya gastó. Se van a la cartera huérfanas y ahí siguen.
                c.eliminar(id_usuario, por=ses['usuario'], con_declaraciones=False)
                return self._ir('/admin/cuentas?ok=eliminada')
        except mod_cuentas.ErrorCuenta as ex:
            return self._ir(destino + '?err=' + urllib.parse.quote(str(ex)))
        self._error('Esa acción no existe.', 404)

    def log_message(self, fmt, *args):
        pass


if __name__ == '__main__':
    # Arranca en el equipo el MISMO código que corre publicado, contra la misma
    # base. Sirve para probar el panel sin desplegar. La cookie se emite sin la
    # marca Secure al ver que el anfitrión es local; en Vercel siempre la lleva.
    from http.server import ThreadingHTTPServer

    puerto = int(env('PUERTO') or 8766)
    faltan = hay_configuracion()
    if faltan:
        print('Falta configurar: ' + ', '.join(faltan))
        sys.exit(1)
    servidor = ThreadingHTTPServer(('127.0.0.1', puerto), handler)
    servidor.daemon_threads = True
    print(f'RENTA IA (versión publicada) → http://localhost:{puerto}')
    print('Ctrl+C para detener.')
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print('\nDetenido.')
