# -*- coding: utf-8 -*-
r"""El panel de administración de RENTA IA: todo el HTML, ninguna decisión.

Aquí solo se pinta. Quién puede hacer qué lo resuelve `api\index.py` antes de
llamar a estas funciones, y las reglas de negocio viven en
`generador\cuentas.py`. Si una vista de estas empieza a decidir permisos, es
que algo se coló donde no debía.

Sigue la misma identidad que la bandeja y la pantalla de acceso —escala zinc
sobre blanco, líneas de un píxel, cifras tabulares— reutilizando `render.ESTILO`
y añadiendo encima lo que solo el panel necesita: fichas de cuenta, conmutadores
y la zona de peligro.

Dos criterios de forma que valen para todo el panel:

  · **Ninguna acción destructiva se ejecuta con un enlace.** Los enlaces son
    para mirar; borrar y cambiar exigen un POST con su testigo. Un GET que
    borra es un desastre esperando a un rastreador o a una precarga.
  · **Lo irreversible pasa por una pantalla de confirmación** que dice, con
    números, qué se va a perder. Nada de ventanitas del navegador.
"""
import cuentas
import render
from render import e

VERDE, AMBAR, ROJO, AZUL, GRIS = (render.VERDE, render.AMBAR, render.ROJO,
                                  render.AZUL, render.GRIS)

ROL_COLOR = {'admin': ROJO, 'contador': AZUL, 'cliente': GRIS}
ROL_NOMBRE = {'admin': 'Administrador', 'contador': 'Contador', 'cliente': 'Cliente'}
ESTADO_COLOR = {'activo': VERDE, 'pendiente': AMBAR, 'inhabilitado': GRIS}
ESTADO_NOMBRE = {'activo': 'Activa', 'pendiente': 'Pendiente', 'inhabilitado': 'Inhabilitada'}

# Cómo se lee cada acción de la bitácora, y si merece resaltarse.
ACCION_ET = {
    'acceso': ('Entró', ''),
    'acceso_fallido': ('Intento fallido', 'mal'),
    'acceso_bloqueado': ('Intento durante el bloqueo', 'mal'),
    'acceso_denegado': ('Acceso denegado', 'mal'),
    'registro': ('Se registró', ''),
    'salida': ('Cerró sesión', ''),
    'cuenta_creada': ('Cuenta creada', ''),
    'cuenta_editada': ('Datos de la cuenta', ''),
    'cuenta_activada': ('Cuenta activada', ''),
    'cuenta_inhabilitada': ('Cuenta inhabilitada', 'mal'),
    'cuenta_a_pendiente': ('Cuenta a pendiente', ''),
    'cuenta_rol': ('Cambio de rol', ''),
    'cuenta_cupo': ('Cambio de cupo', ''),
    'cuenta_eliminada': ('Cuenta eliminada', 'mal'),
    'cuenta_desbloqueada': ('Cuenta desbloqueada', ''),
    'clave_cambiada': ('Contraseña cambiada', ''),
    'clave_restablecida': ('Contraseña restablecida', ''),
    'clave_cambio_fallido': ('Cambio de contraseña fallido', 'mal'),
    'sesiones_cerradas': ('Sesiones cerradas', ''),
    'declaracion_creada': ('Declaración cargada', ''),
    'declaracion_eliminada': ('Declaración eliminada', 'mal'),
    'declaracion_estado': ('Estado de la declaración', ''),
    'libro_descargado': ('Libro descargado', ''),
    'ajuste': ('Ajuste del sistema', ''),
}

ESTILO = """
/* ── PANEL ── */
.tarjetas{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
gap:14px;margin-bottom:26px}
.tj{background:#fff;border:1px solid var(--bord);border-radius:12px;padding:16px 18px;
box-shadow:var(--sombra)}
.tj .n{font-size:27px;font-weight:600;letter-spacing:-.03em;line-height:1.1;
font-variant-numeric:tabular-nums}
.tj .l{font-size:10px;letter-spacing:.13em;color:var(--z500);text-transform:uppercase;
margin-top:5px;font-weight:600}
.tj .p{font-size:11.5px;color:var(--z400);margin-top:7px;line-height:1.45}
.tj.v .n{color:var(--verde)}.tj.a .n{color:var(--ambar)}.tj.r .n{color:var(--rojo)}
.tj a{color:var(--z500);font-size:11.5px}

.seccion{background:#fff;border:1px solid var(--bord);border-radius:12px;
margin-bottom:18px;box-shadow:var(--sombra);overflow:hidden}
.seccion > h2{font-size:15px;padding:15px 20px;border-bottom:1px solid var(--bord);
display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.seccion > h2 .nota{font-weight:400;font-size:12.3px;color:var(--z500);margin-left:auto}
.seccion .cuerpo{padding:18px 20px}
.seccion .cuerpo > p{font-size:12.8px;color:var(--text2);margin-bottom:14px;max-width:82ch}
.seccion table{border:none;border-radius:0;margin:0;box-shadow:none}
.seccion table th:first-child,.seccion table td:first-child{padding-left:20px}
.seccion table th:last-child,.seccion table td:last-child{padding-right:20px}

/* etiquetas de rol y estado */
.tag{display:inline-block;font-size:9.5px;font-weight:600;letter-spacing:.06em;
padding:3px 9px;border-radius:20px;border:1px solid currentColor;white-space:nowrap;
text-transform:uppercase}
.tag.solido{color:#fff;border-color:transparent}

/* la cuenta dentro de la tabla */
.cuenta-cel b{display:block;font-size:13.5px;font-weight:600}
.cuenta-cel span{display:block;font-size:11.8px;color:var(--z500)}
.cuenta-cel .yo{font-size:9.5px;color:var(--z400);letter-spacing:.06em;
text-transform:uppercase;font-weight:600;margin-top:2px}

/* cupo con barrita */
.cupo-cel{min-width:118px}
.cupo-cel .txt{font-size:12.5px;font-variant-numeric:tabular-nums}
.cupo-cel .b{height:4px;background:var(--z200);border-radius:3px;margin-top:5px;overflow:hidden}
.cupo-cel .b i{display:block;height:100%;background:var(--tinta)}
.cupo-cel .b i.lleno{background:var(--rojo)}

/* botones pequeños dentro de las tablas y fichas */
.acc-fila{display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end}
.acc-fila form{display:inline}
button.mini,a.mini{margin-top:0;padding:6px 11px;font-size:12px;border-radius:7px;
font-weight:500;display:inline-block;text-decoration:none;line-height:1.35;
font-family:inherit;border:1px solid transparent;cursor:pointer}
button.sec,a.mini.sec{background:#fff;color:var(--ink);border-color:var(--bord-2)}
button.sec:hover,a.mini.sec:hover{background:var(--z100);border-color:var(--z400)}
button.peligro{background:#fff;color:var(--rojo);border-color:var(--rojo-b)}
button.peligro:hover{background:var(--rojo-f);border-color:var(--rojo)}
button.peligro.firme{background:var(--rojo);color:#fff;border-color:var(--rojo)}
button.peligro.firme:hover{background:#93231A}

/* formularios del panel */
.rejilla{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px;
align-items:start}
/* align-content:start impide que un campo se estire hasta la altura del más
   alto de su fila cuando el vecino lleva una línea de ayuda debajo. */
.campo{display:grid;gap:6px;align-content:start}
.campo > label{font-size:12px;font-weight:600;color:var(--z600);letter-spacing:.01em}
.campo .pista{font-size:11.5px;color:var(--z400);line-height:1.45}
.campo input[type=text],.campo input[type=email],.campo input[type=password],
.campo input[type=number],.campo select,.campo textarea{
width:100%;border:1px solid var(--bord);border-radius:8px;padding:9px 12px;font-size:13.5px;
font-family:inherit;background:#fff;color:var(--ink);box-shadow:var(--sombra);
transition:border-color .15s,box-shadow .15s}
.campo textarea{min-height:74px;resize:vertical;line-height:1.5}
.campo input:focus,.campo select:focus,.campo textarea:focus{outline:none;
border-color:var(--z400);box-shadow:0 0 0 3px rgba(161,161,170,.20)}
.campo input[disabled]{background:var(--z100);color:var(--z500)}
.marca-check{display:flex;align-items:center;gap:9px;font-size:13px;color:var(--text2);
margin-top:9px;cursor:pointer}
.marca-check input{width:16px;height:16px;accent-color:#18181B;cursor:pointer;flex:none}

/* zona de peligro */
.peligro-caja{background:var(--rojo-f);border:1px solid var(--rojo-b);border-radius:12px;
padding:18px 20px;margin-top:8px}
.peligro-caja h2{font-size:14.5px;color:#7A271A;margin-bottom:7px}
.peligro-caja p{font-size:12.8px;color:#7A271A;margin-bottom:14px;max-width:82ch;line-height:1.6}
.peligro-caja b{font-weight:600}

/* filtros */
.filtros{display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;margin-bottom:16px}
.filtros .campo{gap:5px}
.filtros input,.filtros select{min-width:180px}
.filtros button{margin-top:0}

/* bitácora */
td.mono-t{font-variant-numeric:tabular-nums;white-space:nowrap;font-size:12.5px;color:var(--z500)}
tr.mal td{background:var(--rojo-f)}
tr.mal td:first-child{box-shadow:inset 3px 0 0 var(--rojo)}
.detalle-cel{font-size:12.5px;color:var(--text2);max-width:44ch}

/* aviso con la clave temporal */
.clave-nueva{background:#fff;border:1px solid var(--bord-2);border-radius:10px;
padding:14px 17px;margin:12px 0 0;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.clave-nueva code{font-family:ui-monospace,'Cascadia Mono','Consolas',monospace;
font-size:18px;letter-spacing:.06em;font-weight:600;color:var(--ink);
background:var(--z100);border:1px solid var(--bord);border-radius:7px;padding:7px 13px}
.clave-nueva span{font-size:12.3px;color:var(--text2);flex:1;min-width:220px;line-height:1.5}

.migas{font-size:13px;margin-bottom:16px}
.vacio-chico{padding:24px;text-align:center;color:var(--muted);font-size:13px}
@media(max-width:760px){
  .seccion table{display:block;overflow-x:auto}
  .acc-fila{justify-content:flex-start}
}
"""


# ── piezas sueltas ──────────────────────────────────────────────────────
def _t(token):
    """El campo oculto con el testigo anti-CSRF. Va en TODO formulario."""
    return f'<input type="hidden" name="_t" value="{e(token)}">'


def tag(texto, color, solido=False):
    clase = 'tag solido' if solido else 'tag'
    estilo = f'background:{color}' if solido else f'color:{color}'
    return f'<span class="{clase}" style="{estilo}">{e(texto)}</span>'


def tag_rol(rol):
    return tag(ROL_NOMBRE.get(rol, rol), ROL_COLOR.get(rol, GRIS))


def tag_estado(estado):
    return tag(ESTADO_NOMBRE.get(estado, estado), ESTADO_COLOR.get(estado, GRIS),
               solido=(estado == 'activo'))


def nav(activo, rol):
    """Las pestañas.

    Los dos apartados —Renta y RST— los ve todo el mundo: son los dos regímenes
    que atiende la aplicación y cambiar entre ellos es la navegación principal.
    El resto de pestañas es del administrador.
    """
    # El apartado RST es, por ahora, solo del administrador: está recién
    # publicado y los clientes no deben verlo hasta que se decida cómo se les
    # habilita. Para quien no es admin no hay a dónde ir, así que no hay barra.
    if rol != 'admin':
        return ''
    enlaces = [('/', 'Renta', 'bandeja'),
               ('/rst', 'RST', 'rst'),
               ('/admin', 'Panel', 'panel'),
               ('/admin/cuentas', 'Cuentas', 'cuentas'),
               ('/admin/declaraciones', 'Declaraciones', 'declaraciones'),
               ('/admin/bitacora', 'Bitácora', 'bitacora'),
               ('/admin/ajustes', 'Ajustes', 'ajustes')]
    return ''.join(
        f'<a href="{u}" class="{"act" if k == activo else ""}">{e(t)}</a>'
        for u, t, k in enlaces)


def _pagina(titulo, cuerpo, sub, usuario, rol, activo, error='', hecho=''):
    avisos = ((f'<div class="err">{e(error)}</div>' if error else '')
              + (f'<div class="ok-msg">{e(hecho)}</div>' if hecho else ''))
    return render.pagina(titulo, avisos + cuerpo, sub, '', usuario,
                         render.PIE_NUBE, nav(activo, rol), ROL_NOMBRE.get(rol, rol),
                         estilo_extra=ESTILO)


def _cupo_celda(usadas, tope):
    if tope is None:
        return '<div class="cupo-cel"><div class="txt">Sin límite</div></div>'
    pct = min(100, int(usadas * 100 / tope)) if tope else 100
    lleno = ' lleno' if usadas >= tope else ''
    return (f'<div class="cupo-cel"><div class="txt">{usadas} / {tope}</div>'
            f'<div class="b"><i class="{lleno.strip()}" style="width:{pct}%"></i></div></div>')


def _sin_filas(mensaje, columnas):
    return f'<tr><td colspan="{columnas}"><div class="vacio-chico">{e(mensaje)}</div></td></tr>'


# ── resumen ─────────────────────────────────────────────────────────────
def vista_resumen(datos, usuario, token, error='', hecho=''):
    """La portada del panel: qué hay, qué pide atención y por dónde entrar."""
    pendientes = datos['pendientes']
    aviso_pendientes = ''
    if pendientes:
        plural = 's' if pendientes != 1 else ''
        aviso_pendientes = (
            f'<div class="aviso" style="margin:0 0 22px;border-color:#EADFC0;'
            f'background:#FDFAF1"><b>{pendientes} cuenta{plural} '
            f'esperando aprobación.</b> Nadie puede entrar hasta que usted las '
            f'active. <a href="/admin/cuentas?estado=pendiente">Verlas ahora &rarr;</a></div>')

    bloqueadas = datos['bloqueadas']
    aviso_bloqueo = ''
    if bloqueadas:
        plural = 's' if bloqueadas != 1 else ''
        aviso_bloqueo = (
            f'<div class="aviso" style="margin:0 0 22px;border-color:var(--rojo-b);'
            f'background:var(--rojo-f)"><b>{bloqueadas} cuenta{plural} bloqueada{plural} '
            f'por intentos fallidos.</b> Puede ser un olvido de contraseña o alguien '
            f'probando claves. Mírelo en la bitácora antes de desbloquear.</div>')

    tarjetas = f"""<div class="tarjetas">
<div class="tj"><div class="n">{datos['cuentas']}</div><div class="l">Cuentas</div>
  <div class="p">{datos['activas']} activas · {datos['inhabilitadas']} inhabilitadas</div></div>
<div class="tj{' a' if pendientes else ''}"><div class="n">{pendientes}</div>
  <div class="l">Por aprobar</div><div class="p">Cuentas nuevas a la espera</div></div>
<div class="tj"><div class="n">{datos['declaraciones']}</div><div class="l">Declaraciones</div>
  <div class="p">{datos['contribuyentes']} contribuyentes</div></div>
<div class="tj v"><div class="n">{datos['liberadas']}</div><div class="l">Liberadas</div>
  <div class="p">Revisadas y dadas por buenas</div></div>
<div class="tj{' r' if datos['fallidos'] else ''}"><div class="n">{datos['fallidos']}</div>
  <div class="l">Fallos de acceso</div><div class="p">Últimas 24 horas</div></div>
</div>"""

    filas = ''.join(_fila_bitacora(b) for b in datos['ultimos']) or _sin_filas(
        'Todavía no hay movimientos registrados.', 5)

    cuerpo = f"""{aviso_pendientes}{aviso_bloqueo}{tarjetas}
<div class="seccion">
  <h2>Últimos movimientos<span class="nota"><a href="/admin/bitacora">Ver la bitácora completa &rarr;</a></span></h2>
  <table><thead><tr><th style="width:150px">Cuándo</th><th style="width:140px">Quién</th>
  <th style="width:210px">Qué</th><th>Sobre qué</th><th style="width:120px">Desde</th>
  </tr></thead><tbody>{filas}</tbody></table>
</div>
<div class="aviso"><b>Qué puede hacer desde aquí.</b> En <a href="/admin/cuentas">Cuentas</a>
aprueba, inhabilita o elimina personas y le fija a cada una cuántas declaraciones puede
procesar. En <a href="/admin/declaraciones">Declaraciones</a> ve todos los casos de la
plataforma y puede borrar los que no deban conservarse — se van también sus archivos.
En <a href="/admin/ajustes">Ajustes</a> abre o cierra el registro y decide el cupo con el que
nace cada cuenta nueva. Todo lo que se hace queda escrito en la
<a href="/admin/bitacora">bitácora</a>, con quién y cuándo.</div>"""
    return _pagina('Panel', cuerpo, 'PANEL DE ADMINISTRACIÓN', usuario, 'admin',
                   'panel', error, hecho)


# ── cuentas ─────────────────────────────────────────────────────────────
def _fila_cuenta(u, usadas, yo, token):
    """Una cuenta en la tabla. Las acciones de aquí son las de un clic;
    lo demás vive en la ficha."""
    correo = f'<span>{e(u["correo"])}</span>' if u.get('correo') else \
             '<span style="color:var(--z400)">sin correo</span>'
    marca_yo = '<span class="yo">Es usted</span>' if yo else ''
    acciones = []
    if u['estado'] != 'activo':
        acciones.append(
            f'<form method="post" action="/admin/cuenta/{e(u["id"])}/estado">'
            f'{_t(token)}<input type="hidden" name="estado" value="activo">'
            f'<input type="hidden" name="desde" value="lista">'
            f'<button class="mini sec" type="submit">'
            f'{"Aprobar" if u["estado"] == "pendiente" else "Activar"}</button></form>')
    elif not yo:
        acciones.append(
            f'<form method="post" action="/admin/cuenta/{e(u["id"])}/estado">'
            f'{_t(token)}<input type="hidden" name="estado" value="inhabilitado">'
            f'<input type="hidden" name="desde" value="lista">'
            f'<button class="mini peligro" type="submit">Inhabilitar</button></form>')
    acciones.append(f'<a class="mini sec" href="/admin/cuenta/{e(u["id"])}">Ficha</a>')

    ultimo = cuentas.hace_cuanto(u['ultimo_acceso']) if u.get('ultimo_acceso') else 'nunca'
    return f"""<tr>
<td class="cuenta-cel"><b>{e(u['usuario'])}</b><span>{e(u['nombre'])}</span>{marca_yo}</td>
<td>{correo}</td>
<td>{tag_rol(u['rol'])}</td>
<td>{tag_estado(u['estado'])}</td>
<td>{_cupo_celda(usadas, u['cupo'])}</td>
<td class="mono-t">{e(ultimo)}</td>
<td><div class="acc-fila">{''.join(acciones)}</div></td></tr>"""


def vista_cuentas(lista, usadas_por, usuario, token, filtro='', error='', hecho=''):
    filas = ''.join(_fila_cuenta(u, usadas_por.get(u['usuario'], 0),
                                 u['usuario'] == usuario, token)
                    for u in lista)
    if not filas:
        filas = _sin_filas('No hay cuentas que cumplan ese filtro.', 7)

    opciones = ''.join(
        f'<option value="{v}"{" selected" if filtro == v else ""}>{e(t)}</option>'
        for v, t in (('', 'Todas'), ('activo', 'Solo activas'),
                     ('pendiente', 'Solo pendientes de aprobación'),
                     ('inhabilitado', 'Solo inhabilitadas')))

    cuerpo = f"""
<div class="filtros">
  <form method="get" action="/admin/cuentas" class="filtros" style="margin:0">
    <div class="campo"><label for="estado">Estado</label>
      <select id="estado" name="estado" onchange="this.form.submit()">{opciones}</select></div>
    <noscript><button class="mini sec" type="submit">Filtrar</button></noscript>
  </form>
  <div style="margin-left:auto"><a class="mini sec" href="/admin/cuentas/nueva"
     style="padding:9px 15px">Crear una cuenta</a></div>
</div>
<div class="seccion">
  <h2>Cuentas registradas<span class="nota">{len(lista)} en total</span></h2>
  <table><thead><tr>
    <th>Cuenta</th><th>Correo</th><th style="width:120px">Rol</th>
    <th style="width:120px">Estado</th><th style="width:130px">Cupo</th>
    <th style="width:120px">Último acceso</th><th style="width:190px"></th>
  </tr></thead><tbody>{filas}</tbody></table>
</div>
<div class="aviso"><b>Cupo</b> es cuántas declaraciones puede cargar esa cuenta en total.
Al llegar al tope la persona sigue entrando y consultando lo suyo, pero no puede procesar
más. <b>Inhabilitar</b> deja la cuenta y sus declaraciones intactas y le cierra la sesión
en el acto; <b>eliminar</b>, en la ficha, es definitivo. Un contador o un administrador ven
toda la cartera y por eso nunca tienen cupo.</div>"""
    return _pagina('Cuentas', cuerpo, 'CUENTAS REGISTRADAS', usuario, 'admin',
                   'cuentas', error, hecho)


def vista_cuenta(u, datos, usuario, token, error='', hecho='', clave_nueva=''):
    """La ficha completa de una cuenta: todo lo que se le puede hacer."""
    yo = u['usuario'] == usuario
    usadas = datos['usadas']

    aviso_clave = ''
    if clave_nueva:
        aviso_clave = f"""<div class="seccion"><h2>Contraseña provisional</h2>
<div class="cuerpo"><div class="clave-nueva"><code>{e(clave_nueva)}</code>
<span>Entréguesela a <b>{e(u['nombre'])}</b> por un medio seguro. No vuelve a
mostrarse y no queda guardada en ninguna parte: el sistema solo conserva su huella.
Al entrar, se le exigirá cambiarla.</span></div></div></div>"""

    bloqueo = cuentas.desde_iso(u.get('bloqueado_hasta'))
    estado_seguridad = []
    if bloqueo and bloqueo > cuentas.ahora():
        estado_seguridad.append(
            f'<span class="mal">Bloqueada por intentos fallidos hasta '
            f'{e(cuentas.fecha_corta(u["bloqueado_hasta"]))}.</span>')
    if u.get('intentos_fallidos'):
        estado_seguridad.append(f'{u["intentos_fallidos"]} intento(s) fallido(s) sin acertar.')
    if u.get('debe_cambiar_clave'):
        estado_seguridad.append('Tiene pendiente cambiar su contraseña al entrar.')
    estado_seguridad = ('<p>' + '<br>'.join(estado_seguridad) + '</p>'
                        if estado_seguridad else
                        '<p>Sin intentos fallidos pendientes.</p>')

    # ── estado y rol ──
    botones_estado = []
    for valor, texto in (('activo', 'Activar'), ('pendiente', 'Pasar a pendiente'),
                         ('inhabilitado', 'Inhabilitar')):
        if valor == u['estado']:
            continue
        if yo and valor != 'activo':
            continue          # nadie se cierra a sí mismo la puerta por error
        peligro = ' peligro' if valor == 'inhabilitado' else ' sec'
        botones_estado.append(
            f'<form method="post" action="/admin/cuenta/{e(u["id"])}/estado">{_t(token)}'
            f'<input type="hidden" name="estado" value="{valor}">'
            f'<button class="mini{peligro}" type="submit">{e(texto)}</button></form>')

    opciones_rol = ''.join(
        f'<option value="{r}"{" selected" if u["rol"] == r else ""}>'
        f'{e(cuentas.ROL_ET[r][0])} — {e(cuentas.ROL_ET[r][1])}</option>' for r in cuentas.ROLES)
    nota_rol = ('<p class="pista">No puede cambiar su propio rol: si se degrada por '
                'descuido, se queda sin panel.</p>' if yo else '')

    sin_limite = ' checked' if u['cupo'] is None else ''
    cuerpo_cupo = ('' if u['rol'] == 'cliente' else
                   '<p>Esta cuenta es de ' + e(cuentas.ROL_ET[u['rol']][0].lower()) +
                   ': ve toda la cartera, así que el cupo no le aplica. Si la pasa a '
                   'cliente, podrá fijárselo.</p>')

    # ── sus declaraciones ──
    filas_decl = ''.join(_fila_declaracion(d, token, compacta=True)
                         for d in datos['declaraciones'])
    if not filas_decl:
        filas_decl = _sin_filas('Esta cuenta no ha cargado ninguna declaración.', 6)

    marca_yo = ' <span class="yo">(es usted)</span>' if yo else ''
    cuerpo = f"""
<div class="migas"><a href="/admin/cuentas">&larr; Volver a las cuentas</a></div>
{aviso_clave}
<div class="seccion">
  <h2>{e(u['usuario'])}{marca_yo}<span class="nota">{tag_rol(u['rol'])} {tag_estado(u['estado'])}</span></h2>
  <div class="cuerpo">
    <div class="rejilla">
      <div><div class="campo"><label>Nombre</label><div>{e(u['nombre'])}</div></div></div>
      <div><div class="campo"><label>Correo</label>
        <div>{e(u['correo']) if u.get('correo') else '—'}</div></div></div>
      <div><div class="campo"><label>Teléfono</label>
        <div>{e(u['telefono']) if u.get('telefono') else '—'}</div></div></div>
      <div><div class="campo"><label>Creada</label>
        <div>{e(cuentas.fecha_corta(u['creado_en']))}<br>
        <span class="pista">por {e(u.get('creado_por') or '—')}</span></div></div></div>
      <div><div class="campo"><label>Último acceso</label>
        <div>{e(cuentas.fecha_corta(u['ultimo_acceso']) if u.get('ultimo_acceso') else 'Nunca ha entrado')}</div></div></div>
      <div><div class="campo"><label>Declaraciones cargadas</label>
        <div>{usadas}</div></div></div>
    </div>
  </div>
</div>

<div class="seccion">
  <h2>Estado y permisos</h2>
  <div class="cuerpo">
    <p>Inhabilitar una cuenta le cierra la sesión en el acto, aquí y en cualquier
    otro equipo donde esté abierta. Sus declaraciones no se tocan.</p>
    <div class="acc-fila" style="justify-content:flex-start;margin-bottom:20px">
      {''.join(botones_estado)}</div>
    <form method="post" action="/admin/cuenta/{e(u['id'])}/rol">{_t(token)}
      <div class="rejilla"><div class="campo">
        <label for="rol">Rol</label>
        <select id="rol" name="rol" {'disabled' if yo else ''}>{opciones_rol}</select>
        {nota_rol}
      </div></div>
      {'' if yo else '<button class="mini sec" type="submit" style="margin-top:14px">Guardar el rol</button>'}
    </form>
  </div>
</div>

<div class="seccion">
  <h2>Cupo de declaraciones</h2>
  <div class="cuerpo">
    {cuerpo_cupo}
    <p>Cuántas declaraciones puede procesar esta cuenta en total. Lleva
    <b>{usadas}</b>. Si baja el cupo por debajo de lo que ya usó, no se borra nada:
    simplemente no podrá cargar más hasta que se lo suba.</p>
    <form method="post" action="/admin/cuenta/{e(u['id'])}/cupo">{_t(token)}
      <div class="rejilla" style="max-width:420px"><div class="campo">
        <label for="cupo">Declaraciones permitidas</label>
        <input id="cupo" name="cupo" type="number" min="0" max="100000"
               value="{'' if u['cupo'] is None else u['cupo']}" placeholder="0">
        <label class="marca-check"><input type="checkbox" name="sin_limite" value="1"{sin_limite}>
          Sin límite</label>
      </div></div>
      <button class="mini sec" type="submit" style="margin-top:14px">Guardar el cupo</button>
    </form>
  </div>
</div>

<div class="seccion">
  <h2>Datos de contacto</h2>
  <div class="cuerpo">
    <form method="post" action="/admin/cuenta/{e(u['id'])}/datos">{_t(token)}
      <div class="rejilla">
        <div class="campo"><label for="nombre">Nombre completo</label>
          <input id="nombre" name="nombre" type="text" value="{e(u['nombre'])}" maxlength="120" required></div>
        <div class="campo"><label for="correo">Correo</label>
          <input id="correo" name="correo" type="email" value="{e(u.get('correo') or '')}" maxlength="160"></div>
        <div class="campo"><label for="telefono">Teléfono</label>
          <input id="telefono" name="telefono" type="text" value="{e(u.get('telefono') or '')}" maxlength="40"></div>
      </div>
      <div class="campo" style="margin-top:16px"><label for="notas">Notas internas</label>
        <textarea id="notas" name="notas" maxlength="1000"
          placeholder="Para su control: quién es, qué acordaron, por qué tiene ese cupo…">{e(u.get('notas') or '')}</textarea>
        <span class="pista">Solo las ve usted. El titular de la cuenta no.</span></div>
      <button class="mini sec" type="submit" style="margin-top:14px">Guardar los datos</button>
    </form>
  </div>
</div>

<div class="seccion">
  <h2>Seguridad</h2>
  <div class="cuerpo">
    {estado_seguridad}
    <div class="acc-fila" style="justify-content:flex-start">
      <form method="post" action="/admin/cuenta/{e(u['id'])}/clave">{_t(token)}
        <button class="mini sec" type="submit">Restablecer la contraseña</button></form>
      <form method="post" action="/admin/cuenta/{e(u['id'])}/sesiones">{_t(token)}
        <button class="mini sec" type="submit">Cerrar sus sesiones</button></form>
      <form method="post" action="/admin/cuenta/{e(u['id'])}/desbloquear">{_t(token)}
        <button class="mini sec" type="submit">Levantar el bloqueo</button></form>
    </div>
    <p style="margin:14px 0 0"><b>Restablecer</b> genera una contraseña provisional que
    se muestra una sola vez; la anterior deja de servir de inmediato y al titular se le
    exige cambiarla al entrar. Usted nunca puede ver la contraseña de nadie: de todas se
    guarda únicamente una huella irreversible.</p>
  </div>
</div>

<div class="seccion">
  <h2>Declaraciones de esta cuenta<span class="nota">{usadas} caso(s)</span></h2>
  <table><thead><tr><th>Contribuyente</th><th style="width:78px">Año</th>
    <th style="width:110px">Semáforo</th><th style="width:120px">Estado</th>
    <th style="width:120px">Cargada</th><th style="width:170px"></th>
  </tr></thead><tbody>{filas_decl}</tbody></table>
</div>

<div class="peligro-caja">
  <h2>Eliminar esta cuenta</h2>
  <p>Borra a <b>{e(u['usuario'])}</b> de forma definitiva. En la pantalla siguiente
  decidirá qué pasa con sus {usadas} declaración(es): puede conservarlas en la cartera
  o borrarlas también, con sus libros y sus exógenas. No hay papelera.</p>
  <form method="get" action="/admin/cuenta/{e(u['id'])}/eliminar">
    <button class="mini peligro firme" type="submit">Continuar con la eliminación</button>
  </form>
</div>"""
    return _pagina(u['usuario'], cuerpo,
                   f'FICHA DE LA CUENTA &nbsp;&middot;&nbsp; {e(u["usuario"]).upper()}',
                   usuario, 'admin', 'cuentas', error, hecho)


def vista_confirmar_cuenta(u, n_decl, usuario, token):
    """La única pantalla que borra personas. Dice con números qué se pierde."""
    if n_decl:
        opciones = f"""
<form method="post" action="/admin/cuenta/{e(u['id'])}/eliminar" style="margin-bottom:12px">
  {_t(token)}<input type="hidden" name="declaraciones" value="conservar">
  <button class="mini sec" type="submit" style="padding:9px 15px">
    Eliminar solo la cuenta y conservar sus {n_decl} declaración(es)</button></form>
<form method="post" action="/admin/cuenta/{e(u['id'])}/eliminar">
  {_t(token)}<input type="hidden" name="declaraciones" value="eliminar">
  <button class="mini peligro firme" type="submit" style="padding:9px 15px">
    Eliminar la cuenta y también sus {n_decl} declaración(es)</button></form>"""
        explicacion = f"""<p>Esta cuenta ha cargado <b>{n_decl} declaración(es)</b>.
Son papeles de trabajo de contribuyentes reales, así que el sistema no decide por usted:</p>
<ul style="margin:0 0 16px 20px;font-size:12.8px;color:#7A271A;line-height:1.7">
<li><b>Conservarlas</b> — siguen en la cartera y usted las sigue viendo. Quedan a nombre
de un usuario que ya no existe, lo que el panel muestra tal cual.</li>
<li><b>Eliminarlas</b> — se van las declaraciones, sus alertas, sus libros y las exógenas
que subió. Si algún contribuyente se queda sin ningún caso, se borra también su ficha.</li></ul>"""
    else:
        opciones = f"""
<form method="post" action="/admin/cuenta/{e(u['id'])}/eliminar">
  {_t(token)}<input type="hidden" name="declaraciones" value="conservar">
  <button class="mini peligro firme" type="submit" style="padding:9px 15px">
    Sí, eliminar la cuenta</button></form>"""
        explicacion = '<p>Esta cuenta no ha cargado ninguna declaración.</p>'

    cuerpo = f"""
<div class="migas"><a href="/admin/cuenta/{e(u['id'])}">&larr; Volver a la ficha</a></div>
<div class="peligro-caja">
  <h2>¿Eliminar la cuenta «{e(u['usuario'])}»?</h2>
  <p><b>{e(u['nombre'])}</b>{' · ' + e(u['correo']) if u.get('correo') else ''} ·
  {e(ROL_NOMBRE.get(u['rol'], u['rol']))}</p>
  {explicacion}
  <p>La acción es definitiva y queda escrita en la bitácora a su nombre.</p>
  {opciones}
  <p style="margin-top:16px"><a href="/admin/cuenta/{e(u['id'])}">No, cancelar</a></p>
</div>"""
    return _pagina('Eliminar cuenta', cuerpo, 'CONFIRMAR LA ELIMINACIÓN',
                   usuario, 'admin', 'cuentas')


def vista_nueva_cuenta(usuario, token, valores=None, error=''):
    """Alta a mano: para dar acceso sin que la persona pase por el registro."""
    v = valores or {}
    opciones_rol = ''.join(
        f'<option value="{r}"{" selected" if v.get("rol", "cliente") == r else ""}>'
        f'{e(cuentas.ROL_ET[r][0])} — {e(cuentas.ROL_ET[r][1])}</option>' for r in cuentas.ROLES)
    cuerpo = f"""
<div class="migas"><a href="/admin/cuentas">&larr; Volver a las cuentas</a></div>
<div class="seccion">
  <h2>Crear una cuenta</h2>
  <div class="cuerpo">
    <p>Úselo para dar acceso directo sin que la persona se registre. Si deja la
    contraseña en blanco, el sistema genera una provisional y se la muestra una sola vez
    para que usted se la entregue; al entrar se le exigirá cambiarla.</p>
    <form method="post" action="/admin/cuentas/nueva">{_t(token)}
      <div class="rejilla">
        <div class="campo"><label for="usuario">Nombre de usuario</label>
          <input id="usuario" name="usuario" type="text" required maxlength="32"
                 autocapitalize="none" autocorrect="off" spellcheck="false"
                 value="{e(v.get('usuario', ''))}" placeholder="juan.perez">
          <span class="pista">Letras sin tilde, números, punto, guion y guion bajo.
          No se puede cambiar después.</span></div>
        <div class="campo"><label for="nombre">Nombre completo</label>
          <input id="nombre" name="nombre" type="text" required maxlength="120"
                 value="{e(v.get('nombre', ''))}" placeholder="Juan Pérez Gómez"></div>
        <div class="campo"><label for="correo">Correo</label>
          <input id="correo" name="correo" type="email" maxlength="160"
                 value="{e(v.get('correo', ''))}" placeholder="juan@ejemplo.com"></div>
        <div class="campo"><label for="telefono">Teléfono</label>
          <input id="telefono" name="telefono" type="text" maxlength="40"
                 value="{e(v.get('telefono', ''))}"></div>
        <div class="campo"><label for="rol">Rol</label>
          <select id="rol" name="rol">{opciones_rol}</select></div>
        <div class="campo"><label for="cupo">Cupo de declaraciones</label>
          <input id="cupo" name="cupo" type="number" min="0" max="100000"
                 value="{e(v.get('cupo', ''))}" placeholder="1">
          <label class="marca-check"><input type="checkbox" name="sin_limite" value="1">
            Sin límite</label>
          <span class="pista">Solo aplica al rol Cliente.</span></div>
        <div class="campo"><label for="clave">Contraseña (opcional)</label>
          <input id="clave" name="clave" type="text" maxlength="200"
                 autocomplete="off" placeholder="se genera una si lo deja vacío">
          <span class="pista">Mínimo {cuentas.MIN_CLAVE} caracteres.</span></div>
      </div>
      <label class="marca-check"><input type="checkbox" name="activa" value="1" checked>
        Dejarla activa desde ya (si no, queda pendiente de aprobación)</label>
      <button type="submit" style="margin-top:18px">Crear la cuenta</button>
    </form>
  </div>
</div>"""
    return _pagina('Crear cuenta', cuerpo, 'CREAR UNA CUENTA', usuario, 'admin',
                   'cuentas', error)


# ── declaraciones ───────────────────────────────────────────────────────
def _fila_declaracion(d, token, compacta=False):
    sem = d.get('semaforo') or '—'
    color = {'VERDE': VERDE, 'AMARILLO': AMBAR, 'ROJO': ROJO}.get(sem, GRIS)
    est_color, est_texto = render.ESTADO_ET.get(d.get('estado', 'borrador'),
                                                render.ESTADO_ET['borrador'])
    persona = ((d.get('contribuyentes') or {}).get('nombre_titulo')
               or d.get('persona') or 'Sin nombre')
    ident = (d.get('contribuyentes') or {}).get('identificacion', '')

    dueno = ''
    if not compacta:
        marca = '' if d.get('dueno_existe', True) else \
            ' <span class="pista" style="color:var(--z400)">sin cuenta</span>'
        dueno = f'<td class="cuenta-cel"><b>{e(d.get("creada_por") or "—")}</b>{marca}</td>'

    return f"""<tr>
<td class="cuenta-cel"><b>{e(persona)}</b><span>{e(ident)}</span></td>
<td class="cod">AG {e(d.get('ano_gravable', ''))}</td>
<td>{tag(sem, color, solido=(sem != '—'))}</td>
<td>{tag(est_texto, est_color)}</td>{dueno}
<td class="mono-t">{e(cuentas.hace_cuanto(d.get('creado_en')))}</td>
<td><div class="acc-fila">
  <a class="mini sec" href="/caso/{e(d['id'])}">Ver</a>
  <a class="mini sec" href="/admin/declaracion/{e(d['id'])}/eliminar">Eliminar</a>
</div></td></tr>"""


def vista_declaraciones(lista, usuario, token, error='', hecho=''):
    filas = ''.join(_fila_declaracion(d, token) for d in lista) or _sin_filas(
        'Todavía no hay declaraciones en la plataforma.', 7)
    cuerpo = f"""
<div class="seccion">
  <h2>Todas las declaraciones<span class="nota">{len(lista)} caso(s)</span></h2>
  <table><thead><tr>
    <th>Contribuyente</th><th style="width:88px">Año</th><th style="width:110px">Semáforo</th>
    <th style="width:120px">Estado</th><th style="width:150px">La cargó</th>
    <th style="width:120px">Cuándo</th><th style="width:150px"></th>
  </tr></thead><tbody>{filas}</tbody></table>
</div>
<div class="aviso"><b>Eliminar una declaración</b> se lleva su fila, sus alertas, el libro
de nueve hojas y la exógena que la originó. Si el contribuyente se queda sin ningún caso,
su ficha también desaparece: son un nombre y una cédula sujetos a reserva, y sin caso al
que pertenecer no hay razón para conservarlos. Eliminar libera cupo del usuario que la
había cargado.</div>"""
    return _pagina('Declaraciones', cuerpo, 'TODAS LAS DECLARACIONES', usuario,
                   'admin', 'declaraciones', error, hecho)


def vista_confirmar_declaracion(d, usuario, token, volver='/admin/declaraciones'):
    persona = (d.get('contribuyentes') or {}).get('nombre_titulo', 'Sin nombre')
    ident = (d.get('contribuyentes') or {}).get('identificacion', '')
    archivos = []
    if d.get('libro_path'):
        archivos.append('el libro de nueve hojas')
    if d.get('exogena_path'):
        archivos.append('la exógena que subió')
    lista_archivos = (' Se borrarán también ' + ' y '.join(archivos) + '.'
                      if archivos else '')
    cuerpo = f"""
<div class="migas"><a href="{e(volver)}">&larr; Volver</a></div>
<div class="peligro-caja">
  <h2>¿Eliminar esta declaración?</h2>
  <p><b>{e(persona)}</b> · {e(ident)} · año gravable <b>{e(d.get('ano_gravable', ''))}</b><br>
  La cargó <b>{e(d.get('creada_por') or '—')}</b>.</p>
  <p>Desaparecen la declaración y todas sus alertas.{e(lista_archivos)}
  Si es el único caso de este contribuyente, se elimina también su ficha.
  No hay papelera y la acción queda escrita en la bitácora a su nombre.</p>
  <form method="post" action="/admin/declaracion/{e(d['id'])}/eliminar">{_t(token)}
    <input type="hidden" name="volver" value="{e(volver)}">
    <button class="mini peligro firme" type="submit" style="padding:9px 15px">
      Sí, eliminarla definitivamente</button></form>
  <p style="margin-top:16px"><a href="{e(volver)}">No, cancelar</a></p>
</div>"""
    return _pagina('Eliminar declaración', cuerpo, 'CONFIRMAR LA ELIMINACIÓN',
                   usuario, 'admin', 'declaraciones')


# ── bitácora ────────────────────────────────────────────────────────────
def _fila_bitacora(b):
    texto, clase = ACCION_ET.get(b['accion'], (b['accion'].replace('_', ' '), ''))
    if not b.get('exito'):
        clase = 'mal'
    return f"""<tr class="{clase}">
<td class="mono-t" title="{e(cuentas.fecha_corta(b['ocurrido_en']))}">{e(cuentas.hace_cuanto(b['ocurrido_en']))}</td>
<td class="cuenta-cel"><b>{e(b.get('usuario') or '—')}</b></td>
<td>{e(texto)}</td>
<td class="detalle-cel">{e(b.get('objeto') or '')}
  {'<br><span style="color:var(--z400)">' + e(b['detalle']) + '</span>' if b.get('detalle') else ''}</td>
<td class="mono-t">{e(b.get('ip') or '—')}</td></tr>"""


def vista_bitacora(entradas, usuario, filtro_usuario='', filtro_accion='',
                   limite=200, error=''):
    filas = ''.join(_fila_bitacora(b) for b in entradas) or _sin_filas(
        'No hay movimientos que cumplan ese filtro.', 5)
    opciones = '<option value="">Todo</option>' + ''.join(
        f'<option value="{k}"{" selected" if filtro_accion == k else ""}>{e(v[0])}</option>'
        for k, v in sorted(ACCION_ET.items(), key=lambda x: x[1][0]))
    mas = ''
    if len(entradas) >= limite:
        mas = (f'<p style="text-align:center;margin-top:14px;font-size:12.5px">'
               f'<a href="/admin/bitacora?n={limite * 3}&usuario={e(filtro_usuario)}'
               f'&accion={e(filtro_accion)}">Ver más movimientos &darr;</a></p>')
    cuerpo = f"""
<form method="get" action="/admin/bitacora" class="filtros">
  <div class="campo"><label for="usuario">Cuenta</label>
    <input id="usuario" name="usuario" type="text" value="{e(filtro_usuario)}"
           placeholder="todas" autocapitalize="none" spellcheck="false"></div>
  <div class="campo"><label for="accion">Acción</label>
    <select id="accion" name="accion">{opciones}</select></div>
  <button class="mini sec" type="submit" style="padding:9px 15px">Filtrar</button>
  <a class="mini sec" href="/admin/bitacora" style="padding:9px 15px">Limpiar</a>
</form>
<div class="seccion">
  <h2>Bitácora<span class="nota">{len(entradas)} movimiento(s), del más reciente al más antiguo</span></h2>
  <table><thead><tr><th style="width:150px">Cuándo</th><th style="width:150px">Quién</th>
  <th style="width:230px">Qué</th><th>Sobre qué</th><th style="width:130px">Desde</th>
  </tr></thead><tbody>{filas}</tbody></table>
</div>{mas}
<div class="aviso"><b>Por qué existe esta bitácora.</b> Por aquí pasan declaraciones de
personas reales, amparadas por la reserva del artículo 583 del Estatuto Tributario. Saber
quién entró, qué miró y qué borró es parte de custodiarlas. Las filas en rojo son intentos
que no prosperaron: varios seguidos sobre la misma cuenta, desde direcciones distintas,
no son un olvido de contraseña.</div>"""
    return _pagina('Bitácora', cuerpo, 'REGISTRO DE ACTIVIDAD', usuario, 'admin',
                   'bitacora', error)


# ── ajustes ─────────────────────────────────────────────────────────────
def vista_ajustes(valores, usuario, token, error='', hecho=''):
    abierto = ' checked' if valores.get('registro_abierto') else ''
    aprobacion = ' checked' if valores.get('requiere_aprobacion') else ''
    cupo = valores.get('cupo_por_defecto', 1)
    mensaje = valores.get('mensaje_portada', '') or ''
    cuerpo = f"""
<div class="seccion">
  <h2>Registro de cuentas nuevas</h2>
  <div class="cuerpo">
    <form method="post" action="/admin/ajustes">{_t(token)}
      <label class="marca-check"><input type="checkbox" name="registro_abierto" value="1"{abierto}>
        <span><b>Permitir que cualquiera cree una cuenta</b><br>
        <span class="pista">Con esto apagado, la pantalla de acceso deja de ofrecer el
        registro y solo usted crea cuentas desde el panel.</span></span></label>

      <label class="marca-check" style="margin-top:16px">
        <input type="checkbox" name="requiere_aprobacion" value="1"{aprobacion}>
        <span><b>Las cuentas nuevas quedan pendientes de mi aprobación</b><br>
        <span class="pista">Quien se registre podrá crear su cuenta pero no entrará
        hasta que usted la active. Más control, más trabajo para usted.</span></span></label>

      <div class="rejilla" style="max-width:420px;margin-top:20px">
        <div class="campo"><label for="cupo_por_defecto">Cupo con el que nace una cuenta</label>
          <input id="cupo_por_defecto" name="cupo_por_defecto" type="number" min="0" max="1000"
                 value="{e(cupo)}">
          <span class="pista">Declaraciones que podrá procesar quien se registre, antes de
          que usted decida ampliárselo. Cero significa que se registra pero no procesa nada
          hasta que usted lo autorice.</span></div>
      </div>

      <div class="campo" style="margin-top:20px"><label for="mensaje_portada">
        Aviso en la bandeja</label>
        <textarea id="mensaje_portada" name="mensaje_portada" maxlength="500"
          placeholder="Por ejemplo: «Plazo de la DIAN para el año gravable 2025 …». Déjelo vacío para no mostrar nada.">{e(mensaje)}</textarea>
        <span class="pista">Lo ven todos los usuarios al entrar.</span></div>

      <button type="submit" style="margin-top:18px">Guardar los ajustes</button>
    </form>
  </div>
</div>
<div class="aviso"><b>Estos ajustes cambian el sitio al instante</b>, sin volver a
publicarlo. Cada cambio queda en la bitácora con su nombre y la hora.</div>"""
    return _pagina('Ajustes', cuerpo, 'AJUSTES DEL SISTEMA', usuario, 'admin',
                   'ajustes', error, hecho)


# ── mi cuenta (cualquier rol) ───────────────────────────────────────────
def vista_mi_cuenta(u, datos, token, error='', hecho=''):
    """La ficha propia. La ve cualquiera; nadie edita permisos desde aquí."""
    cupo = ('Sin límite' if u['cupo'] is None
            else f'{datos["usadas"]} de {u["cupo"]} declaraciones procesadas')
    barra = ''
    if u['cupo']:
        pct = min(100, int(datos['usadas'] * 100 / u['cupo']))
        barra = f'<div class="b" style="margin-top:7px"><i style="width:{pct}%"></i></div>'

    cuerpo = f"""
<div class="seccion">
  <h2>Mi cuenta<span class="nota">{tag_rol(u['rol'])} {tag_estado(u['estado'])}</span></h2>
  <div class="cuerpo"><div class="rejilla">
    <div class="campo"><label>Usuario</label><div>{e(u['usuario'])}</div></div>
    <div class="campo"><label>Nombre</label><div>{e(u['nombre'])}</div></div>
    <div class="campo"><label>Correo</label>
      <div>{e(u['correo']) if u.get('correo') else '—'}</div></div>
    <div class="campo"><label>Cuenta creada</label>
      <div>{e(cuentas.fecha_corta(u['creado_en']))}</div></div>
    <div class="campo"><label>Cupo</label>
      <div class="cupo-cel"><div class="txt">{e(cupo)}</div>{barra}</div></div>
    <div class="campo"><label>Declaraciones cargadas</label><div>{datos['usadas']}</div></div>
  </div></div>
</div>

<div class="seccion">
  <h2>Cambiar mi contraseña</h2>
  <div class="cuerpo">
    <p>Al cambiarla se cierran las sesiones abiertas en otros equipos. Si cree que
    alguien más la conoce, este es el camino.</p>
    <form method="post" action="/cuenta/clave">{_t(token)}
      <div class="rejilla" style="max-width:640px">
        <div class="campo"><label for="actual">Contraseña actual</label>
          <input id="actual" name="actual" type="password" required autocomplete="current-password"></div>
        <div class="campo"><label for="nueva">Contraseña nueva</label>
          <input id="nueva" name="nueva" type="password" required autocomplete="new-password"
                 minlength="{cuentas.MIN_CLAVE}">
          <span class="pista">Mínimo {cuentas.MIN_CLAVE} caracteres. Una frase que recuerde
          resiste más que ocho caracteres raros.</span></div>
        <div class="campo"><label for="repetir">Repítala</label>
          <input id="repetir" name="repetir" type="password" required autocomplete="new-password"></div>
      </div>
      <button type="submit" style="margin-top:16px">Cambiar la contraseña</button>
    </form>
  </div>
</div>

<div class="seccion">
  <h2>Últimos accesos a mi cuenta</h2>
  <table><thead><tr><th style="width:150px">Cuándo</th><th style="width:150px">Quién</th>
  <th style="width:230px">Qué</th><th>Sobre qué</th><th style="width:130px">Desde</th>
  </tr></thead><tbody>{''.join(_fila_bitacora(b) for b in datos['movimientos'])
                       or _sin_filas('Sin movimientos registrados.', 5)}</tbody></table>
</div>
<div class="aviso">Si ve aquí un acceso que no reconoce, cambie su contraseña de inmediato
y avísele al contador.</div>"""
    return _pagina('Mi cuenta', cuerpo, 'MI CUENTA', u['usuario'], u['rol'],
                   '', error, hecho)
