# -*- coding: utf-8 -*-
r"""RENTA IA en Vercel — la bandeja y el panel, sobre funciones sin estado.

Diferencias con la versión de escritorio, todas por el entorno:

  · No hay disco persistente. El caso se procesa en memoria y se guarda en
    Supabase (tablas + buckets privados); el .xlsx recibido solo pasa por /tmp,
    que es efímero.
  · Todo pide usuario y contraseña. Aquí viajan declaraciones de personas
    reales, sujetas a la reserva del art. 583 E.T.
  · Cada quien ve lo suyo, y el administrador tampoco: sin permiso concedido
    por el dueño, no ve ni una declaración ajena.

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
import borradores as mod_borradores
import calculos
import clasificador
import config
import cuentas as mod_cuentas
import db
import generar
import legal
import login
import multipart
import nube
import perfil as mod_perfil
import permisos as mod_permisos
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
NO_HAY_RST = ('El apartado del Régimen Simple todavía no está habilitado para esta '
              'cuenta. Escriba al administrador si necesita acceso.')
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
    'clave': 'Contraseña cambiada.',
    'permiso_dado': ('Acceso concedido. Vence solo, y puede retirarse antes '
                     'desde «Mi cuenta».'),
    'permiso_negado': ('Solicitud rechazada. Nadie más entra a estas '
                       'declaraciones.'),
    'permiso_revocado': 'Acceso retirado. Surtió efecto de inmediato.',
    'carga_cancelada': ('Carga descartada. No se creó ninguna declaración y no se '
                        'consumió cupo.'),
    'permiso_pedido': ('Solicitud enviada. Solo el titular puede concederla, '
                       'y la ve al entrar.'),
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
            return self._expulsar('Su cuenta ya no tiene acceso. Consulte con el administrador.')
        nacida = mod_cuentas.desde_iso(fila.get('sesiones_desde'))
        # La holgura de cinco segundos absorbe el desfase entre el reloj de la
        # base y el del servidor web. Sin ella, cerrar sesiones o cambiar la
        # contraseña podría invalidar la cookie que se acaba de emitir.
        if nacida and emitida < nacida.timestamp() - 5:
            return self._expulsar('Su sesión se cerró. Vuelva a entrar.')

        # A quién ve. La regla es una sola y no tiene excepción por rol: **lo
        # suyo, y la cartera de quien le haya concedido permiso vigente**. El
        # administrador maneja cuentas y cupos, pero las declaraciones de sus
        # usuarios son datos tributarios de terceros y no los ve por ser el
        # dueño de la plataforma. Se recalcula en cada petición, igual que ya se
        # relee la cuenta: así revocar un permiso surte efecto en el acto.
        p = mod_permisos.Permisos(c.s)
        try:
            prestadas = p.vigentes_para(fila['usuario'])
        except db.ErrorSupabase:
            prestadas = []          # si la tabla no responde, ve solo lo suyo
        ses = {'usuario': fila['usuario'], 'rol': fila['rol'], 'fila': fila,
               'cuentas': c, 's': c.s, 'emitida': emitida,
               'testigo': testigo(fila['usuario'], emitida),
               'es_admin': fila['rol'] == 'admin',
               'permisos': p,
               'prestadas': prestadas,
               'solo_de': [fila['usuario']] + prestadas,
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
                return self._html(self._bandeja(
                    ses, hecho=AVISOS.get(self._consulta().get('ok', ''), '')))
            if ruta == '/cuenta':
                return self._get_mi_cuenta(ses)
            if ruta.startswith('/confirmar/'):
                partes = ruta.split('/')
                if len(partes) > 3 and partes[3] == 'cancelar':
                    return self._cancelar_confirmar(ses, partes[2])
                return self._get_confirmar(ses, partes[2])
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
                'Escriba al administrador para pedir acceso.', code=200)
        self._html(login.pagina_registro(
            min_clave=mod_cuentas.MIN_CLAVE,
            aprobacion=c.ajuste_bool('requiere_aprobacion', False)))

    def _get_mi_cuenta(self, ses):
        c = ses['cuentas']
        datos = {'usadas': c.cuantas_lleva(ses['usuario']),
                 'accesos': ses['permisos'].concedidos_de(ses['usuario']),
                 'movimientos': c.bitacora(limite=15, usuario=ses['usuario'])}
        aviso = AVISOS.get(self._consulta().get('ok', ''), '')
        self._html(vista_admin.vista_mi_cuenta(ses['fila'], datos, ses['testigo'],
                                               hecho=aviso))

    def _get_caso(self, ses, ref):
        caso = nube.buscar(ref, ses['s'], solo_de=ses['solo_de'])
        if not caso:
            return self._error('Ese caso no existe o no pertenece a esta cuenta.', 404)
        if 'error' in caso:
            return self._error(caso['error'])
        acciones = self._acciones_caso(ses, caso)
        self._html(render.vista_caso(caso, clasificador.tolerancia,
                                     usuario=ses['usuario'], pie=render.PIE_NUBE,
                                     mostrar_estado=True, nav=self._nav(ses),
                                     rol=vista_admin.ROL_NOMBRE.get(ses['rol'], ''),
                                     acciones=acciones, token=ses['testigo'],
                                     puede_marcar=True,
                                     estilo_extra=vista_admin.ESTILO))

    @staticmethod
    def _altas_abiertas(caso):
        """Alertas ALTA que nadie ha dado por resueltas."""
        return [a for a in (caso.get('alertas') or [])
                if isinstance(a, dict) and a.get('severidad') == 'ALTA'
                and not a.get('resuelta')]

    def _acciones_caso(self, ses, caso):
        """Los botones del pie del caso: mover el estado de la revisión.

        Los ve quien ve el caso. Ya no hay un rol «que revisa» distinto del que
        trabaja: quien usa el sistema es el contador, y libera lo suyo.
        """
        abiertas = self._altas_abiertas(caso)
        botones = []
        for valor, texto in (('borrador', 'Devolver a borrador'),
                             ('en_revision', 'Marcar en revisión'),
                             ('liberada', 'Liberar')):
            if valor == caso.get('estado'):
                continue
            if valor == 'liberada' and abiertas:
                # No se oculta el botón: se deshabilita y se dice por qué.
                # Ocultarlo dejaría al usuario buscando qué hizo mal.
                botones.append(
                    f'<button class="mini sec" type="button" disabled '
                    f'title="Resuelva primero las {len(abiertas)} alerta(s) ALTA">'
                    f'{e(texto)}</button>')
                continue
            botones.append(
                f'<form method="post" action="/caso/{e(caso["ref"])}/estado">'
                f'<input type="hidden" name="_t" value="{e(ses["testigo"])}">'
                f'<input type="hidden" name="estado" value="{valor}">'
                f'<button class="mini sec" type="submit">{e(texto)}</button></form>')
        traba = ''
        if abiertas:
            traba = (f'<p style="margin-top:12px;color:{render.ROJO}"><b>No se puede '
                     f'liberar todavía:</b> quedan {len(abiertas)} alerta(s) de '
                     f'severidad ALTA sin resolver. Se marcan arriba, una por una, '
                     f'anotando cómo se resolvieron; o se corrige lo que haga falta '
                     f'y se vuelve a cargar el archivo.</p>')
        # Una declaración no se elimina desde ninguna parte. El cupo es lo que
        # se vende: si borrar devolviera el cupo, una cuenta de cupo 1 podría
        # procesar sin límite subiendo, borrando y volviendo a subir.
        return ('<div class="seccion" style="margin-top:22px"><h2>Revisión</h2>'
                '<div class="cuerpo"><p>Liberar deja constancia de que el caso quedó '
                'revisado y se da por bueno. Es una marca de trabajo, no un envío '
                'a la DIAN.</p><div class="acc-fila" style="justify-content:flex-start">'
                + ''.join(botones) + '</div>' + traba + '</div></div>')

    def _get_libro(self, ses, ref):
        caso = nube.buscar(ref, ses['s'], solo_de=ses['solo_de'])
        if not caso or not caso.get('libro_path'):
            return self._error('Ese libro no existe o no pertenece a esta cuenta.', 404)
        # En la bitácora NO va el nombre del contribuyente: la lee el
        # administrador, y él no tiene por qué saber a quién le llevan la
        # contabilidad sus usuarios. La referencia del caso basta para auditar.
        ses['cuentas'].anotar('libro_descargado', ses['usuario'], rol=ses['rol'],
                              objeto=f"declaración {ref}", ip=self._ip())
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
            return self._ir('/admin/uso')      # se llamaba así antes

        if ruta == '/admin/uso':
            renta, rst = self._uso_por_cuenta(ses)
            return self._html(vista_admin.vista_uso(
                c.listar(), renta, rst, ses['permisos'].vigentes_para(ses['usuario']),
                ses['usuario'], ses['testigo'], err, ok))

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
            # De la cartera de esta cuenta se le dice al administrador cuántos
            # casos lleva, y nada más. Para entrar tiene que pedir permiso.
            datos = {'usadas': c.cuantas_lleva(u['usuario']),
                     'permiso': ses['permisos'].entre(u['usuario'], ses['usuario'])}
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

    def _uso_por_cuenta(self, ses):
        """Cuántos casos lleva cada cuenta. Ni un dato del contribuyente.

        Es **todo** lo que el administrador puede saber de la cartera ajena: el
        número. Ni el nombre, ni la cédula, ni el año, ni el semáforo, ni las
        cifras. Para ver una declaración tiene que pedirle permiso a su dueño.
        Se piden solo las columnas `creada_por` a propósito: lo que no se trae
        no se puede filtrar mal más adelante.
        """
        renta, rst = {}, {}
        for d in ses['s'].seleccionar('declaraciones', select='creada_por'):
            renta[d['creada_por']] = renta.get(d['creada_por'], 0) + 1
        try:
            for r in ses['s'].seleccionar('recibos_rst', select='creada_por'):
                rst[r['creada_por']] = rst.get(r['creada_por'], 0) + 1
        except db.ErrorSupabase:
            pass                          # base todavía sin el módulo RST
        return renta, rst

    def _bandeja(self, ses, error='', hecho=''):
        c = ses['cuentas']
        lista = nube.listar(ses['s'], solo_de=ses['solo_de'])
        cupo = c.cupo_de(ses['fila'])
        # El filtro viaja en la dirección: así el enlace de una cifra del
        # encabezado se puede compartir, marcar y recargar sin perderlo.
        consulta = self._consulta()
        sem = consulta.get('sem', '')
        sem = sem if sem in ('VERDE', 'AMARILLO', 'ROJO') else ''
        estado = consulta.get('estado', '')
        estado = estado if estado in ('borrador', 'en_revision', 'liberada') else ''
        orden = consulta.get('orden', 'nombre')
        orden = orden if orden in dict(render.ORDENES) else 'nombre'
        if ses['prestadas']:
            quienes = ', '.join(ses['prestadas'])
            sub = ('CARTERA PROPIA &nbsp;&middot;&nbsp; Y LA DE ' +
                   e(quienes.upper()) + ', CON PERMISO VIGENTE')
        else:
            sub = ('CARTERA PROPIA &nbsp;&middot;&nbsp; NADIE MÁS VE ESTAS '
                   'DECLARACIONES SIN PERMISO DEL TITULAR')
        return render.vista_bandeja(
            lista, error=error, hecho=hecho, usuario=ses['usuario'], cupo=cupo,
            pie=render.PIE_NUBE, mostrar_estado=True, sub=sub, nav=self._nav(ses),
            rol=vista_admin.ROL_NOMBRE.get(ses['rol'], ''), token=ses['testigo'],
            aviso=c.ajuste('mensaje_portada', '') or '',
            solicitudes=self._solicitudes_html(ses),
            sem=sem, estado=estado, orden=orden)

    def _solicitudes_html(self, ses):
        """La franja de «alguien pide entrar a sus declaraciones».

        Sale arriba de la bandeja, sin poder ignorarse, porque es una decisión
        sobre datos de terceros que solo el dueño puede tomar. Las duraciones
        son cortas a propósito: un acceso a declaraciones ajenas no debería
        concederse «para siempre» y olvidarse.
        """
        try:
            pendientes = ses['permisos'].pendientes_de(ses['usuario'])
        except db.ErrorSupabase:
            return ''
        if not pendientes:
            return ''
        bloques = []
        for p in pendientes:
            quien = ses['cuentas'].buscar(p['solicitante'])
            nombre = (quien or {}).get('nombre') or p['solicitante']
            motivo = (p.get('motivo') or '').strip()
            botones = ''.join(
                f'<button class="mini sec" type="submit" name="dias" value="{d}">'
                f'{e(et)}</button>'
                for d, et in mod_permisos.DURACIONES)
            bloques.append(f"""<div class="peticion">
  <div class="peticion-txt">
    <b>{e(nombre)}</b> (<span class="mono-t">{e(p['solicitante'])}</span>)
    pide entrar a estas declaraciones.
    {('<br><i>«' + e(motivo) + '»</i>') if motivo else
     '<br><span class="pista">No escribió un motivo.</span>'}
  </div>
  <form method="post" action="/permiso/{e(p['solicitante'])}/conceder" class="peticion-acc">
    <input type="hidden" name="_t" value="{e(ses['testigo'])}">
    <span class="pista">Dar acceso por:</span>{botones}
  </form>
  <form method="post" action="/permiso/{e(p['solicitante'])}/denegar">
    <input type="hidden" name="_t" value="{e(ses['testigo'])}">
    <button class="mini peligro" type="submit">No dar acceso</button>
  </form>
</div>""")
        return ('<div class="peticiones"><h2>Alguien pide ver estas declaraciones'
                '</h2><p class="pista">Mientras no se conceda, nadie más las ve. '
                'El acceso se puede retirar en cualquier momento desde '
                '<a href="/cuenta">Mi cuenta</a>.</p>'
                + ''.join(bloques) + '</div>')

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
            return self._error('Ese recibo no existe o no pertenece a esta cuenta.', 404)
        self._html(rst_vista.vista_recibo(
            caso, usuario=ses['usuario'], pie=render.PIE_NUBE, mostrar_estado=True,
            nav=self._nav(ses, 'rst'),
            rol=vista_admin.ROL_NOMBRE.get(ses['rol'], ''),
            acciones=self._acciones_rst(ses, caso),
            estilo_extra=vista_admin.ESTILO + rst_vista.ESTILO))

    def _acciones_rst(self, ses, caso):
        """Los botones del pie del recibo. Los ve quien ve el recibo."""
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
        bloques = [('<div class="seccion" style="margin-top:22px"><h2>Revisión</h2>'
                    '<div class="cuerpo"><p>Liberar deja constancia de que el recibo '
                    'quedó revisado y se da por bueno. Es una marca de trabajo, no una '
                    'presentación ante la DIAN.</p>'
                    '<div class="acc-fila" style="justify-content:flex-start">'
                    + ''.join(botones) + '</div></div></div>')]
        if caso.get('estado') == 'borrador' and caso.get('creada_por') == ses['usuario']:
            bloques.append(
                f'<div class="seccion" style="margin-top:22px">'
                f'<h2>Eliminar este recibo</h2><div class="cuerpo">'
                f'<p>Un recibo en borrador se puede eliminar. Se borran su libro y el '
                f'consolidado que lo originó, y el cupo se recupera.</p>'
                f'<form method="get" action="/rst/{e(caso["ref"])}/eliminar">'
                f'<button class="mini peligro" type="submit">Eliminar este recibo'
                f'</button></form></div></div>')
        return ''.join(bloques)

    def _get_libro_rst(self, ses, ref):
        caso = rst_nube.buscar(ses['s'], ref, solo_de=ses['solo_de'])
        if not caso or not caso['fila'].get('libro_path'):
            return self._error('Ese libro no existe o no pertenece a esta cuenta.', 404)
        # En la bitácora NO va el nombre del contribuyente: la lee el
        # administrador, y él no tiene por qué saber a quién le llevan la
        # contabilidad sus usuarios. La referencia basta para auditar.
        ses['cuentas'].anotar('libro_rst_descargado', ses['usuario'], rol=ses['rol'],
                              objeto=f"recibo {ref}", ip=self._ip())
        url = ses['s'].url_firmada(db.BUCKET_LIBROS, caso['fila']['libro_path'], 120)
        self.send_response(302)
        self.send_header('Location', url)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()

    def _eliminar_rst(self, ses, ref):
        caso = rst_nube.buscar(ses['s'], ref, solo_de=ses['solo_de'])
        if not caso:
            return self._error('Ese recibo no existe o no pertenece a esta cuenta.', 404)
        if (caso.get('estado') != 'borrador'
                or caso.get('creada_por') != ses['usuario']):
            return self._error('Solo se eliminan recibos propios que sigan en '
                               'borrador.', 403)
        rst_nube.eliminar(ses['s'], ref)
        ses['cuentas'].anotar('recibo_rst_eliminado', ses['usuario'], rol=ses['rol'],
                              objeto=f"recibo {ref}", ip=self._ip())
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
                             f'Para ampliarlo, escriba al administrador.'), 403)

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

            # El descargo se comprueba aquí, en el servidor, y no ocultando el
            # botón: es la diferencia entre una cortesía y una condición.
            if not multipart.extraer_campo(crudo, legal.NOMBRE_CAMPO):
                return self._html(self._bandeja_rst(ses, legal.NO_ACEPTADO), 400)

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
                creada_por=ses['usuario'])
            c.anotar('recibo_rst_creado', ses['usuario'], rol=ses['rol'],
                     objeto=f"recibo {recibo['id']}",
                     detalle=f"semáforo {liq['semaforo']}", ip=self._ip())
            c.anotar('descargo_aceptado', ses['usuario'], rol=ses['rol'],
                     objeto=f"recibo {recibo['id']}",
                     detalle='aceptó revisar antes de presentar', ip=self._ip())
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
            if ruta.startswith('/confirmar/'):
                return self._post_confirmar(ses, ruta.split('/')[2], campos)
            if ruta.startswith('/permiso/'):
                return self._post_permiso(ses, ruta.split('/'), campos)
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
            # Las cuentas que quedaron con el rol «contador», que ya no existe,
            # pasan a «cliente» conservando su cupo. También una sola vez.
            c.migrar_rol_contador()
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
                 'accesos': ses['permisos'].concedidos_de(ses['usuario']),
                 'movimientos': c.bitacora(limite=15, usuario=ses['usuario'])}
        return vista_admin.vista_mi_cuenta(ses['fila'], datos, ses['testigo'], error)

    def _post_permiso(self, ses, partes, campos):
        """POST /permiso/<otro>/<conceder|denegar|revocar>.

        Siempre lo ejecuta **el dueño de las declaraciones** sobre su propia
        cartera: `ses['usuario']` es quien decide y el de la URL es el que pide.
        Un administrador no puede llamar a esto para concederse acceso a sí
        mismo — la fila que se toca es la de (dueño=quien pide la página).
        """
        otro = mod_cuentas.normalizar(urllib.parse.unquote(partes[2] if len(partes) > 2 else ''))
        accion = partes[3] if len(partes) > 3 else ''
        p = ses['permisos']
        try:
            if accion == 'conceder':
                dias = int((campos or {}).get('dias') or 0)
                p.conceder(ses['usuario'], otro, dias=dias, por=ses['usuario'],
                           ip=self._ip())
                destino = '/?ok=permiso_dado'
            elif accion == 'denegar':
                p.denegar(ses['usuario'], otro, por=ses['usuario'], ip=self._ip())
                destino = '/?ok=permiso_negado'
            elif accion == 'revocar':
                p.revocar(ses['usuario'], otro, por=ses['usuario'], ip=self._ip())
                destino = '/cuenta?ok=permiso_revocado'
            else:
                return self._error('Esa acción no existe.', 404)
        except mod_permisos.ErrorPermiso as ex:
            return self._error(str(ex), 400)
        self._ir(destino)

    # ── carga en dos pasos ──────────────────────────────────────────
    def _previa_de(self, ses, C):
        """Si ESTA cuenta ya cargó ese (contribuyente, año), cuándo. Si no, None.

        Sirve para avisar de que se va a reemplazar y —lo importante— para no
        cobrar cupo por reprocesar algo que ya está: se actualiza la fila que
        hay, no se crea otra, así que no hay nada que cobrar.

        **Solo mira lo de esta cuenta, y es a propósito.** Cada cuenta tiene su
        propia copia del caso: que otra persona haya trabajado el mismo
        contribuyente y el mismo año no la afecta en nada, no le impide cargar
        el suyo y —sobre todo— no se le dice, porque no es asunto suyo. Ni
        siquiera la cartera prestada cuenta aquí: esa es otra fila, de otro
        dueño, y reprocesar no la toca.
        """
        ident = str(C.get('identificacion', '')).replace('.', '').strip()
        if not ident:
            return None
        personas = ses['s'].seleccionar('contribuyentes', select='id',
                                        identificacion='eq.' + ident)
        if not personas:
            return None
        filas = ses['s'].seleccionar(
            'declaraciones', select='id,creado_en',
            contribuyente_id='eq.' + personas[0]['id'],
            ano_gravable='eq.' + str(C.get('ano_gravable', '')),
            creada_por='eq.' + ses['usuario'])
        if not filas:
            return None
        return mod_cuentas.fecha_corta(filas[0].get('creado_en'))

    def _get_confirmar(self, ses, ref, error='', valores=None):
        b = mod_borradores.Borradores(ses['s'])
        fila = b.buscar(ref, ses['usuario'])
        if not fila:
            return self._html(self._bandeja(
                ses, 'Esa carga ya no está disponible: se canceló o pasaron las dos '
                     'horas que dura sin confirmar. Vuelva a subir el archivo — no '
                     'se consumió cupo.'), 404)
        C, T = fila['cliente'], fila['textos']
        calc = calculos.calcular_dict(C, T)
        self._html(render.vista_confirmar(
            ref, C, calc, previa=self._previa_de(ses, C),
            cupo=ses['cuentas'].cupo_de(ses['fila']), token=ses['testigo'],
            usuario=ses['usuario'], pie=render.PIE_NUBE, nav=self._nav(ses),
            rol=vista_admin.ROL_NOMBRE.get(ses['rol'], ''), error=error,
            valores=valores), 200 if not error else 400)

    def _cancelar_confirmar(self, ses, ref):
        b = mod_borradores.Borradores(ses['s'])
        b.borrar(b.buscar(ref, ses['usuario']))
        self._ir('/?ok=carga_cancelada')

    def _post_confirmar(self, ses, ref, campos):
        """Paso 2 de 2: aquí sí se crea la declaración y se cuenta el cupo."""
        s, c = ses['s'], ses['cuentas']
        b = mod_borradores.Borradores(s)
        fila = b.buscar(ref, ses['usuario'])
        if not fila:
            return self._html(self._bandeja(
                ses, 'Esa carga ya no está disponible: se canceló o venció. Vuelva '
                     'a subir el archivo — no se consumió cupo.'), 404)

        C, T = fila['cliente'], fila['textos']
        # El descargo, antes que nada y en el servidor. Sin él no se genera.
        if not legal.aceptado(campos):
            return self._get_confirmar(ses, ref, legal.NO_ACEPTADO, campos)

        previa = self._previa_de(ses, C)
        # El cupo solo se mira si esto crea una declaración nueva. Reemplazar
        # una suya no crea fila, así que no puede consumir lo que no gasta —y
        # es lo que destraba a quien subió el archivo equivocado.
        if ses['cupo'] is not None and not previa:
            usadas = c.cuantas_lleva(ses['usuario'])
            if usadas >= ses['cupo']:
                return self._html(self._bandeja(
                    ses, f'Su cupo está completo: {usadas} de {ses["cupo"]} '
                         f'declaraciones. Para ampliarlo, escriba al administrador.'), 403)

        C['perfil'] = mod_perfil.desde_formulario(campos)
        # Lo que quedó sin responder no tumba el caso —el semáforo mide si la
        # clasificación cuadra, no si el contribuyente contestó el teléfono—
        # pero sí queda escrito en la hoja de alertas y en la ficha del caso.
        falta = mod_perfil.alerta(C['perfil'],
                                  codigo='P%d' % (len(C.get('alertas') or []) + 1))
        if falta:
            C['alertas'] = list(C.get('alertas') or []) + [falta]
        try:
            calc = calculos.calcular_dict(C, T)
            decl = s.guardar_caso(calc, creada_por=ses['usuario'],
                                  libro_bytes=generar.a_bytes(C, T),
                                  nombre_libro=generar.nombre_libro(C),
                                  exogena_bytes=b.exogena(fila),
                                  nombre_exogena=fila.get('nombre_exogena'))
        except db.ErrorPermiso as ex:
            return self._html(self._bandeja(ses, str(ex)), 403)
        b.borrar(fila)
        c.anotar('declaracion_creada', ses['usuario'], rol=ses['rol'],
                 objeto=f"declaración {decl['id']}",
                 detalle=f"semáforo {calc['semaforo']}"
                         + (' · reemplaza la anterior' if previa else ''),
                 ip=self._ip())
        # La aceptación del descargo se anota aparte y con su propio nombre:
        # es lo que convierte el aviso en un respaldo con fecha y usuario.
        c.anotar('descargo_aceptado', ses['usuario'], rol=ses['rol'],
                 objeto=f"declaración {decl['id']}",
                 detalle='aceptó revisar antes de presentar', ip=self._ip())
        self._ir('/caso/' + decl['id'])

    def _post_caso(self, ses, partes, campos):
        ref = partes[2]
        accion = partes[3] if len(partes) > 3 else ''
        caso = nube.buscar(ref, ses['s'], solo_de=ses['solo_de'])
        if not caso:
            return self._error('Ese caso no existe o no pertenece a esta cuenta.', 404)

        if accion == 'estado':
            # Quien ve el caso lo mueve: ya no hay un rol «que revisa» aparte
            # del que trabaja. `nube.buscar` con `solo_de` ya negó el acceso a
            # quien no debía llegar hasta aquí.
            estado = campos.get('estado', '')
            # Liberar con alertas ALTA abiertas se niega en el SERVIDOR, no
            # solo deshabilitando el botón: quien arme el POST a mano tampoco.
            abiertas = self._altas_abiertas(caso)
            if estado == 'liberada' and abiertas:
                return self._error(
                    f'No se puede liberar: quedan {len(abiertas)} alerta(s) de '
                    f'severidad ALTA sin resolver. Se marcan como resueltas en la '
                    f'ficha del caso, anotando cómo se resolvieron.', 400)
            ses['s'].cambiar_estado(ref, estado, por=ses['usuario'])
            ses['cuentas'].anotar('declaracion_estado', ses['usuario'], rol=ses['rol'],
                                  objeto=f"declaración {ref}",
                                  detalle=f'→ {estado}', ip=self._ip())
            return self._ir(f'/caso/{ref}')

        if accion == 'alerta':
            # La alerta tiene que ser de ESTE caso. Sin comprobarlo, el id de
            # una alerta cualquiera permitiría tocar la de un caso ajeno con
            # solo cambiar el número en el formulario.
            id_alerta = str(campos.get('alerta', ''))
            propias = {str(a['id']) for a in ses['s'].alertas_de(ref)}
            if id_alerta not in propias:
                return self._error('Esa alerta no es de este caso.', 400)
            resuelta = campos.get('resuelta') == '1'
            ses['s'].marcar_alerta(id_alerta, resuelta,
                                   nota=campos.get('nota', ''), por=ses['usuario'])
            ses['cuentas'].anotar(
                'alerta_resuelta' if resuelta else 'alerta_reabierta',
                ses['usuario'], rol=ses['rol'], objeto=f'declaración {ref}',
                detalle=f'alerta {id_alerta}', ip=self._ip())
            return self._ir(f'/caso/{ref}#alertas')

        if accion == 'eliminar':
            return self._error('Las declaraciones de renta no se eliminan: una vez '
                               'procesada, la declaración y el cupo que consumió '
                               'quedan.', 403)
        self._error('Esa acción no existe.', 404)

    def _post_subir(self, ses):
        """Paso 1 de 2: lee y clasifica la exógena. **No crea nada todavía.**

        Aquí no se toca el cupo ni se guarda declaración: el resultado queda en
        un borrador que vence en dos horas y el usuario decide en la pantalla
        siguiente. Equivocarse de archivo dejó de costar un cupo.

        **El cupo no se comprueba aquí, y es a propósito.** Hasta no leer el
        archivo no se sabe de quién es ni de qué año, así que tampoco se sabe si
        va a crear una declaración nueva —que cuesta cupo— o a reemplazar una
        suya —que no—. Negar la carga por adelantado dejaría atascado justo al
        que subió el archivo equivocado, que es a quien esto viene a destrabar.
        La comprobación va en el paso 2, cuando ya se sabe cuál de las dos es.
        """
        s, c = ses['s'], ses['cuentas']
        try:
            largo = int(self.headers.get('Content-Length') or 0)
            if largo <= 0:
                raise ValueError('El envío llegó vacío.')
            if largo > LIMITE_SUBIDA:
                raise ValueError('El archivo supera los 4 MB que admite el servidor. '
                                 'Procéselo desde el programa instalado en el equipo '
                                 'del contador, que no tiene ese tope.')
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
                    f'«{nombre}» no es un .xlsx. Si el reporte está en el formato '
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

            # El libro NO se arma aquí: se armará al confirmar, ya con las
            # respuestas del perfil dentro. Armarlo dos veces sería tirar dos
            # segundos de función por cada carga que se cancela.
            borrador = mod_borradores.Borradores(s).crear(
                ses['usuario'], res['cliente'], res['textos'],
                exogena_bytes=datos, nombre_exogena=nombre)
            self._ir('/confirmar/' + borrador['id'])
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
            datos = {'usadas': 0, 'permiso': None}
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

            if accion == 'permiso':
                # El administrador PIDE; no se concede nada aquí. Conceder es
                # del dueño y solo del dueño, desde su propia bandeja.
                otra = c.buscar_id(id_usuario)
                if not otra:
                    raise mod_cuentas.ErrorCuenta('Esa cuenta ya no existe.')
                try:
                    ses['permisos'].pedir(otra['usuario'], ses['usuario'],
                                          motivo=campos.get('motivo', ''),
                                          por=ses['usuario'], ip=self._ip())
                except mod_permisos.ErrorPermiso as ex:
                    return self._ir(destino + '?err=' + urllib.parse.quote(str(ex)))
                return self._ir(destino + '?ok=permiso_pedido')

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
                         'permiso': ses['permisos'].entre(u['usuario'], ses['usuario'])}
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
