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
import permisos
import render
from render import e

VERDE, AMBAR, ROJO, AZUL, GRIS = (render.VERDE, render.AMBAR, render.ROJO,
                                  render.AZUL, render.GRIS)

ROL_COLOR = {'admin': ROJO, 'cliente': GRIS}
ROL_NOMBRE = {'admin': 'Administrador', 'cliente': 'Cliente'}
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
    'libro_rst_descargado': ('Libro RST descargado', ''),
    'recibo_rst_creado': ('Recibo RST cargado', ''),
    'recibo_rst_eliminado': ('Recibo RST eliminado', 'mal'),
    'descargo_aceptado': ('Aceptó el descargo', ''),
    'permiso_pedido': ('Pidió acceso a una cartera', ''),
    'permiso_concedido': ('Concedió acceso a su cartera', ''),
    'permiso_denegado': ('Negó el acceso a su cartera', ''),
    'permiso_revocado': ('Retiró el acceso a su cartera', 'mal'),
    'migracion_dueno': ('Cambio de dueño (migración)', ''),
    'ajuste': ('Ajuste del sistema', ''),
}

# Acciones cuyo «objeto» puede delatar a un contribuyente. Hoy ya no se escribe
# ahí ningún nombre —solo la referencia del caso—, pero la bitácora es un
# registro histórico y las filas de antes de agosto de 2026 sí lo llevan. Se
# tapan al mostrarlas: lo que se guardó no se puede desguardar, pero sí se
# puede dejar de enseñar.
ACCIONES_RESERVADAS = {
    'declaracion_creada', 'declaracion_eliminada', 'declaracion_estado',
    'libro_descargado', 'libro_rst_descargado', 'recibo_rst_creado',
    'recibo_rst_eliminado', 'descargo_aceptado',
}

ESTILO = """
/* ── PANEL ── */
.tarjetas{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
gap:14px;margin-bottom:26px}
.tj{background:var(--sup);border:1px solid var(--bord);border-radius:12px;padding:16px 18px;
box-shadow:var(--sombra)}
.tj .n{font-size:27px;font-weight:600;letter-spacing:-.03em;line-height:1.1;
font-variant-numeric:tabular-nums}
.tj .l{font-size:10px;letter-spacing:.13em;color:var(--z500);text-transform:uppercase;
margin-top:5px;font-weight:600}
.tj .p{font-size:11.5px;color:var(--z400);margin-top:7px;line-height:1.45}
.tj.v .n{color:var(--verde)}.tj.a .n{color:var(--ambar)}.tj.r .n{color:var(--rojo)}
.tj a{color:var(--z500);font-size:11.5px}

.seccion{background:var(--sup);border:1px solid var(--bord);border-radius:12px;
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

/* Los botones pequeños viven en `render.ESTILO`: los usa también la bandeja,
   desde que la franja de solicitudes de acceso salió del panel. */

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
font-family:inherit;background:var(--sup);color:var(--ink);box-shadow:var(--sombra);
transition:border-color .15s,box-shadow .15s}
.campo textarea{min-height:74px;resize:vertical;line-height:1.5}
.campo input:focus,.campo select:focus,.campo textarea:focus{outline:none;
border-color:var(--z400);box-shadow:0 0 0 3px rgba(161,161,170,.20)}
.campo input[disabled]{background:var(--z100);color:var(--z500)}
.marca-check{display:flex;align-items:center;gap:9px;font-size:13px;color:var(--text2);
margin-top:9px;cursor:pointer}
.marca-check input{width:16px;height:16px;accent-color:var(--tinta);cursor:pointer;flex:none}

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
.clave-nueva{background:var(--sup);border:1px solid var(--bord-2);border-radius:10px;
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
               ('/admin/uso', 'Uso', 'uso'),
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
            f'<div class="aviso" style="margin:0 0 22px;border-color:var(--ambar-b);'
            f'background:var(--ambar-f)"><b>{pendientes} cuenta{plural} '
            f'esperando aprobación.</b> Ninguna entra mientras no se active. '
            f'<a href="/admin/cuentas?estado=pendiente">Verlas ahora &rarr;</a></div>')

    bloqueadas = datos['bloqueadas']
    aviso_bloqueo = ''
    if bloqueadas:
        plural = 's' if bloqueadas != 1 else ''
        aviso_bloqueo = (
            f'<div class="aviso" style="margin:0 0 22px;border-color:var(--rojo-b);'
            f'background:var(--rojo-f)"><b>{bloqueadas} cuenta{plural} bloqueada{plural} '
            f'por intentos fallidos.</b> Puede tratarse de un olvido de contraseña o de '
            f'alguien probando claves. El detalle está en la bitácora.</div>')

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
<div class="aviso"><b>Qué se hace desde aquí.</b> En <a href="/admin/cuentas">Cuentas</a>
se aprueba, inhabilita o elimina una cuenta y se fija cuántas declaraciones puede
procesar. En <a href="/admin/uso">Uso</a> aparece cuántos casos lleva cada cuenta —el
número y nada más— y desde su ficha se le pide permiso para entrar a la cartera.
En <a href="/admin/ajustes">Ajustes</a> se abre o cierra el registro y se decide el cupo
con el que nace cada cuenta nueva. Todo movimiento queda escrito en la
<a href="/admin/bitacora">bitácora</a>, con quién y cuándo.</div>
<div class="aviso"><b>Lo que el panel no permite, a propósito.</b> Ver las declaraciones
de las demás cuentas. Son datos tributarios de personas reales, sujetos a la reserva del
art. 583 E.T., y quien responde por ellos es el contador que los cargó. Para entrar a
una cartera hay que <b>pedirle permiso a su titular</b>: él decide, decide por cuánto
tiempo, y puede retirarlo cuando quiera. Cada solicitud y cada permiso quedan en la
bitácora.</div>"""
    return _pagina('Panel', cuerpo, 'PANEL DE ADMINISTRACIÓN', usuario, 'admin',
                   'panel', error, hecho)


# ── cuentas ─────────────────────────────────────────────────────────────
def _fila_cuenta(u, usadas, yo, token):
    """Una cuenta en la tabla. Las acciones de aquí son las de un clic;
    lo demás vive en la ficha."""
    correo = f'<span>{e(u["correo"])}</span>' if u.get('correo') else \
             '<span style="color:var(--z400)">sin correo</span>'
    marca_yo = '<span class="yo">Sesión actual</span>' if yo else ''
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
Al llegar al tope, la cuenta sigue entrando y consultando lo suyo, pero no procesa más.
<b>Inhabilitar</b> deja la cuenta y sus declaraciones intactas y le cierra la sesión
en el acto; <b>eliminar</b>, en la ficha, es definitivo. El administrador no procesa
declaraciones y por eso nunca tiene cupo — y tampoco ve las de nadie sin permiso.</div>"""
    return _pagina('Cuentas', cuerpo, 'CUENTAS REGISTRADAS', usuario, 'admin',
                   'cuentas', error, hecho)


def _bloque_acceso(u, permiso, usadas, token, yo):
    """Qué puede saber el administrador de la cartera de esta cuenta.

    La respuesta corta es: **cuántos casos lleva, y nada más**. Ni el nombre de
    un contribuyente, ni una cédula, ni un año, ni una cifra. Son datos
    tributarios de terceros —reserva del art. 583 E.T.— y el titular de la
    cuenta es quien responde por ellos, no el dueño de la plataforma.

    Para entrar hay que pedírselo, y él concede por un tiempo limitado.
    """
    if yo:
        return ''
    estado = (permiso or {}).get('estado')
    vigente = permisos.Permisos.vigente(permiso)

    if vigente:
        cuadro = f"""<div class="ok-msg" style="margin:0">
Acceso concedido a esta cartera hasta el
<b>{e(cuentas.fecha_corta(permiso.get('expira_en')))}</b>
(lo concedió {e(cuentas.hace_cuanto(permiso.get('respondido_en')))}).
Después se cierra solo. El titular puede retirarlo antes cuando quiera.</div>
<p style="margin-top:14px"><a class="mini sec" href="/">Ir a la bandeja</a>
<span class="pista">Sus casos aparecen en la bandeja junto a los demás, marcados con
el nombre de la cuenta.</span></p>"""
    else:
        if estado == 'pendiente':
            aviso = ('<div class="aviso" style="margin:0 0 14px"><b>Solicitud '
                     'enviada.</b> Le aparece al titular en cuanto entre, con el motivo '
                     'escrito. Se puede volver a pedir con otro motivo.</div>')
        elif estado == 'denegado':
            aviso = ('<div class="aviso" style="margin:0 0 14px"><b>Solicitud '
                     'denegada por el titular.</b> Se puede volver a pedir.</div>')
        elif estado in ('revocado', 'concedido'):
            aviso = ('<div class="aviso" style="margin:0 0 14px">El acceso anterior '
                     '<b>ya no está vigente</b>: venció o el titular lo retiró.</div>')
        else:
            aviso = ''
        cuadro = f"""{aviso}
<form method="post" action="/admin/cuenta/{e(u['id'])}/permiso">{_t(token)}
  <div class="campo"><label for="motivo">Motivo de la solicitud</label>
    <input id="motivo" name="motivo" type="text" maxlength="400"
           placeholder="Ej.: revisar el caso que reportó por correo el 12 de agosto">
    <span class="pista">Lo lee el titular antes de decidir.</span></div>
  <button class="mini sec" type="submit" style="margin-top:14px">Pedir acceso a esta
  cartera</button>
</form>"""

    return f"""
<div class="seccion">
  <h2>Cartera de esta cuenta<span class="nota">{usadas} caso(s)</span></h2>
  <div class="cuerpo">
    <p>De las declaraciones de esta cuenta el panel informa <b>cuántas son</b>, y nada
    más: ni el nombre de un contribuyente, ni una cédula, ni las cifras. Son datos de
    terceros sujetos a reserva, y quien responde por ellos es el titular de la
    cuenta.</p>
    {cuadro}
  </div>
</div>"""


def vista_cuenta(u, datos, usuario, token, error='', hecho='', clave_nueva=''):
    """La ficha completa de una cuenta: todo lo que se le puede hacer."""
    yo = u['usuario'] == usuario
    usadas = datos['usadas']

    aviso_clave = ''
    if clave_nueva:
        aviso_clave = f"""<div class="seccion"><h2>Contraseña provisional</h2>
<div class="cuerpo"><div class="clave-nueva"><code>{e(clave_nueva)}</code>
<span>Debe entregarse a <b>{e(u['nombre'])}</b> por un medio seguro. No vuelve a
mostrarse y no queda guardada en ninguna parte: el sistema solo conserva su huella.
Al entrar se le exige cambiarla.</span></div></div></div>"""

    bloqueo = cuentas.desde_iso(u.get('bloqueado_hasta'))
    estado_seguridad = []
    if bloqueo and bloqueo > cuentas.ahora():
        estado_seguridad.append(
            f'<span class="mal">Bloqueada por intentos fallidos hasta '
            f'{e(cuentas.fecha_corta(u["bloqueado_hasta"]))}.</span>')
    if u.get('intentos_fallidos'):
        estado_seguridad.append(f'{u["intentos_fallidos"]} intento(s) fallido(s) sin acertar.')
    if u.get('debe_cambiar_clave'):
        estado_seguridad.append('Debe cambiar la contraseña al entrar.')
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
    nota_rol = ('<p class="pista">El rol de la cuenta en uso no se cambia desde aquí: '
                'una degradación por descuido dejaría el panel sin administrador.</p>'
                if yo else '')

    sin_limite = ' checked' if u['cupo'] is None else ''
    cuerpo_cupo = ('' if u['rol'] == 'cliente' else
                   '<p>Esta cuenta es de ' + e(cuentas.ROL_ET[u['rol']][0].lower()) +
                   ': no procesa declaraciones para terceros, así que el cupo no le '
                   'aplica. Al pasarla a cliente, el cupo queda disponible.</p>')

    bloque_acceso = _bloque_acceso(u, datos.get('permiso'), usadas, token, yo)

    marca_yo = ' <span class="yo">(sesión actual)</span>' if yo else ''
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
    <b>{usadas}</b>. Con el cupo por debajo de lo ya usado no se borra nada: la cuenta
    deja de cargar hasta que se le amplíe.</p>
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
          placeholder="Quién es, qué se acordó, por qué tiene ese cupo…">{e(u.get('notas') or '')}</textarea>
        <span class="pista">Solo las ve el administrador. El titular de la cuenta
        no.</span></div>
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
    exige cambiarla al entrar. El panel nunca muestra la contraseña de nadie: de todas
    se guarda únicamente una huella irreversible.</p>
  </div>
</div>

{bloque_acceso}

<div class="peligro-caja">
  <h2>Eliminar esta cuenta</h2>
  <p>Borra a <b>{e(u['usuario'])}</b> de forma definitiva. Sus {usadas} declaración(es)
  se conservan en la cartera: son papeles de trabajo de contribuyentes reales y no
  propiedad de quien las subió. No hay papelera para la cuenta.</p>
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
<form method="post" action="/admin/cuenta/{e(u['id'])}/eliminar">
  {_t(token)}<input type="hidden" name="declaraciones" value="conservar">
  <button class="mini peligro firme" type="submit" style="padding:9px 15px">
    Sí, eliminar la cuenta y conservar sus {n_decl} declaración(es)</button></form>"""
        explicacion = f"""<p>Esta cuenta ha cargado <b>{n_decl} declaración(es)</b>.
Se quedan donde están: son papeles de trabajo de contribuyentes reales, no propiedad de
quien las subió, y las declaraciones no se eliminan en ningún caso. Seguirán en la cartera
a nombre de un usuario que ya no existe, y el panel lo muestra tal cual.</p>"""
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
  <p>La acción es definitiva y queda escrita en la bitácora con el nombre de quien la
  ejecuta.</p>
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
    <p>Alta directa, sin que la persona pase por el registro. Con la contraseña en
    blanco, el sistema genera una provisional y la muestra una sola vez para poder
    entregarla; al entrar se le exige cambiarla.</p>
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
                 autocomplete="off" placeholder="se genera una si queda vacía">
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


# ── uso de la plataforma ────────────────────────────────────────────────
# Lo que ANTES era «todas las declaraciones», con nombre y cédula de cada
# contribuyente a la vista del administrador. Ya no: de la cartera ajena solo
# se informa **cuántos casos** lleva cada cuenta. Son datos tributarios de
# terceros y el titular de la cuenta es quien responde por ellos.
def _fila_uso(u, n_renta, n_rst, con_acceso):
    cupo = _cupo_celda(n_renta, u['cupo'])
    acceso = (tag('Con acceso', VERDE, solido=True) if con_acceso
              else '<span class="pista">—</span>')
    return f"""<tr>
<td class="cuenta-cel"><b>{e(u['usuario'])}</b><span>{e(u['nombre'])}</span></td>
<td>{tag_rol(u['rol'])}</td>
<td>{tag_estado(u['estado'])}</td>
<td class="n">{n_renta}</td>
<td class="n">{n_rst}</td>
<td>{cupo}</td>
<td>{acceso}</td>
<td class="mono-t">{e(cuentas.hace_cuanto(u.get('ultimo_acceso')))}</td>
<td><div class="acc-fila">
  <a class="mini sec" href="/admin/cuenta/{e(u['id'])}">Ver la cuenta</a>
</div></td></tr>"""


def vista_uso(lista, renta, rst, con_acceso, usuario, token, error='', hecho=''):
    """Cuántos casos lleva cada cuenta. Sin un solo dato de contribuyente."""
    permitidos = set(con_acceso or ())
    filas = ''.join(_fila_uso(u, renta.get(u['usuario'], 0), rst.get(u['usuario'], 0),
                              u['usuario'] in permitidos)
                    for u in lista) or _sin_filas('Todavía no hay cuentas.', 9)
    total_renta, total_rst = sum(renta.values()), sum(rst.values())
    # Casos cuyo dueño ya no tiene cuenta: se cuentan aparte para que los
    # totales cuadren y para que no pasen inadvertidos.
    conocidos = {u['usuario'] for u in lista}
    sueltos = sum(n for k, n in renta.items() if k not in conocidos)
    nota_sueltos = ('' if not sueltos else
                    f'<div class="aviso" style="margin-top:0"><b>{sueltos} '
                    f'declaración(es)</b> figuran a nombre de una cuenta que ya no '
                    f'existe. Nadie las ve. Para recuperarlas hay que volver a crear '
                    f'esa cuenta con el mismo nombre de usuario.</div>')
    cuerpo = f"""
<div class="seccion">
  <h2>Uso por cuenta<span class="nota">{total_renta} de renta &middot; {total_rst} de RST</span></h2>
  <table><thead><tr>
    <th>Cuenta</th><th style="width:120px">Rol</th><th style="width:110px">Estado</th>
    <th class="n" style="width:90px">Renta</th><th class="n" style="width:80px">RST</th>
    <th style="width:140px">Cupo</th><th style="width:120px">Acceso</th>
    <th style="width:120px">Último acceso</th><th style="width:130px"></th>
  </tr></thead><tbody>{filas}</tbody></table>
</div>
{nota_sueltos}
<div class="aviso"><b>De la cartera ajena, el panel muestra el número y nada más.</b>
Ni el nombre de un contribuyente, ni una cédula, ni un año, ni una cifra. Son datos
tributarios de terceros —reserva del art. 583 E.T.— y quien responde por ellos es el
titular de cada cuenta. Para entrar a una cartera hay que <b>pedirle permiso a su
titular</b> desde la ficha de la cuenta: él decide, y decide por cuánto tiempo.</div>
<div class="aviso"><b>Las declaraciones no se eliminan.</b> Una vez procesada, la
declaración queda y el cupo que consumió sigue consumido. Es deliberado: el cupo es lo
que se vende, y si borrar lo devolviera, una cuenta de cupo 1 podría procesar sin
límite subiendo, borrando y volviendo a subir. Para dejar de dar servicio a una cuenta
se la inhabilita; para ampliarla, se le sube el cupo desde su ficha.</div>"""
    return _pagina('Uso', cuerpo, 'USO DE LA PLATAFORMA, POR CUENTA', usuario,
                   'admin', 'uso', error, hecho)


# ── bitácora ────────────────────────────────────────────────────────────
def _fila_bitacora(b):
    texto, clase = ACCION_ET.get(b['accion'], (b['accion'].replace('_', ' '), ''))
    if not b.get('exito'):
        clase = 'mal'
    objeto = b.get('objeto') or ''
    if b.get('accion') in ACCIONES_RESERVADAS and not objeto.startswith(
            ('declaración ', 'recibo ')):
        # Fila vieja: ahí quedó escrito el nombre de un contribuyente. Se tapa.
        objeto = ('<span class="pista" title="Dato de un contribuyente: '
                  'sujeto a reserva">(reservado)</span>')
    else:
        objeto = e(objeto)
    return f"""<tr class="{clase}">
<td class="mono-t" title="{e(cuentas.fecha_corta(b['ocurrido_en']))}">{e(cuentas.hace_cuanto(b['ocurrido_en']))}</td>
<td class="cuenta-cel"><b>{e(b.get('usuario') or '—')}</b></td>
<td>{e(texto)}</td>
<td class="detalle-cel">{objeto}
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
<div class="aviso"><b>Qué registra la bitácora.</b> Por el sistema pasan declaraciones de
personas reales, amparadas por la reserva del artículo 583 del Estatuto Tributario: queda
anotado quién entró, qué consultó y qué eliminó. Las filas en rojo son intentos que no
prosperaron; varios seguidos sobre la misma cuenta, desde direcciones distintas, no son
un olvido de contraseña.</div>"""
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
        <span><b>Registro abierto al público</b><br>
        <span class="pista">Con esto apagado, la pantalla de acceso deja de ofrecer el
        registro y las cuentas se crean únicamente desde el panel.</span></span></label>

      <label class="marca-check" style="margin-top:16px">
        <input type="checkbox" name="requiere_aprobacion" value="1"{aprobacion}>
        <span><b>Cuentas nuevas por aprobación</b></span></label>

      <div class="rejilla" style="max-width:420px;margin-top:20px">
        <div class="campo"><label for="cupo_por_defecto">Cupo con el que nace una cuenta</label>
          <input id="cupo_por_defecto" name="cupo_por_defecto" type="number" min="0" max="1000"
                 value="{e(cupo)}">
          <span class="pista">Declaraciones que puede procesar una cuenta recién registrada,
          antes de que se le amplíe el cupo. En cero, la cuenta se registra pero no procesa
          nada hasta que se le autorice.</span></div>
      </div>

      <div class="campo" style="margin-top:20px"><label for="mensaje_portada">
        Aviso en la bandeja</label>
        <textarea id="mensaje_portada" name="mensaje_portada" maxlength="500"
          placeholder="Por ejemplo: «Plazo de la DIAN para el año gravable 2025 …». En blanco no se muestra nada.">{e(mensaje)}</textarea>
        <span class="pista">Lo ven todos los usuarios al entrar.</span></div>

      <button type="submit" style="margin-top:18px">Guardar los ajustes</button>
    </form>
  </div>
</div>
<div class="aviso"><b>Estos ajustes cambian el sitio al instante</b>, sin volver a
publicarlo. Cada cambio queda en la bitácora con el usuario y la hora.</div>"""
    return _pagina('Ajustes', cuerpo, 'AJUSTES DEL SISTEMA', usuario, 'admin',
                   'ajustes', error, hecho)


def _bloque_accesos_dados(concedidos, token):
    """Quién puede entrar hoy a MIS declaraciones, y el botón para cortarlo.

    Aparece siempre, aunque no haya nadie: que la respuesta sea «nadie» es
    justamente lo que el titular necesita poder comprobar de un vistazo.
    """
    if not concedidos:
        cuerpo = ('<p><b>Nadie.</b> Ninguna otra cuenta ve estas declaraciones. '
                  'Quien necesite entrar tiene que pedirlo, y la solicitud aparece '
                  'en la bandeja.</p>')
    else:
        filas = []
        for p in concedidos:
            if p.get('vigente'):
                cuando = (f'hasta el <b>{e(cuentas.fecha_corta(p.get("expira_en")))}</b>'
                          f' <span class="pista">'
                          f'(concedido {e(cuentas.hace_cuanto(p.get("respondido_en")))})'
                          f'</span>')
                marca = tag('Vigente', VERDE, solido=True)
            else:
                cuando = (f'<span class="pista">venció el '
                          f'{e(cuentas.fecha_corta(p.get("expira_en")))}</span>')
                marca = tag('Vencido', GRIS)
            filas.append(f"""<tr>
<td class="cuenta-cel"><b>{e(p['solicitante'])}</b></td>
<td>{marca}</td>
<td>{cuando}</td>
<td><form method="post" action="/permiso/{e(p['solicitante'])}/revocar">{_t(token)}
  <button class="mini peligro" type="submit">Retirar el acceso</button></form></td>
</tr>""")
        cuerpo = (f'<p>Estas cuentas han podido entrar a estas declaraciones. '
                  f'Retirar el acceso surte efecto <b>de inmediato</b>.</p>'
                  f'<table style="margin-top:12px"><thead><tr>'
                  f'<th>Cuenta</th><th style="width:110px">Estado</th>'
                  f'<th>Hasta cuándo</th><th style="width:160px"></th>'
                  f'</tr></thead><tbody>{"".join(filas)}</tbody></table>')
    return f"""
<div class="seccion">
  <h2>Quién más ve estas declaraciones</h2>
  <div class="cuerpo">{cuerpo}
    <p class="pista" style="margin-top:14px">Ni el administrador de la plataforma
    entra sin un permiso concedido desde aquí, y todo permiso vence solo.</p>
  </div>
</div>"""


# ── mi cuenta (cualquier rol) ───────────────────────────────────────────
def vista_mi_cuenta(u, datos, token, error='', hecho=''):
    """La ficha propia. La ve cualquiera; nadie edita permisos desde aquí."""
    cupo = ('Sin límite' if u['cupo'] is None
            else f'{datos["usadas"]} de {u["cupo"]} declaraciones procesadas')
    barra = ''
    if u['cupo']:
        pct = min(100, int(datos['usadas'] * 100 / u['cupo']))
        barra = f'<div class="b" style="margin-top:7px"><i style="width:{pct}%"></i></div>'
    accesos = _bloque_accesos_dados(datos.get('accesos') or [], token)

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

{accesos}

<div class="seccion">
  <h2>Cambiar la contraseña</h2>
  <div class="cuerpo">
    <p>Al cambiarla se cierran las sesiones abiertas en otros equipos.</p>
    <form method="post" action="/cuenta/clave">{_t(token)}
      <div class="rejilla" style="max-width:640px">
        <div class="campo"><label for="actual">Contraseña actual</label>
          <input id="actual" name="actual" type="password" required autocomplete="current-password"></div>
        <div class="campo"><label for="nueva">Contraseña nueva</label>
          <input id="nueva" name="nueva" type="password" required autocomplete="new-password"
                 minlength="{cuentas.MIN_CLAVE}">
          <span class="pista">Mínimo {cuentas.MIN_CLAVE} caracteres. Una frase larga
          resiste más que ocho caracteres sueltos.</span></div>
        <div class="campo"><label for="repetir">Repítala</label>
          <input id="repetir" name="repetir" type="password" required autocomplete="new-password"></div>
      </div>
      <button type="submit" style="margin-top:16px">Cambiar la contraseña</button>
    </form>
  </div>
</div>

<div class="seccion">
  <h2>Últimos accesos a la cuenta</h2>
  <table><thead><tr><th style="width:150px">Cuándo</th><th style="width:150px">Quién</th>
  <th style="width:230px">Qué</th><th>Sobre qué</th><th style="width:130px">Desde</th>
  </tr></thead><tbody>{''.join(_fila_bitacora(b) for b in datos['movimientos'])
                       or _sin_filas('Sin movimientos registrados.', 5)}</tbody></table>
</div>
<div class="aviso">Ante un acceso que no se reconozca: cambiar la contraseña de inmediato
y avisar al administrador.</div>"""
    return _pagina('Mi cuenta', cuerpo, 'MI CUENTA', u['usuario'], u['rol'],
                   '', error, hecho)
