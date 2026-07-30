# -*- coding: utf-8 -*-
r"""La puerta de entrada de RENTA IA.

Reproduce en HTML y CSS puros el diseño del componente React que pidió el
usuario —cabecera con la marca, líneas de acento que se dibujan solas,
partículas ascendentes en canvas, viñeta y tarjeta que sube al aparecer—,
pasado de la escala oscura (zinc-950) a la clara (zinc-50):

    fondo    #0A0A0B → #FAFAFA        texto     #FAFAFA → #18181B
    líneas   #27272A → #E4E4E7        tarjeta   zinc-900/70 → blanco/70
    botón    claro sobre oscuro → oscuro sobre claro

No se usa React ni Tailwind: el resto del sistema es Python que devuelve HTML,
y montar un front aparte solo para esta pantalla obligaría a mantener dos
aplicaciones. Todo va embebido, sin tipografías ni scripts externos, para que
la pantalla se pinte completa en la primera respuesta.
"""
import html


def e(t):
    return html.escape(str(t), quote=True)


ESTILO = """
:root{
  --z50:#FAFAFA; --z100:#F4F4F5; --z200:#E4E4E7; --z300:#D4D4D8;
  --z400:#A1A1AA; --z500:#71717A; --z600:#52525B; --z900:#18181B; --z950:#09090B;
  --rojo:#B42318; --rojo-fondo:#FEF3F2; --rojo-borde:#FECDCA;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{
  font-family:ui-sans-serif,system-ui,'Segoe UI',-apple-system,sans-serif;
  background:var(--z50); color:var(--z900); font-size:14px; line-height:1.5;
  -webkit-font-smoothing:antialiased;
}
.pantalla{position:fixed; inset:0; background:var(--z50); color:var(--z900); overflow:hidden}

/* viñeta */
.vineta{position:absolute; inset:0; pointer-events:none;
  background:radial-gradient(80% 60% at 50% 30%, rgba(9,9,11,.045), transparent 60%)}

/* líneas de acento que se dibujan */
.accent-lines{position:absolute; inset:0; pointer-events:none; opacity:.7}
.hline,.vline{position:absolute; background:var(--z200); will-change:transform,opacity}
.hline{left:0; right:0; height:1px; transform:scaleX(0); transform-origin:50% 50%;
  animation:drawX .8s cubic-bezier(.22,.61,.36,1) forwards}
.vline{top:0; bottom:0; width:1px; transform:scaleY(0); transform-origin:50% 0%;
  animation:drawY .9s cubic-bezier(.22,.61,.36,1) forwards}
.hline:nth-child(1){top:18%; animation-delay:.12s}
.hline:nth-child(2){top:50%; animation-delay:.22s}
.hline:nth-child(3){top:82%; animation-delay:.32s}
.vline:nth-child(4){left:22%; animation-delay:.42s}
.vline:nth-child(5){left:50%; animation-delay:.54s}
.vline:nth-child(6){left:78%; animation-delay:.66s}
.hline::after,.vline::after{content:""; position:absolute; inset:0; opacity:0;
  background:linear-gradient(90deg,transparent,rgba(9,9,11,.20),transparent);
  animation:shimmer .9s ease-out forwards}
.hline:nth-child(1)::after{animation-delay:.12s}
.hline:nth-child(2)::after{animation-delay:.22s}
.hline:nth-child(3)::after{animation-delay:.32s}
.vline:nth-child(4)::after{animation-delay:.42s}
.vline:nth-child(5)::after{animation-delay:.54s}
.vline:nth-child(6)::after{animation-delay:.66s}
@keyframes drawX{0%{transform:scaleX(0);opacity:0}60%{opacity:.95}100%{transform:scaleX(1);opacity:.7}}
@keyframes drawY{0%{transform:scaleY(0);opacity:0}60%{opacity:.95}100%{transform:scaleY(1);opacity:.7}}
@keyframes shimmer{0%{opacity:0}35%{opacity:.25}100%{opacity:0}}

canvas#particulas{position:absolute; inset:0; width:100%; height:100%;
  opacity:.55; mix-blend-mode:multiply; pointer-events:none}

/* cabecera */
header{position:absolute; left:0; right:0; top:0; display:flex; align-items:center;
  justify-content:space-between; padding:16px 24px;
  border-bottom:1px solid rgba(228,228,231,.8); z-index:2;
  background:rgba(250,250,250,.55); backdrop-filter:blur(6px)}
.marca-min{font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--z500)}
.marca-min b{color:var(--z900); font-weight:600}
.btn-contacto{display:inline-flex; align-items:center; gap:8px; height:36px; padding:0 14px;
  border-radius:8px; border:1px solid var(--z200); background:#fff; color:var(--z900);
  font-size:14px; font-weight:500; text-decoration:none; transition:background .15s,border-color .15s}
.btn-contacto:hover{background:var(--z100); border-color:var(--z300)}
.btn-contacto svg{width:16px; height:16px}

/* centro */
.centro{height:100%; width:100%; display:grid; place-items:center; padding:16px; position:relative; z-index:1}

/* tarjeta */
.card{
  width:100%; max-width:384px; border:1px solid var(--z200); border-radius:12px;
  background:rgba(255,255,255,.72); backdrop-filter:blur(10px);
  box-shadow:0 1px 2px rgba(9,9,11,.05), 0 24px 48px -28px rgba(9,9,11,.25);
  opacity:0; transform:translateY(20px);
  animation:fadeUp .8s cubic-bezier(.22,.61,.36,1) .4s forwards;
}
@keyframes fadeUp{to{opacity:1; transform:translateY(0)}}
.card-header{padding:24px 24px 0; display:flex; flex-direction:column; gap:6px}
.card-header h1{font-size:24px; font-weight:600; letter-spacing:-.02em; line-height:1.15}
.card-header p{font-size:14px; color:var(--z500)}
.card-content{padding:24px; display:grid; gap:20px}
.card-footer{padding:0 24px 24px; display:flex; align-items:center; justify-content:center;
  font-size:14px; color:var(--z500)}
.card-footer b{color:var(--z900); font-weight:500; margin-left:4px}

/* campos */
.grupo{display:grid; gap:8px}
.grupo > label{font-size:14px; font-weight:500; color:var(--z600); line-height:1}
.rel{position:relative; display:flex; align-items:center}
.rel > .ic{position:absolute; left:12px; width:16px; height:16px; color:var(--z400); pointer-events:none}
.rel input{
  width:100%; height:40px; border-radius:8px; border:1px solid var(--z200); background:#fff;
  padding:8px 12px 8px 38px; font-family:inherit; font-size:14px; color:var(--z900);
  box-shadow:0 1px 2px rgba(9,9,11,.04); transition:border-color .15s, box-shadow .15s;
}
.rel input::placeholder{color:var(--z400)}
.rel input:focus{outline:none; border-color:var(--z400); box-shadow:0 0 0 3px rgba(161,161,170,.20)}
.rel.clave input{padding-right:40px}
.ojo{position:absolute; right:6px; display:grid; place-items:center; width:30px; height:30px;
  border:none; background:none; border-radius:6px; color:var(--z400); cursor:pointer;
  transition:color .15s, background .15s}
.ojo:hover{color:var(--z600); background:var(--z100)}
.ojo:focus-visible{outline:2px solid var(--z400); outline-offset:-2px}
.ojo svg{width:16px; height:16px}
svg{fill:none; stroke:currentColor; stroke-width:2; stroke-linecap:round; stroke-linejoin:round}

/* recordarme + ayuda */
.fila{display:flex; align-items:center; justify-content:space-between; gap:12px}
.recordar{display:flex; align-items:center; gap:8px}
.recordar input{appearance:none; -webkit-appearance:none; width:16px; height:16px; flex:none;
  border:1px solid var(--z300); border-radius:4px; background:#fff; cursor:pointer;
  display:grid; place-items:center; transition:background .15s, border-color .15s}
.recordar input:checked{background:var(--z900); border-color:var(--z900)}
.recordar input:checked::after{content:""; width:9px; height:5px; border:2px solid #fff;
  border-top:0; border-right:0; transform:rotate(-45deg) translate(1px,-1px)}
.recordar input:focus-visible{outline:2px solid var(--z400); outline-offset:2px}
.recordar label{font-size:14px; color:var(--z500); cursor:pointer}
.fila .ayuda{font-size:14px; color:var(--z600); text-decoration:none}
.fila .ayuda:hover{color:var(--z900); text-decoration:underline}

/* botón principal */
button.continuar{
  width:100%; height:40px; border:none; border-radius:8px; cursor:pointer;
  background:var(--z900); color:var(--z50); font-family:inherit; font-size:14px; font-weight:500;
  transition:background .15s, transform .12s;
}
button.continuar:hover{background:#27272A}
button.continuar:active{transform:translateY(1px)}
button.continuar:focus-visible{outline:2px solid var(--z900); outline-offset:2px}
button.continuar[disabled]{opacity:.6; cursor:progress}

/* avisos */
.error{display:flex; gap:8px; align-items:flex-start; background:var(--rojo-fondo);
  border:1px solid var(--rojo-borde); color:var(--rojo); border-radius:8px;
  padding:10px 12px; font-size:13px; animation:temblar .4s cubic-bezier(.36,.07,.19,.97) both}
@keyframes temblar{10%,90%{transform:translateX(-1px)}20%,80%{transform:translateX(2px)}
  30%,50%,70%{transform:translateX(-4px)}40%,60%{transform:translateX(4px)}}
.mayus{font-size:12.5px; color:var(--z600); background:var(--z100); border:1px solid var(--z200);
  border-radius:8px; padding:8px 11px; display:none}
.mayus.ver{display:block}
.reserva{font-size:11.5px; color:var(--z400); text-align:center; line-height:1.6}

/* pantallas con más campos que la de acceso */
.card.ancha{max-width:470px}
.centro.alto{align-items:start; padding:88px 16px 40px; overflow-y:auto}
.par{display:grid; grid-template-columns:1fr 1fr; gap:14px}
.rel.simple input{padding-left:12px}
.ok-aviso{display:flex; gap:8px; align-items:flex-start; background:#F3F8F5;
  border:1px solid #CFE3D8; color:#14532D; border-radius:8px; padding:10px 12px; font-size:13px}
.medidor{height:4px; background:var(--z200); border-radius:3px; overflow:hidden; margin-top:2px}
.medidor i{display:block; height:100%; width:0; background:var(--z400);
  transition:width .2s, background .2s}
.medidor.f1 i{width:25%; background:#B42318} .medidor.f2 i{width:50%; background:#8D6209}
.medidor.f3 i{width:75%; background:#1D5A8C} .medidor.f4 i{width:100%; background:#1C6F43}
.fuerza-txt{font-size:11.5px; color:var(--z500)}
.reglas{font-size:11.5px; color:var(--z500); line-height:1.6; margin-top:-2px}
.volver{text-align:center; font-size:13px; margin-top:2px}
.volver a{color:var(--z600)}

@media(prefers-reduced-motion:reduce){
  *,*::before,*::after{animation:none !important; transition:none !important}
  .card{opacity:1; transform:none}
  .hline{transform:scaleX(1)} .vline{transform:scaleY(1)}
  canvas#particulas{display:none}
}
@media(max-width:420px){
  .card-header{padding:20px 18px 0} .card-content{padding:18px} .card-footer{padding:0 18px 18px}
  header{padding:12px 16px}
  .par{grid-template-columns:1fr}
}
"""

IC_USUARIO = ('<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">'
              '<circle cx="12" cy="8" r="4"/><path d="M20 21a8 8 0 0 0-16 0"/></svg>')
IC_CANDADO = ('<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">'
              '<rect width="18" height="11" x="3" y="11" rx="2"/>'
              '<path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>')
IC_FLECHA = ('<svg viewBox="0 0 24 24" aria-hidden="true">'
             '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>')
IC_OJO = ('<svg id="ojo-abierto" viewBox="0 0 24 24" aria-hidden="true">'
          '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/>'
          '<circle cx="12" cy="12" r="3"/></svg>'
          '<svg id="ojo-cerrado" viewBox="0 0 24 24" aria-hidden="true" style="display:none">'
          '<path d="M10.7 5.1A10.9 10.9 0 0 1 12 5c6.5 0 10 7 10 7a18 18 0 0 1-2.4 3.4"/>'
          '<path d="M6.6 6.6A18 18 0 0 0 2 12s3.5 7 10 7a10.8 10.8 0 0 0 5.4-1.4"/>'
          '<path d="M2 2l20 20"/></svg>')

GUION_FONDO = """
(function(){
  // ── partículas ascendentes ────────────────────────────────────
  var lienzo = document.getElementById('particulas');
  var ctx = lienzo && lienzo.getContext('2d');
  var quieto = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (ctx && !quieto) {
    var ps = [], raf = 0;
    function medir(){ lienzo.width = window.innerWidth; lienzo.height = window.innerHeight; }
    function nueva(){
      return { x: Math.random() * lienzo.width, y: Math.random() * lienzo.height,
               v: Math.random() * 0.25 + 0.05, o: Math.random() * 0.22 + 0.08 };
    }
    function iniciar(){
      ps = [];
      var n = Math.floor((lienzo.width * lienzo.height) / 9000);
      for (var i = 0; i < n; i++) ps.push(nueva());
    }
    function pintar(){
      ctx.clearRect(0, 0, lienzo.width, lienzo.height);
      for (var i = 0; i < ps.length; i++) {
        var p = ps[i];
        p.y -= p.v;
        if (p.y < 0) {
          p.x = Math.random() * lienzo.width;
          p.y = lienzo.height + Math.random() * 40;
          p.v = Math.random() * 0.25 + 0.05;
          p.o = Math.random() * 0.22 + 0.08;
        }
        // en claro las partículas son tinta, no luz
        ctx.fillStyle = 'rgba(24,24,27,' + p.o + ')';
        ctx.fillRect(p.x, p.y, 0.7, 2.2);
      }
      raf = requestAnimationFrame(pintar);
    }
    medir(); iniciar(); raf = requestAnimationFrame(pintar);
    window.addEventListener('resize', function(){ medir(); iniciar(); });
  }

})();
"""

# Solo tiene sentido donde hay una contraseña que escribir; las tres pantallas
# (acceso, registro y cambio) comparten este comportamiento.
GUION_CLAVE = """
(function(){
  // ── mostrar u ocultar la contraseña ───────────────────────────
  var f = document.getElementById('f'), b = document.getElementById('b'),
      c = document.getElementById('clave'), ojo = document.getElementById('ojo'),
      mayus = document.getElementById('mayus');
  if (!c || !ojo) return;
  ojo.addEventListener('click', function(){
    var oculta = c.type === 'password';
    c.type = oculta ? 'text' : 'password';
    ojo.setAttribute('aria-pressed', oculta);
    ojo.setAttribute('aria-label', oculta ? 'Ocultar la contraseña' : 'Mostrar la contraseña');
    document.getElementById('ojo-abierto').style.display = oculta ? 'none' : '';
    document.getElementById('ojo-cerrado').style.display = oculta ? '' : 'none';
    c.focus();
  });

  // El bloqueo de mayúsculas es la causa más común de un acceso que "no sirve".
  function revisar(ev){
    var activo = ev.getModifierState && ev.getModifierState('CapsLock');
    mayus.classList.toggle('ver', !!activo);
  }
  c.addEventListener('keydown', revisar);
  c.addEventListener('keyup', revisar);
  c.addEventListener('blur', function(){ mayus.classList.remove('ver'); });

  if (f && b) f.addEventListener('submit', function(ev){
    if (f.usuario && (!f.usuario.value.trim() || !f.clave.value)) { ev.preventDefault(); return; }
    b.disabled = true; b.textContent = b.dataset.esperando || 'Verificando…';
  });
})();
"""

# Medidor de fuerza y aviso de contraseñas que no coinciden. Es una ayuda visual:
# la validación de verdad la hace el servidor, que es el único que no se puede
# saltar desde el navegador.
GUION_FUERZA = """
(function(){
  var c = document.getElementById('clave'), r = document.getElementById('repetir'),
      m = document.getElementById('medidor'), t = document.getElementById('fuerza'),
      avisoR = document.getElementById('aviso-repetir');
  if (!c || !m) return;
  var nombres = ['Muy débil','Débil','Aceptable','Buena','Fuerte'];
  function medir(){
    var v = c.value, p = 0;
    if (v.length >= 10) p++;
    if (v.length >= 14) p++;
    var distintos = {}; for (var i = 0; i < v.length; i++) distintos[v[i]] = 1;
    if (Object.keys(distintos).length >= 8) p++;
    var clases = 0;
    if (/[a-záéíóúñ]/.test(v)) clases++;
    if (/[A-ZÁÉÍÓÚÑ]/.test(v)) clases++;
    if (/[0-9]/.test(v)) clases++;
    if (/[^a-zA-Z0-9áéíóúñÁÉÍÓÚÑ]/.test(v)) clases++;
    if (clases >= 3) p++;
    m.className = 'medidor f' + (v ? p : 0);
    t.textContent = v ? nombres[p] : '';
    comparar();
  }
  function comparar(){
    if (!r || !avisoR) return;
    avisoR.textContent = (r.value && r.value !== c.value)
      ? 'Las dos contraseñas no coinciden.' : '';
    avisoR.style.color = '#B42318';
  }
  c.addEventListener('input', medir);
  if (r) r.addEventListener('input', comparar);
})();
"""


CORREO = 'santiagotrek2@gmail.com'


def _marco(titulo, tarjeta, guiones=(), ancha=False, alto=False):
    """El fondo compartido por las tres pantallas de fuera de la aplicación.

    Las líneas, las partículas y la cabecera son las mismas siempre; lo único
    que cambia es la tarjeta del centro. Así entrar, registrarse y cambiar la
    contraseña se sienten el mismo sitio y no tres formularios sueltos.
    """
    scripts = ''.join(f'<script>{g}</script>' for g in guiones)
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="theme-color" content="#FAFAFA">
<title>{e(titulo)} · RENTA IA</title><style>{ESTILO}</style></head><body>
<section class="pantalla">
  <div class="vineta"></div>
  <div class="accent-lines">
    <div class="hline"></div><div class="hline"></div><div class="hline"></div>
    <div class="vline"></div><div class="vline"></div><div class="vline"></div>
  </div>
  <canvas id="particulas"></canvas>

  <header>
    <span class="marca-min"><b>RENTA IA</b></span>
    <a class="btn-contacto" href="mailto:{CORREO}?subject=Acceso%20a%20RENTA%20IA">
      <span>Contacto</span>{IC_FLECHA}</a>
  </header>

  <div class="centro{' alto' if alto else ''}">{tarjeta}</div>
</section>{scripts}
</body></html>"""


def _error(mensaje):
    return (f'<div class="error" role="alert"><span aria-hidden="true">&#9888;</span>'
            f'<span>{e(mensaje)}</span></div>') if mensaje else ''


def _hecho(mensaje):
    return (f'<div class="ok-aviso" role="status"><span aria-hidden="true">&#10003;</span>'
            f'<span>{e(mensaje)}</span></div>') if mensaje else ''


def _campo_clave(id_campo, etiqueta, autocomplete='current-password',
                 con_ojo=True, autofocus=False, placeholder='••••••••'):
    ojo = (f'<button type="button" class="ojo" id="ojo" aria-pressed="false"'
           f' aria-label="Mostrar la contraseña">{IC_OJO}</button>') if con_ojo else ''
    return f"""<div class="grupo">
  <label for="{id_campo}">{e(etiqueta)}</label>
  <div class="rel clave">{IC_CANDADO}
    <input id="{id_campo}" name="{id_campo}" type="password" placeholder="{placeholder}"
           required autocomplete="{autocomplete}" {'autofocus' if autofocus else ''}>
    {ojo}
  </div>
</div>"""


def pagina(mensaje='', usuario='', registro_abierto=False, hecho=''):
    """La pantalla de acceso. `mensaje` se muestra como error si viene."""
    pie = ('¿No tiene cuenta?<b><a href="/registrarse" style="color:inherit">'
           'Regístrese aquí</a></b>' if registro_abierto else
           '¿No tiene acceso?<b>Solicítelo al contador</b>')
    tarjeta = f"""<form class="card" method="post" action="/entrar" id="f" novalidate>
      <div class="card-header">
        <h1>Bienvenido de nuevo</h1>
        <p>Ingrese a su cuenta</p>
      </div>

      <div class="card-content">
        {_hecho(hecho)}{_error(mensaje)}
        <div class="grupo">
          <label for="usuario">Usuario</label>
          <div class="rel">{IC_USUARIO}
            <input id="usuario" name="usuario" type="text" placeholder="su usuario" required
                   autocomplete="username" autocapitalize="none" autocorrect="off"
                   spellcheck="false" value="{e(usuario)}" {'' if usuario else 'autofocus'}>
          </div>
        </div>

        {_campo_clave('clave', 'Contraseña', autofocus=bool(usuario))}
        <div class="mayus" id="mayus">Bloqueo de mayúsculas activado.</div>

        <div class="fila">
          <span class="recordar">
            <input type="checkbox" id="recordar" name="recordar" value="1">
            <label for="recordar">Recordarme</label>
          </span>
          <a class="ayuda" href="mailto:{CORREO}?subject=Clave%20de%20RENTA%20IA">
            ¿Olvidó su contraseña?</a>
        </div>

        <button type="submit" class="continuar" id="b">Continuar</button>

        <p class="reserva">Información tributaria sujeta a reserva.<br>
          El acceso queda registrado.</p>
      </div>

      <div class="card-footer">{pie}</div>
    </form>"""
    return _marco('Acceso', tarjeta, (GUION_FONDO, GUION_CLAVE))


def pagina_registro(mensaje='', valores=None, min_clave=10, aprobacion=False):
    """Alta de una cuenta nueva desde la calle.

    Se piden pocos datos a propósito: el usuario, con qué entrar y por dónde
    avisarle. Lo demás —rol y cupo— lo decide el sistema, nunca el formulario.
    """
    v = valores or {}
    nota_final = ('Su cuenta quedará <b>a la espera de aprobación</b>: el contador '
                  'la revisa y le avisa por correo.' if aprobacion else
                  'Podrá entrar de inmediato. El número de declaraciones que puede '
                  'procesar lo fija el contador.')
    tarjeta = f"""<form class="card ancha" method="post" action="/registrarse" id="f" novalidate>
      <div class="card-header">
        <h1>Crear una cuenta</h1>
        <p>Para preparar su declaración de renta</p>
      </div>

      <div class="card-content">
        {_error(mensaje)}
        <div class="par">
          <div class="grupo">
            <label for="usuario">Usuario</label>
            <div class="rel">{IC_USUARIO}
              <input id="usuario" name="usuario" type="text" placeholder="juan.perez" required
                     autocomplete="username" autocapitalize="none" autocorrect="off"
                     spellcheck="false" maxlength="32" value="{e(v.get('usuario', ''))}" autofocus>
            </div>
          </div>
          <div class="grupo">
            <label for="telefono">Teléfono <span style="font-weight:400;color:#A1A1AA">(opcional)</span></label>
            <div class="rel simple">
              <input id="telefono" name="telefono" type="text" placeholder="300 000 0000"
                     autocomplete="tel" maxlength="40" value="{e(v.get('telefono', ''))}">
            </div>
          </div>
        </div>

        <div class="grupo">
          <label for="nombre">Nombre completo</label>
          <div class="rel simple">
            <input id="nombre" name="nombre" type="text" placeholder="Juan Pérez Gómez" required
                   autocomplete="name" maxlength="120" value="{e(v.get('nombre', ''))}">
          </div>
        </div>

        <div class="grupo">
          <label for="correo">Correo electrónico</label>
          <div class="rel simple">
            <input id="correo" name="correo" type="email" placeholder="juan@ejemplo.com" required
                   autocomplete="email" autocapitalize="none" spellcheck="false"
                   maxlength="160" value="{e(v.get('correo', ''))}">
          </div>
        </div>

        {_campo_clave('clave', 'Contraseña', 'new-password', placeholder='mínimo %d caracteres' % min_clave)}
        <div class="medidor" id="medidor"><i></i></div>
        <div class="fuerza-txt" id="fuerza"></div>
        <div class="mayus" id="mayus">Bloqueo de mayúsculas activado.</div>
        <p class="reglas">Al menos {min_clave} caracteres. Una frase que recuerde
        —«mesa verde 2026 sol»— resiste mucho más que ocho caracteres raros.
        No puede contener su usuario ni su nombre.</p>

        {_campo_clave('repetir', 'Repita la contraseña', 'new-password', con_ojo=False)}
        <div class="fuerza-txt" id="aviso-repetir"></div>

        <button type="submit" class="continuar" id="b" data-esperando="Creando la cuenta…">
          Crear la cuenta</button>

        <p class="reserva">{nota_final}<br>
          Sus datos quedan amparados por la reserva del artículo 583 del Estatuto Tributario.</p>
      </div>

      <div class="card-footer">¿Ya tiene cuenta?<b><a href="/entrar" style="color:inherit">Entre aquí</a></b></div>
    </form>"""
    return _marco('Crear una cuenta', tarjeta,
                  (GUION_FONDO, GUION_CLAVE, GUION_FUERZA), ancha=True, alto=True)


def pagina_clave(usuario, token, mensaje='', min_clave=10):
    """Cambio obligatorio: la cuenta entró con una contraseña que le asignaron.

    No se deja seguir a ninguna otra página hasta que la cambie. Una clave que
    pasó por un tercero —aunque ese tercero sea el contador— no es un secreto.
    """
    tarjeta = f"""<form class="card" method="post" action="/clave" id="f" novalidate>
      <input type="hidden" name="_t" value="{e(token)}">
      <div class="card-header">
        <h1>Elija su contraseña</h1>
        <p>Entró con una contraseña provisional</p>
      </div>

      <div class="card-content">
        {_error(mensaje)}
        <p class="reglas" style="margin:0">La contraseña con la que acaba de entrar se la
        asignó el administrador, así que él la conoce. Elija una que solo sepa usted;
        es la última pantalla antes de continuar.</p>

        {_campo_clave('actual', 'Contraseña provisional', 'current-password',
                      con_ojo=False, autofocus=True)}
        {_campo_clave('clave', 'Contraseña nueva', 'new-password',
                      placeholder='mínimo %d caracteres' % min_clave)}
        <div class="medidor" id="medidor"><i></i></div>
        <div class="fuerza-txt" id="fuerza"></div>
        <div class="mayus" id="mayus">Bloqueo de mayúsculas activado.</div>

        {_campo_clave('repetir', 'Repita la contraseña nueva', 'new-password', con_ojo=False)}
        <div class="fuerza-txt" id="aviso-repetir"></div>

        <button type="submit" class="continuar" id="b" data-esperando="Guardando…">
          Guardar y continuar</button>

        <p class="reserva">Al cambiarla se cierran las sesiones abiertas en otros equipos.</p>
      </div>

      <div class="card-footer">Sesión de<b>{e(usuario)}</b></div>
    </form>"""
    return _marco('Cambiar la contraseña', tarjeta,
                  (GUION_FONDO, GUION_CLAVE, GUION_FUERZA), alto=True)
