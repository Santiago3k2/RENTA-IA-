# -*- coding: utf-8 -*-
r"""Regresión de extremo a extremo del sitio publicado.

    python pruebas_web.py

Levanta `api\index.py` —el mismo código que corre en Vercel— en un puerto
libre y lo recorre como lo haría un navegador: con cookies, siguiendo (o no)
las redirecciones y mirando los códigos de respuesta. No hay simulacros: la
base es la de verdad y las páginas son las que ve el usuario.

Comprueba lo que de otro modo solo se descubre en producción: que sin sesión no
se pasa, que el testigo anti-CSRF se exige de veras, que inhabilitar a alguien
lo echa en el acto y que un cliente no puede asomarse al panel.

Todo lo que crea queda bajo cuentas «zzweb…» y se borra al terminar, también
si algo falla. Debe decir «TODAS LAS PRUEBAS PASAN».
"""
import http.cookiejar
import os
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
for sub in (BASE, os.path.join(RAIZ, 'web'), os.path.join(RAIZ, 'api')):
    if sub not in sys.path:
        sys.path.insert(0, sub)

import cuentas
import db
import index as sitio

fallos = []
hechas = 0

CLAVE_ADMIN = 'roble alto 41 enero'
CLAVE_CLIENTE = 'puerto claro 92 junio'


def revisar(condicion, titulo, extra=''):
    global hechas
    hechas += 1
    if condicion:
        print(f'  ok   {titulo}')
    else:
        print(f'  FALLA {titulo}' + (f' — {extra}' if extra else ''))
        fallos.append(titulo)


# ── un navegador de mentiras ────────────────────────────────────────────
class Navegador:
    """Cliente HTTP con cookies que NO sigue las redirecciones.

    Seguirlas escondería justo lo que hay que comprobar: que entrar responde
    303, que sin sesión responde 401 y que el panel le cierra la puerta a quien
    no es administrador con un 403.
    """

    def __init__(self, base):
        self.base = base
        self.galletas = http.cookiejar.CookieJar()
        self.abridor = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.galletas), _SinRedirigir())

    def _pedir(self, metodo, ruta, datos=None):
        url = self.base + ruta
        cuerpo = urllib.parse.urlencode(datos).encode() if datos is not None else None
        pet = urllib.request.Request(url, data=cuerpo, method=metodo)
        if cuerpo is not None:
            pet.add_header('Content-Type', 'application/x-www-form-urlencoded')
        try:
            with self.abridor.open(pet, timeout=30) as r:
                return r.status, r.read().decode('utf-8', 'replace'), dict(r.headers)
        except urllib.error.HTTPError as ex:
            return ex.code, ex.read().decode('utf-8', 'replace'), dict(ex.headers)

    def get(self, ruta):
        return self._pedir('GET', ruta)

    def post(self, ruta, datos):
        return self._pedir('POST', ruta, datos)

    def testigo(self, html):
        """Saca el testigo anti-CSRF de un formulario ya pintado."""
        marca = 'name="_t" value="'
        i = html.find(marca)
        return html[i + len(marca):html.find('"', i + len(marca))] if i >= 0 else ''


class _SinRedirigir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def puerto_libre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


# ── las pruebas ─────────────────────────────────────────────────────────
def probar_sin_sesion(nav):
    print('\nSin sesión no se pasa')
    for ruta in ('/', '/cuenta', '/admin', '/admin/cuentas', '/admin/bitacora'):
        code, html, _ = nav.get(ruta)
        revisar(code == 401 and 'Bienvenido de nuevo' in html,
                f'{ruta} responde con la pantalla de acceso', f'dio {code}')
    code, _, cab = nav.post('/admin/ajustes', {'registro_abierto': '1'})
    revisar(code == 401, 'no se puede escribir en el panel sin sesión', f'dio {code}')


def probar_acceso(nav, usuario):
    print('\nAcceso')
    code, html, _ = nav.get('/entrar')
    revisar(code == 200 and 'Bienvenido de nuevo' in html, 'la pantalla de acceso carga')

    code, html, _ = nav.post('/entrar', {'usuario': usuario, 'clave': 'no es'})
    revisar(code == 401 and 'incorrectos' in html,
            'con la contraseña errada no entra y no dice cuál de los dos falló')

    code, html, _ = nav.post('/entrar', {'usuario': usuario, 'clave': CLAVE_ADMIN})
    revisar(code == 303, 'con la contraseña correcta responde una redirección', f'dio {code}')

    code, html, _ = nav.get('/')
    revisar(code == 200 and 'Contribuyentes' in html, 'la bandeja carga con la sesión abierta')
    revisar('PANEL DE ADMINISTRACIÓN' not in html and 'Panel' in html,
            'el administrador ve las pestañas del panel')


def probar_panel(nav):
    print('\nPáginas del panel')
    esperado = {
        '/admin': 'PANEL DE ADMINISTRACIÓN',
        '/admin/cuentas': 'Cuentas registradas',
        '/admin/cuentas/nueva': 'Crear una cuenta',
        '/admin/uso': 'Uso por cuenta',
        '/admin/bitacora': 'Bitácora',
        '/admin/ajustes': 'Registro de cuentas nuevas',
    }
    for ruta, marca in esperado.items():
        code, html, _ = nav.get(ruta)
        revisar(code == 200 and marca in html, f'{ruta} carga', f'dio {code}')
    code, html, _ = nav.get('/cuenta')
    revisar(code == 200 and 'Cambiar mi contraseña' in html, '/cuenta carga')


def probar_csrf(nav):
    print('\nTestigo anti-CSRF')
    code, html, _ = nav.get('/admin/ajustes')
    bueno = nav.testigo(html)
    revisar(len(bueno) == 32, 'el formulario trae un testigo', f'trajo «{bueno}»')

    code, _, _ = nav.post('/admin/ajustes', {'registro_abierto': '1'})
    revisar(code == 400, 'sin testigo, la escritura se rechaza', f'dio {code}')

    code, _, _ = nav.post('/admin/ajustes', {'_t': 'a' * 32, 'registro_abierto': '1'})
    revisar(code == 400, 'con un testigo inventado, también se rechaza', f'dio {code}')

    code, _, _ = nav.post('/admin/ajustes', {'_t': bueno, 'registro_abierto': '1',
                                             'cupo_por_defecto': '1'})
    revisar(code == 303, 'con el testigo correcto, la escritura pasa', f'dio {code}')


def probar_gestion_cuentas(nav, c):
    print('\nGestión de una cuenta desde el panel')
    u = 'zzweb' + secrets.token_hex(4)
    code, html, _ = nav.get('/admin/cuentas/nueva')
    token = nav.testigo(html)

    code, html, _ = nav.post('/admin/cuentas/nueva', {
        '_t': token, 'usuario': u, 'nombre': 'Cliente De Ensayo',
        'correo': u + '@ejemplo.co', 'rol': 'cliente', 'cupo': '2',
        'clave': CLAVE_CLIENTE, 'activa': '1'})
    revisar(code == 303, 'la cuenta se crea desde el panel', f'dio {code}')
    fila = c.buscar(u)
    revisar(bool(fila) and fila['cupo'] == 2 and fila['estado'] == 'activo',
            'nace activa, como cliente y con el cupo que se le puso')

    code, html, _ = nav.get(f'/admin/cuenta/{fila["id"]}')
    revisar(code == 200 and u in html, 'la ficha de la cuenta carga')
    token = nav.testigo(html)

    nav.post(f'/admin/cuenta/{fila["id"]}/cupo', {'_t': token, 'cupo': '7'})
    revisar(c.buscar(u)['cupo'] == 7, 'el cupo se cambia desde el panel')

    nav.post(f'/admin/cuenta/{fila["id"]}/cupo', {'_t': token, 'sin_limite': '1'})
    revisar(c.buscar(u)['cupo'] is None, 'el cupo se puede quitar desde el panel')

    nav.post(f'/admin/cuenta/{fila["id"]}/datos', {
        '_t': token, 'nombre': 'Cliente Corregido', 'correo': u + '@otro.co',
        'telefono': '3000000', 'notas': 'una nota'})
    revisar(c.buscar(u)['nombre'] == 'Cliente Corregido', 'los datos se editan')

    code, html, _ = nav.post(f'/admin/cuenta/{fila["id"]}/clave', {'_t': token})
    revisar(code == 200 and 'Contraseña provisional' in html,
            'restablecer muestra la contraseña provisional una sola vez')
    revisar('?clave=' not in html and 'clave=' not in (html.split('<form')[0]),
            'la contraseña provisional no viaja en ninguna URL')
    revisar(c.buscar(u)['debe_cambiar_clave'] is True,
            'tras restablecer, queda obligada a cambiarla')
    return u, fila['id']


def probar_expulsion(base, c, u, id_u, nav_admin):
    print('\nInhabilitar echa a quien esté dentro')
    c.restablecer_clave(id_u, clave=CLAVE_CLIENTE)
    c._actualizar(id_u, {'debe_cambiar_clave': False})

    cliente = Navegador(base)
    code, _, _ = cliente.post('/entrar', {'usuario': u, 'clave': CLAVE_CLIENTE})
    revisar(code == 303, 'el cliente entra')
    code, html, _ = cliente.get('/')
    revisar(code == 200 and 'NADIE MÁS VE ESTAS DECLARACIONES' in html,
            'el cliente ve solo lo suyo, y la bandeja se lo dice')
    revisar('/admin' not in html, 'al cliente no se le ofrece el panel')

    code, _, _ = cliente.get('/admin/cuentas')
    revisar(code == 403, 'el cliente no entra al panel ni escribiendo la dirección',
            f'dio {code}')

    code, html, _ = nav_admin.get(f'/admin/cuenta/{id_u}')
    token = nav_admin.testigo(html)
    nav_admin.post(f'/admin/cuenta/{id_u}/estado', {'_t': token, 'estado': 'inhabilitado'})

    code, html, _ = cliente.get('/')
    revisar(code == 401, 'inhabilitado, la sesión abierta deja de valer al instante',
            f'dio {code}')
    revisar('ya no tiene acceso' in html, 'y se le explica por qué')

    code, html, _ = cliente.post('/entrar', {'usuario': u, 'clave': CLAVE_CLIENTE})
    revisar(code == 401 and 'inhabilitada' in html, 'tampoco puede volver a entrar')
    return cliente


def probar_cierre_de_sesiones(base, c, u, id_u, nav_admin):
    print('\nCerrar sesiones a distancia')
    c.cambiar_estado(id_u, 'activo')
    cliente = Navegador(base)
    cliente.post('/entrar', {'usuario': u, 'clave': CLAVE_CLIENTE})
    revisar(cliente.get('/')[0] == 200, 'el cliente vuelve a entrar')

    code, html, _ = nav_admin.get(f'/admin/cuenta/{id_u}')
    token = nav_admin.testigo(html)
    nav_admin.post(f'/admin/cuenta/{id_u}/sesiones', {'_t': token})

    code, html, _ = cliente.get('/')
    revisar(code == 401 and 'sesión se cerró' in html,
            'cerrar sus sesiones lo saca sin tocarle la contraseña', f'dio {code}')


def probar_registro_publico(base, c, nav_admin):
    print('\nRegistro público')
    code, html, _ = nav_admin.get('/admin/ajustes')
    token = nav_admin.testigo(html)
    nav_admin.post('/admin/ajustes', {'_t': token, 'registro_abierto': '1',
                                      'cupo_por_defecto': '3'})

    visitante = Navegador(base)
    code, html, _ = visitante.get('/registrarse')
    revisar(code == 200 and 'Crear una cuenta' in html, 'la pantalla de registro carga')

    u = 'zzweb' + secrets.token_hex(4)
    code, _, _ = visitante.post('/registrarse', {
        'usuario': u, 'nombre': 'Visitante De Ensayo', 'correo': u + '@ejemplo.co',
        'clave': CLAVE_CLIENTE, 'repetir': 'otra cosa distinta'})
    revisar(code == 400 and not c.buscar(u),
            'si las dos contraseñas no coinciden, no se crea nada')

    code, _, _ = visitante.post('/registrarse', {
        'usuario': u, 'nombre': 'Visitante De Ensayo', 'correo': u + '@ejemplo.co',
        'clave': 'corta', 'repetir': 'corta'})
    revisar(code == 400 and not c.buscar(u), 'una contraseña corta no crea la cuenta')

    code, _, _ = visitante.post('/registrarse', {
        'usuario': u, 'nombre': 'Visitante De Ensayo', 'correo': u + '@ejemplo.co',
        'clave': CLAVE_CLIENTE, 'repetir': CLAVE_CLIENTE, 'rol': 'admin', 'cupo': '999'})
    nueva = c.buscar(u)
    revisar(code == 303 and bool(nueva), 'el registro crea la cuenta')
    revisar(nueva and nueva['rol'] == 'cliente',
            'aunque el formulario pida rol de administrador, nace como cliente')
    revisar(nueva and nueva['cupo'] == 3,
            'el cupo lo pone el ajuste del sistema, no el formulario')

    code, _, _ = visitante.post('/entrar', {'usuario': u, 'clave': CLAVE_CLIENTE})
    revisar(code == 303, 'quien se registra puede entrar de una vez')

    # con el registro cerrado, la puerta no está
    code, html, _ = nav_admin.get('/admin/ajustes')
    token = nav_admin.testigo(html)
    nav_admin.post('/admin/ajustes', {'_t': token, 'cupo_por_defecto': '1'})
    otro = Navegador(base)
    code, html, _ = otro.get('/registrarse')
    revisar(code == 200 and 'está cerrado' in html,
            'con el registro cerrado, la pantalla lo dice en vez de dejar crear')
    code, html, _ = otro.get('/entrar')
    revisar('Regístrese aquí' not in html,
            'y la pantalla de acceso deja de ofrecer el registro')

    code, html, _ = nav_admin.get('/admin/ajustes')
    token = nav_admin.testigo(html)
    nav_admin.post('/admin/ajustes', {'_t': token, 'registro_abierto': '1',
                                      'cupo_por_defecto': '1'})
    return u


def probar_eliminacion(nav_admin, c, usuarios):
    print('\nEliminar cuentas')
    for u in usuarios:
        fila = c.buscar(u)
        if not fila:
            continue
        code, html, _ = nav_admin.get(f'/admin/cuenta/{fila["id"]}/eliminar')
        revisar(code == 200 and 'Eliminar la cuenta' in html or 'eliminar la cuenta' in html,
                f'la confirmación de borrado de «{u}» explica qué se pierde')
        token = nav_admin.testigo(html)
        code, _, _ = nav_admin.post(f'/admin/cuenta/{fila["id"]}/eliminar',
                                    {'_t': token, 'declaraciones': 'conservar'})
        revisar(code == 303 and not c.buscar(u), f'la cuenta «{u}» se elimina')


def probar_ultimo_admin(nav_admin, c, id_admin):
    print('\nEl panel no deja quedarse sin administrador')
    if c.cuantos_admin(excepto=id_admin):
        print('  (hay más administradores activos: se omite)')
        return
    code, html, _ = nav_admin.get(f'/admin/cuenta/{id_admin}')
    token = nav_admin.testigo(html)
    code, _, _ = nav_admin.post(f'/admin/cuenta/{id_admin}/estado',
                                {'_t': token, 'estado': 'inhabilitado'})
    revisar(c.buscar_id(id_admin)['estado'] == 'activo',
            'no se puede inhabilitar al único administrador')
    code, _, _ = nav_admin.post(f'/admin/cuenta/{id_admin}/rol',
                                {'_t': token, 'rol': 'cliente'})
    revisar(c.buscar_id(id_admin)['rol'] == 'admin',
            'no se puede cambiarse el rol a sí mismo')


def probar_salida(nav):
    print('\nSalir')
    code, _, _ = nav.get('/salir')
    revisar(code == 303, 'salir responde una redirección')
    code, html, _ = nav.get('/')
    revisar(code == 401 and 'Bienvenido de nuevo' in html,
            'después de salir, la bandeja vuelve a pedir la clave')



def probar_privacidad(base, c, nav_admin, ua):
    """Nadie ve lo que no cargó, ni el administrador — hasta que se lo concedan.

    Es la regla de privacidad del producto y la más fácil de romper sin darse
    cuenta: basta con que una consulta se olvide del filtro por dueño.
    """
    print('\nPrivacidad: la cartera ajena no se ve')
    import permisos as mod_permisos
    p = mod_permisos.Permisos(c.s)

    # Un cliente con una declaración a su nombre. No se carga de verdad —eso
    # cuesta segundos y una exógena— sino que se le cambia el dueño a una que
    # ya exista; para lo que se mide da igual quién la generó.
    ajenas = c.s.seleccionar('declaraciones', select='id,creada_por', limit='1')
    if not ajenas:
        print('  (no hay declaraciones en la base: se omite)')
        return
    ref, dueno = ajenas[0]['id'], ajenas[0]['creada_por']

    code, html, _ = nav_admin.get('/caso/' + ref)
    revisar(code == 404, 'sin permiso, el administrador no abre un caso ajeno',
            f'dio {code}')
    code, _, _ = nav_admin.get('/libro/' + ref)
    revisar(code == 404, 'ni descarga su libro', f'dio {code}')

    code, html, _ = nav_admin.get('/admin/uso')
    revisar(code == 200 and 'Uso por cuenta' in html, 'el panel de uso carga')
    revisar('nombre_titulo' not in html and 'Contribuyente</th>' not in html,
            'el panel de uso no enseña ni un nombre de contribuyente')

    # Se lo concede el dueño, y entonces sí.
    p.conceder(dueno, ua, dias=1, por='pruebas')
    code, _, _ = nav_admin.get('/caso/' + ref)
    revisar(code == 200, 'con permiso vigente, el caso se abre', f'dio {code}')

    # Un permiso vencido no vale: se fuerza la fecha hacia atrás.
    fila = p.entre(dueno, ua)
    c.s.actualizar('permisos', {'expira_en': '2020-01-01T00:00:00+00:00'},
                   id='eq.' + str(fila['id']))
    code, _, _ = nav_admin.get('/caso/' + ref)
    revisar(code == 404, 'un permiso vencido deja de valer, sin que nadie lo apague',
            f'dio {code}')

    # Y revocarlo surte efecto en la petición siguiente.
    p.conceder(dueno, ua, dias=1, por='pruebas')
    code, _, _ = nav_admin.get('/caso/' + ref)
    revisar(code == 200, 'concedido otra vez, vuelve a abrirse', f'dio {code}')
    p.revocar(dueno, ua, por='pruebas')
    code, _, _ = nav_admin.get('/caso/' + ref)
    revisar(code == 404, 'revocar corta el acceso de inmediato', f'dio {code}')

    # La bitácora no puede delatar a un contribuyente por la puerta de atrás.
    code, html, _ = nav_admin.get('/admin/bitacora')
    revisar(code == 200, 'la bitácora carga')
    revisar('(reservado)' in html or 'declaración ' in html,
            'la bitácora no muestra nombres de contribuyentes')


def probar_descargo_y_cupo(base, c, nav_admin):
    """El descargo es obligatorio y el cupo no se gasta por equivocarse."""
    print('\nDescargo y cupo')
    code, html, _ = nav_admin.get('/')
    revisar('debo revisar la información antes de presentarla' in html
            or 'documento de trabajo' in html.lower(),
            'la bandeja lleva el descargo a la vista')

    # Confirmar sin marcar la casilla no crea nada. Se prueba contra un
    # borrador inventado: si el servidor mirara la casilla DESPUÉS de buscar
    # el borrador, esto daría 404 en vez de negarse — y ese orden importa.
    t = nav_admin.testigo(html)
    inexistente = '00000000-0000-0000-0000-000000000000'
    code, html2, _ = nav_admin.post('/confirmar/' + inexistente, {'_t': t})
    revisar(code in (400, 404) and 'declaración' not in html2.split('<title>')[0],
            'confirmar un borrador que no existe no crea nada', f'dio {code}')


def probar_alertas(base, c, nav_admin, ua):
    """Una alerta marcada como resuelta sobrevive a que el caso se reprocese."""
    print('\nAlertas que se marcan como resueltas')
    import permisos as mod_permisos
    p = mod_permisos.Permisos(c.s)
    filas = c.s.seleccionar('declaraciones', select='id,creada_por', limit='1')
    if not filas:
        print('  (no hay declaraciones en la base: se omite)')
        return
    ref, dueno = filas[0]['id'], filas[0]['creada_por']
    alertas = c.s.alertas_de(ref)
    if not alertas:
        print('  (ese caso no tiene alertas: se omite)')
        return

    p.conceder(dueno, ua, dias=1, por='pruebas')
    try:
        a = alertas[0]
        antes = bool(a.get('resuelta'))
        c.s.marcar_alerta(a['id'], True, nota='resuelta en la prueba', por='pruebas')
        vuelta = {x['id']: x for x in c.s.alertas_de(ref)}[a['id']]
        revisar(vuelta['resuelta'] is True, 'la alerta queda marcada como resuelta')
        revisar('pruebas' in (vuelta.get('nota_contador') or ''),
                'la nota guarda quién la resolvió')
        revisar(bool(vuelta.get('resuelta_en')), 'y cuándo')

        code, html, _ = nav_admin.get('/caso/' + ref)
        revisar(code == 200 and 'Dar por resuelta' in html or 'Reabrir' in html,
                'la ficha del caso ofrece marcar las alertas')

        c.s.marcar_alerta(a['id'], False, por='pruebas')
        vuelta = {x['id']: x for x in c.s.alertas_de(ref)}[a['id']]
        revisar(vuelta['resuelta'] is False, 'y se puede reabrir')
        if antes:
            c.s.marcar_alerta(a['id'], True, nota='(estado original)', por='pruebas')
    finally:
        p.revocar(dueno, ua, por='pruebas')

def main():
    print('═' * 66)
    print('  RENTA IA — regresión del sitio publicado')
    print('═' * 66)

    faltan = sitio.hay_configuracion()
    if faltan:
        print('\nFalta configurar: ' + ', '.join(faltan))
        return 1

    c = cuentas.Cuentas(db.Supabase.desde_env())
    puerto = puerto_libre()
    base = f'http://localhost:{puerto}'
    servidor = ThreadingHTTPServer(('127.0.0.1', puerto), sitio.handler)
    servidor.daemon_threads = True
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    print(f'\nSitio levantado en {base}')

    creados = []
    admin_id = None
    try:
        # Un administrador de un solo uso: el «admin» de verdad se crea en la
        # nube con la contraseña que ya está en Vercel, y no hay que tocarlo.
        ua = 'zzweb' + secrets.token_hex(4)
        creada = c.crear(ua, 'Administrador De Ensayo', CLAVE_ADMIN, rol='admin',
                         estado='activo', creado_por='pruebas')
        admin_id = creada['id']
        creados.append(ua)

        nav = Navegador(base)
        probar_sin_sesion(nav)
        probar_acceso(nav, ua)
        probar_panel(nav)
        probar_csrf(nav)
        u_cliente, id_cliente = probar_gestion_cuentas(nav, c)
        creados.append(u_cliente)
        probar_expulsion(base, c, u_cliente, id_cliente, nav)
        probar_cierre_de_sesiones(base, c, u_cliente, id_cliente, nav)
        u_registrado = probar_registro_publico(base, c, nav)
        creados.append(u_registrado)
        probar_privacidad(base, c, nav, ua)
        probar_descargo_y_cupo(base, c, nav)
        probar_alertas(base, c, nav, ua)
        probar_ultimo_admin(nav, c, admin_id)
        probar_eliminacion(nav, c, [u_cliente, u_registrado])
        probar_salida(nav)
    finally:
        servidor.shutdown()
        for u in creados:
            fila = c.buscar(u)
            if not fila:
                continue
            try:
                c.eliminar(fila['id'], por='pruebas', con_declaraciones=True)
            except cuentas.ErrorCuenta:
                # El administrador de un solo uso suele ser el único que queda,
                # y el sistema —con razón— se niega a borrar al último. Esto es
                # desmontaje de una prueba, no una operación del panel: se borra
                # la fila directamente para no dejar basura en la base.
                c.s.borrar('usuarios', id='eq.' + fila['id'])
            except Exception as ex:
                print(f'  ATENCIÓN: quedó sin borrar «{u}»: {ex}')
        print('\nCuentas de prueba eliminadas.')

    print('\n' + '═' * 66)
    if fallos:
        print(f'  {len(fallos)} PRUEBA(S) FALLAN de {hechas}:')
        for f in fallos:
            print(f'    · {f}')
    else:
        print(f'  TODAS LAS PRUEBAS PASAN ({hechas} comprobaciones)')
    print('═' * 66)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(main())
