# -*- coding: utf-8 -*-
r"""La puerta de entrada de RENTA IA.

Es lo primero que ve alguien del sistema, así que se aparta de la paleta verde
del libro y trabaja en blanco con acentos dorados: papel, tinta y filo de oro.

Todo el CSS va aquí dentro, sin tipografías ni archivos externos, porque la
pantalla debe pintarse completa en la primera respuesta — cualquier descarga
extra se nota justo en el momento en que el usuario está esperando.
"""
import html


def e(t):
    return html.escape(str(t), quote=True)


ESTILO = """
:root{
  --tinta:#1C1B18; --tinta-2:#3A3833; --gris:#6E6A61; --gris-2:#96918A;
  --oro:#B08D3F; --oro-claro:#D9BE86; --oro-palido:#F3E9D2; --oro-brillo:#E7D3A1;
  --papel:#FFFFFF; --fondo:#FBF9F5; --linea:#EBE5D9;
  --error:#9B2C2C; --error-fondo:#FDF3F3; --error-borde:#F0D5D5;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{
  font-family:'Segoe UI',system-ui,-apple-system,sans-serif;
  background:var(--fondo); color:var(--tinta);
  font-size:15px; line-height:1.5;
  display:grid; place-items:center; padding:24px;
  -webkit-font-smoothing:antialiased;
  position:relative; overflow-x:hidden;
}
/* halo dorado tenue: da profundidad sin ensuciar el blanco */
body::before{
  content:''; position:fixed; inset:0; pointer-events:none; z-index:0;
  background:
    radial-gradient(720px 420px at 50% -10%, rgba(217,190,134,.28), transparent 62%),
    radial-gradient(540px 340px at 92% 104%, rgba(176,141,63,.12), transparent 64%);
}
.marco{position:relative; z-index:1; width:100%; max-width:412px}

/* ── membrete ── */
.membrete{text-align:center; margin-bottom:26px; animation:surgir .55s cubic-bezier(.2,.7,.3,1) both}
.sello{
  width:60px; height:60px; margin:0 auto 16px; border-radius:16px;
  background:linear-gradient(145deg,#F7EEDA,#E3CB96 46%,#B08D3F);
  display:grid; place-items:center;
  font-family:Georgia,'Times New Roman',serif; font-weight:700; font-size:27px;
  color:#4A3714;
  box-shadow:0 10px 26px rgba(176,141,63,.28), inset 0 1px 0 rgba(255,255,255,.75);
}
.wordmark{font-family:Georgia,'Times New Roman',serif; font-size:31px; font-weight:700;
  letter-spacing:-.4px; line-height:1.1}
.wordmark span{
  background:linear-gradient(96deg,#C9A227,#A87F27 52%,#D9BE86);
  -webkit-background-clip:text; background-clip:text; color:transparent;
}
.lema{color:var(--gris); font-size:12.6px; margin-top:8px; letter-spacing:.01em}

/* ── tarjeta ── */
.tarjeta{
  background:var(--papel); border:1px solid var(--linea); border-radius:18px;
  padding:34px 32px 28px; position:relative; overflow:hidden;
  box-shadow:0 1px 2px rgba(28,27,24,.04), 0 18px 44px -22px rgba(28,27,24,.22);
  animation:surgir .6s .08s cubic-bezier(.2,.7,.3,1) both;
}
/* filo de oro superior */
.tarjeta::before{
  content:''; position:absolute; top:0; left:0; right:0; height:2px;
  background:linear-gradient(90deg,transparent,var(--oro-claro) 18%,var(--oro) 50%,var(--oro-claro) 82%,transparent);
}
h1{font-family:Georgia,serif; font-size:20.5px; font-weight:700; letter-spacing:-.2px}
.intro{color:var(--gris); font-size:13.2px; margin:7px 0 24px}

/* ── campos con etiqueta flotante ── */
.campo{position:relative; margin-bottom:15px}
.campo input{
  width:100%; font-family:inherit; font-size:15px; color:var(--tinta);
  background:#fff; border:1px solid var(--linea); border-radius:11px;
  padding:23px 15px 9px; transition:border-color .18s, box-shadow .18s, background .18s;
}
.campo input::placeholder{color:transparent}
.campo label{
  position:absolute; left:16px; top:16px; color:var(--gris-2); font-size:14.5px;
  pointer-events:none; transition:all .16s cubic-bezier(.2,.7,.3,1);
}
.campo input:focus{
  outline:none; border-color:var(--oro-claro); background:#FFFDF8;
  box-shadow:0 0 0 3.5px rgba(217,190,134,.26);
}
.campo input:focus + label,
.campo input:not(:placeholder-shown) + label{
  top:8px; font-size:10.5px; letter-spacing:.09em; text-transform:uppercase;
  font-weight:700; color:var(--oro);
}
.campo.clave input{padding-right:50px; letter-spacing:.02em}
.ojo{
  position:absolute; right:7px; top:50%; transform:translateY(-50%);
  width:38px; height:38px; border:none; background:none; cursor:pointer;
  border-radius:9px; color:var(--gris-2); display:grid; place-items:center;
  transition:color .15s, background .15s;
}
.ojo:hover{color:var(--oro); background:var(--oro-palido)}
.ojo:focus-visible{outline:2px solid var(--oro-claro); outline-offset:-2px}
.ojo svg{width:19px; height:19px; fill:none; stroke:currentColor; stroke-width:1.7;
  stroke-linecap:round; stroke-linejoin:round}

/* ── botón ── */
button.entrar{
  width:100%; margin-top:9px; padding:13px 20px; border:none; border-radius:11px;
  font-family:inherit; font-size:14.6px; font-weight:600; letter-spacing:.015em;
  color:#FDFBF6; cursor:pointer; position:relative; overflow:hidden;
  background:linear-gradient(180deg,#2B2926,#1C1B18);
  box-shadow:0 1px 0 rgba(255,255,255,.06) inset, 0 8px 20px -10px rgba(28,27,24,.6);
  transition:transform .14s, box-shadow .2s, filter .2s;
}
button.entrar::after{  /* barrido dorado al pasar el cursor */
  content:''; position:absolute; inset:0; opacity:0; transition:opacity .25s;
  background:linear-gradient(100deg,transparent 18%,rgba(217,190,134,.24) 50%,transparent 82%);
}
button.entrar:hover{transform:translateY(-1px);
  box-shadow:0 10px 24px -10px rgba(176,141,63,.65), 0 0 0 1px rgba(176,141,63,.5)}
button.entrar:hover::after{opacity:1}
button.entrar:active{transform:translateY(0)}
button.entrar:focus-visible{outline:2px solid var(--oro); outline-offset:2px}
button.entrar[disabled]{filter:saturate(.4) opacity(.7); cursor:progress; transform:none}

/* ── avisos ── */
.error{
  background:var(--error-fondo); border:1px solid var(--error-borde); color:var(--error);
  border-radius:11px; padding:11px 14px; font-size:13px; margin-bottom:18px;
  display:flex; gap:9px; align-items:flex-start;
  animation:temblar .4s cubic-bezier(.36,.07,.19,.97) both;
}
.error b{font-weight:700}
.mayus{
  margin-top:9px; font-size:12.2px; color:#8A6D1F; background:var(--oro-palido);
  border:1px solid var(--oro-brillo); border-radius:9px; padding:8px 12px; display:none;
}
.mayus.ver{display:block; animation:surgir .2s both}
.reserva{
  margin-top:22px; padding-top:17px; border-top:1px solid var(--linea);
  font-size:11.6px; color:var(--gris-2); line-height:1.65; text-align:center;
}
.pie{text-align:center; margin-top:20px; font-size:11.4px; color:var(--gris-2);
  animation:surgir .6s .16s both}

@keyframes surgir{from{opacity:0; transform:translateY(11px)} to{opacity:1; transform:none}}
@keyframes temblar{
  10%,90%{transform:translateX(-1px)} 20%,80%{transform:translateX(2px)}
  30%,50%,70%{transform:translateX(-4px)} 40%,60%{transform:translateX(4px)}
}
@media(prefers-reduced-motion:reduce){
  *,*::before,*::after{animation:none !important; transition:none !important}
}
@media(max-width:420px){
  .tarjeta{padding:28px 22px 24px; border-radius:15px}
  .wordmark{font-size:27px}
}
"""

OJO = """<svg viewBox="0 0 24 24" aria-hidden="true"><path class="o1"
d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z"/>
<circle class="o1" cx="12" cy="12" r="2.7"/>
<path class="o2" style="display:none" d="M3 3l18 18"/></svg>"""


def pagina(mensaje='', usuario=''):
    """La pantalla de acceso. `mensaje` se muestra como error si viene."""
    error = (f'<div class="error" role="alert"><span aria-hidden="true">&#9888;</span>'
             f'<span>{e(mensaje)}</span></div>') if mensaje else ''
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="theme-color" content="#FBF9F5">
<title>Acceso · RENTA IA</title><style>{ESTILO}</style></head><body>
<main class="marco">
  <div class="membrete">
    <div class="sello" aria-hidden="true">R</div>
    <div class="wordmark">RENTA<span> IA</span></div>
    <p class="lema">Declaraciones de renta de personas naturales,<br>
      desde la exógena de la DIAN</p>
  </div>

  <div class="tarjeta">
    <h1>Acceso al sistema</h1>
    <p class="intro">Ingrese con las credenciales que le entregó el contador.</p>
    {error}
    <form method="post" action="/entrar" id="f" novalidate>
      <div class="campo">
        <input type="text" id="u" name="usuario" placeholder=" " required
               autocomplete="username" autocapitalize="none" autocorrect="off"
               spellcheck="false" value="{e(usuario)}" {'' if usuario else 'autofocus'}>
        <label for="u">Usuario</label>
      </div>
      <div class="campo clave">
        <input type="password" id="c" name="clave" placeholder=" " required
               autocomplete="current-password" {'autofocus' if usuario else ''}>
        <label for="c">Contraseña</label>
        <button type="button" class="ojo" id="ojo" aria-label="Mostrar la contraseña"
                aria-pressed="false" tabindex="0">{OJO}</button>
      </div>
      <div class="mayus" id="mayus">Bloqueo de mayúsculas activado.</div>
      <button type="submit" class="entrar" id="b">Entrar</button>
    </form>
    <p class="reserva">Información tributaria sujeta a reserva.<br>
      El acceso queda registrado.</p>
  </div>
  <p class="pie">RENTA IA · el contador revisa y libera antes de presentar</p>
</main>
<script>
(function(){{
  var f=document.getElementById('f'), b=document.getElementById('b'),
      c=document.getElementById('c'), ojo=document.getElementById('ojo'),
      mayus=document.getElementById('mayus');

  ojo.addEventListener('click', function(){{
    var oculta = c.type === 'password';
    c.type = oculta ? 'text' : 'password';
    ojo.setAttribute('aria-pressed', oculta);
    ojo.setAttribute('aria-label', oculta ? 'Ocultar la contraseña' : 'Mostrar la contraseña');
    ojo.querySelector('.o2').style.display = oculta ? '' : 'none';
    c.focus();
  }});

  // El bloqueo de mayúsculas es la causa más común de un login que "no sirve".
  function revisarMayus(ev){{
    var activo = ev.getModifierState && ev.getModifierState('CapsLock');
    mayus.classList.toggle('ver', !!activo);
  }}
  c.addEventListener('keydown', revisarMayus);
  c.addEventListener('keyup', revisarMayus);
  c.addEventListener('blur', function(){{ mayus.classList.remove('ver'); }});

  f.addEventListener('submit', function(ev){{
    if(!f.usuario.value.trim() || !f.clave.value){{ ev.preventDefault(); return; }}
    b.disabled = true; b.textContent = 'Verificando…';
  }});
}})();
</script>
</body></html>"""
