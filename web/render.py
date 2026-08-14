# -*- coding: utf-8 -*-
r"""La interfaz de RENTA IA: una sola definición del HTML.

La usan la bandeja local (`web\app.py`, casos de `clientes\`) y la web publicada
en Vercel (`api\index.py`, casos de Supabase). Ambas entregan casos con la misma
forma —persona, ano, ref, calc, C— así que el diseño no se duplica ni se
desincroniza entre las dos.

Identidad: la misma de la pantalla de acceso (`web\login.py`) —escala de grises
zinc sobre blanco, líneas de un píxel, tipografía del sistema con interletraje
cerrado— para que entrar y trabajar se sientan la misma aplicación. El color
queda reservado para lo único que lo necesita: el semáforo del caso.
"""
import html

import legal
import perfil as mod_perfil

MARCA = 'RENTA IA'
LEMA = 'Declaraciones de renta de personas naturales, desde la exógena de la DIAN'

VERDE, AMBAR, ROJO, AZUL, GRIS = '#1C6F43', '#8D6209', '#B42318', '#1D5A8C', '#71717A'
TINTA = '#18181B'

SEM = {
    'VERDE':    (VERDE, 'Listo para revisar',   'Los topes de la DIAN cuadran y no hay alertas altas'),
    'AMARILLO': (AMBAR, 'Alertas por resolver', 'Los topes cuadran, pero hay hallazgos de severidad ALTA'),
    'ROJO':     (ROJO,  'No liberar',           'Los totales no reconstruyen los topes: clasificación incompleta'),
}
SEM_CORTO = {'VERDE': 'LISTO', 'AMARILLO': 'CON ALERTAS', 'ROJO': 'NO LIBERAR'}
SEV_COLOR = {'ALTA': ROJO, 'MEDIA': AMBAR, 'VERIFICADO': VERDE,
             'NORMATIVO': AZUL, 'INFORMATIVO': GRIS}
ESTADO_ET = {'borrador': (GRIS, 'Borrador'),
             'en_revision': (AZUL, 'En revisión'),
             'liberada': (VERDE, 'Liberada')}


def pesos(v):
    s = '−' if v < 0 else ''
    return f'{s}$ {abs(int(round(v))):,}'.replace(',', '.')


def e(t):
    return html.escape(str(t), quote=True)


def iniciales(nombre):
    palabras = [p for p in str(nombre).split() if len(p) > 2]
    return ''.join(p[0] for p in palabras[:2]).upper() or '?'


def agrupar(lista):
    """Agrupa los casos por contribuyente, año más reciente primero."""
    grupos = {}
    for c in lista:
        g = grupos.setdefault(c['persona'], {'persona': c['persona'], 'filas': []})
        g['filas'].append(c)
        if 'C' in c and 'ident' not in g:
            g['ident'] = c['C'].get('identificacion', '—')
            g['titulo'] = c['C'].get('nombre_titulo', c['persona'])
    for g in grupos.values():
        g.setdefault('ident', '—')
        g.setdefault('titulo', g['persona'])
        g['filas'].sort(key=lambda x: x['ano'], reverse=True)
    return sorted(grupos.values(), key=lambda g: g['titulo'])


ESTILO = """
/* Todo el color del sitio vive en estas variables, y solo aquí. Por eso el
   modo oscuro cabe en un bloque al final que redefine los mismos nombres: no
   hay un color suelto en ninguna regla que se quede claro cuando el resto se
   apaga. `--sup` es la superficie de tarjetas y tablas —lo que antes era un
   #fff a mano— y `--sobre-tinta` es el texto que va encima del color fuerte,
   que en oscuro se invierte con él. */
:root{
--tinta:#18181B;--tinta-2:#27272A;--sobre-tinta:#FFFFFF;--sup:#FFFFFF;
--z50:#FAFAFA;--z100:#F4F4F5;--z200:#E4E4E7;--z300:#D4D4D8;--z400:#A1A1AA;
--z500:#71717A;--z600:#52525B;
--verde:#1C6F43;--ambar:#8D6209;--rojo:#B42318;
--rojo-f:#FEF3F2;--rojo-b:#FECDCA;--verde-f:#F3F8F5;--verde-b:#CFE3D8;
--ambar-f:#FDFAF1;--ambar-b:#EADFC0;--ambar-t:#7A5309;
--ink:var(--tinta);--muted:var(--z500);--text2:var(--z600);
--bord:var(--z200);--bord-2:var(--z300);--zebra:var(--z50);--fondo:var(--z50);
--sombra:0 1px 2px rgba(9,9,11,.04);
color-scheme:light;
}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-font-smoothing:antialiased}
body{font-family:ui-sans-serif,system-ui,'Segoe UI',-apple-system,'Helvetica Neue',sans-serif;
background:var(--fondo);color:var(--ink);font-size:14.5px;line-height:1.55}
h1,h2,h3{font-weight:600;letter-spacing:-.018em;line-height:1.25}
a{color:var(--ink);text-underline-offset:2px}

/* ── CABECERA ── */
.hero{background:var(--sup);border-bottom:1px solid var(--bord);position:relative}
.hero-in{max-width:1120px;margin:0 auto;padding:26px 28px 22px;position:relative;z-index:1}
.marca{display:flex;align-items:center;gap:14px}
.logo{width:40px;height:40px;border-radius:10px;background:var(--tinta);color:var(--sobre-tinta);
display:grid;place-items:center;font-size:16px;font-weight:600;letter-spacing:-.02em;flex:none}
.wordmark{font-size:25px;font-weight:600;letter-spacing:-.032em;line-height:1.1}
.wordmark span{color:var(--z400);font-weight:500}
.lema{color:var(--z500);font-size:12.8px;margin-top:3px}
.hero-sub{color:var(--z400);font-size:10.5px;font-weight:600;letter-spacing:.14em;
text-transform:uppercase;margin-top:16px}
.quien{position:absolute;right:28px;top:28px;z-index:2;text-align:right;color:var(--z500);font-size:12px}
.quien b{color:var(--ink);display:block;font-size:13px;font-weight:600}
.quien a{color:var(--z500)}
.quien a:hover{color:var(--ink)}
.quien .rolete{display:inline-block;font-size:9.5px;font-weight:600;letter-spacing:.08em;
text-transform:uppercase;color:var(--z500);border:1px solid var(--bord);border-radius:20px;
padding:1px 8px;margin-top:3px}

/* ── PESTAÑAS ── */
.nav-wrap{max-width:1120px;margin:0 auto;padding:0 28px}
.nav{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:-1px}
.nav a{padding:10px 14px;font-size:13px;color:var(--z500);text-decoration:none;
border-bottom:2px solid transparent;white-space:nowrap;transition:color .15s}
.nav a:hover{color:var(--ink)}
.nav a.act{color:var(--ink);font-weight:600;border-bottom-color:var(--tinta)}
.stats{display:flex;margin-top:20px;border-top:1px solid var(--bord);padding-top:16px;flex-wrap:wrap}
.stat{padding-right:32px;margin-right:32px;border-right:1px solid var(--bord)}
.stat:last-child{border-right:none;margin-right:0;padding-right:0}
.stat .n{font-size:24px;font-weight:600;line-height:1.1;letter-spacing:-.03em;
font-variant-numeric:tabular-nums}
.stat .l{font-size:10px;letter-spacing:.13em;color:var(--z500);text-transform:uppercase;
margin-top:4px;font-weight:600}
.stat.v .n{color:var(--verde)}.stat.a .n{color:var(--ambar)}.stat.r .n{color:var(--rojo)}

/* Las cifras del encabezado son enlaces: cada una filtra la lista de abajo. */
a.stat{text-decoration:none;color:inherit;border-radius:8px;padding-top:2px;
transition:background .15s}
a.stat:hover{background:var(--z100)}
a.stat.act{background:var(--z100);box-shadow:inset 0 -2px 0 var(--tinta)}

.wrap{max-width:1120px;margin:26px auto 60px;padding:0 28px}

/* ── FILTROS Y ORDEN ── */
.filtros-bar{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:14px}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip-f{display:inline-block;font-size:12px;text-decoration:none;color:var(--text2);
background:var(--sup);border:1px solid var(--bord);border-radius:20px;padding:5px 12px;
transition:border-color .15s,color .15s,background .15s;white-space:nowrap}
.chip-f:hover{border-color:var(--z400);color:var(--ink)}
.chip-f.act{background:var(--tinta);color:var(--sobre-tinta);border-color:var(--tinta);
font-weight:500}
.orden{display:flex;align-items:center;gap:8px;margin-left:auto}
.orden label{font-size:11.5px;color:var(--muted);white-space:nowrap}
.orden select{border:1px solid var(--bord);border-radius:8px;padding:7px 11px;
font-size:12.8px;font-family:inherit;background:var(--sup);color:var(--ink)}
.plazo{display:inline-block;margin-left:10px;font-size:11px;color:var(--muted);
border:1px solid var(--bord);border-radius:20px;padding:1px 9px;white-space:nowrap}
.plazo.cerca{color:var(--ambar);border-color:var(--ambar-b)}
.plazo.vencido{color:var(--rojo);border-color:var(--rojo-b)}

/* Para lectores de pantalla: rótulo que existe pero no se ve. */
.oculto{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
clip:rect(0 0 0 0);white-space:nowrap;border:0}

/* ── SUBIDA ── */
.subir{background:var(--sup);border:1px solid var(--bord);border-radius:12px;padding:22px 24px;
margin-bottom:26px;box-shadow:var(--sombra)}
.subir h2{font-size:18px}
.subir p{font-size:13.2px;color:var(--text2);margin:6px 0 16px;max-width:82ch}
.zona{display:block;border:1px dashed var(--bord-2);background:var(--z50);padding:26px;
text-align:center;border-radius:10px;cursor:pointer;transition:border-color .15s,background .15s}
.zona:hover,.zona.hover{border-color:var(--z400);background:var(--z100)}
.zona input{display:none}
.zona .ic{font-size:24px;line-height:1;opacity:.5}
.zona .txt{font-size:13.8px;color:var(--text2);margin-top:8px}
.zona.hover .txt{color:var(--ink)}
.zona .arch{font-weight:600;color:var(--ink);margin-top:7px;font-size:13px}
button{margin-top:16px;background:var(--tinta);color:var(--sobre-tinta);border:none;font-size:13.5px;font-weight:500;
padding:10px 20px;border-radius:8px;cursor:pointer;font-family:inherit;
transition:background .15s,transform .12s}
button:hover{background:var(--tinta-2)}
button:active{transform:translateY(1px)}
button:disabled{background:var(--z400);cursor:progress;transform:none}
.pasos{display:flex;gap:7px;font-size:11.5px;color:var(--muted);margin-top:15px;flex-wrap:wrap}
.pasos span{background:var(--z50);border:1px solid var(--bord);padding:4px 11px;border-radius:20px}
.cupo{margin-top:15px;font-size:12.5px;color:var(--text2);background:var(--z50);
border:1px solid var(--bord);border-radius:9px;padding:11px 14px}
.cupo b{color:var(--ink);font-weight:600}
.barrita{height:5px;background:var(--z200);border-radius:4px;margin-top:9px;overflow:hidden}
.barrita i{display:block;height:100%;background:var(--tinta)}

/* botones pequeños dentro de las tablas y fichas */
.acc-fila{display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end}
.acc-fila form{display:inline}
button.mini,a.mini{margin-top:0;padding:6px 11px;font-size:12px;border-radius:7px;
font-weight:500;display:inline-block;text-decoration:none;line-height:1.35;
font-family:inherit;border:1px solid transparent;cursor:pointer}
button.sec,a.mini.sec{background:var(--sup);color:var(--ink);border-color:var(--bord-2)}
button.sec:hover,a.mini.sec:hover{background:var(--z100);border-color:var(--z400)}
button.peligro{background:var(--sup);color:var(--rojo);border-color:var(--rojo-b)}
button.peligro:hover{background:var(--rojo-f);border-color:var(--rojo)}
button.peligro.firme{background:var(--rojo);color:#fff;border-color:var(--rojo)}
button.peligro.firme:hover{background:#93231A}

/* ── ALERTAS QUE SE MARCAN COMO RESUELTAS ── */
tr.resuelta td{background:var(--verde-f)}
tr.resuelta td b{color:var(--z600);font-weight:600}
.nota-res{margin-top:8px;font-size:12.2px;color:var(--verde);border-left:2px solid var(--verde-b);
padding-left:10px;line-height:1.5}
.nota-res b{color:var(--verde)!important}
form.marcar{display:flex;gap:7px;margin-top:10px;flex-wrap:wrap;align-items:center}
form.marcar input[type=text]{flex:1;min-width:190px;border:1px solid var(--bord);
border-radius:7px;padding:6px 10px;font-size:12.3px;font-family:inherit;
background:var(--sup);color:var(--ink)}
form.marcar input[type=text]:focus{outline:none;border-color:var(--z400);
box-shadow:0 0 0 3px rgba(161,161,170,.20)}
button:disabled.mini{background:var(--sup);color:var(--z400);border-color:var(--bord);
cursor:not-allowed}

/* ── PANTALLA DE CONFIRMACIÓN ── */
.conf-caja{background:var(--sup);border:1px solid var(--bord);border-radius:12px;
padding:18px 20px;margin-bottom:16px;box-shadow:var(--sombra)}
.conf-tit{font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;
font-weight:600;color:var(--z500);margin-bottom:14px;display:flex;
align-items:center;gap:9px;flex-wrap:wrap}
.conf-rej{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:16px}
.cf .l{font-size:9.5px;letter-spacing:.12em;color:var(--z400);font-weight:600;
text-transform:uppercase}
.cf .v{font-size:15.5px;font-weight:600;margin-top:3px;letter-spacing:-.01em;
font-variant-numeric:tabular-nums;word-break:break-word}
.cf .v.fav{color:var(--verde)}
.conf-pie{font-size:12.4px;color:var(--text2);margin-top:14px;line-height:1.55;max-width:86ch}
.pregunta{display:grid;grid-template-columns:1fr 120px 240px;gap:12px;align-items:center;
padding:11px 0;border-top:1px solid var(--z100)}
.pregunta:first-of-type{border-top:none}
.pregunta .q{font-size:13.3px}
.pregunta select,.pregunta input{border:1px solid var(--bord);border-radius:8px;
padding:8px 11px;font-size:13px;font-family:inherit;background:var(--sup);color:var(--ink);
width:100%}
.pregunta select:focus,.pregunta input:focus{outline:none;border-color:var(--z400);
box-shadow:0 0 0 3px rgba(161,161,170,.20)}
@media(max-width:700px){.pregunta{grid-template-columns:1fr;gap:8px}}

/* ── SOLICITUDES DE ACCESO ── */
/* Sale antes que nada en la bandeja: decidir quién ve declaraciones ajenas no
   es un aviso más, y no debe poder pasarse por alto. */
.peticiones{background:var(--sup);border:1px solid var(--ambar);border-left:3px solid var(--ambar);
border-radius:12px;padding:20px 22px;margin-bottom:22px;box-shadow:var(--sombra)}
.peticiones h2{font-size:16.5px;color:var(--ambar)}
.peticiones>.pista{font-size:12.8px;color:var(--text2);margin:6px 0 4px}
.peticion{display:flex;align-items:center;gap:14px;flex-wrap:wrap;
border-top:1px solid var(--bord);margin-top:14px;padding-top:14px}
.peticion:first-of-type{border-top:none;margin-top:8px;padding-top:0}
.peticion-txt{flex:1;min-width:260px;font-size:13.4px;line-height:1.5}
.peticion-txt i{color:var(--text2)}
.peticion-acc{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.peticiones .pista{font-size:11.8px;color:var(--muted)}

/* ── BUSCADOR ── */
.barra{display:flex;align-items:center;gap:14px;margin-bottom:14px;flex-wrap:wrap}
.barra h2{font-size:19px;flex:1}
.barra .cuenta{font-size:12.5px;color:var(--muted)}
#q{border:1px solid var(--bord);border-radius:8px;padding:9px 13px;font-size:13.5px;
font-family:inherit;width:270px;background:var(--sup);color:var(--ink);box-shadow:var(--sombra);
transition:border-color .15s,box-shadow .15s}
#q::placeholder{color:var(--z400)}
#q:focus{outline:none;border-color:var(--z400);box-shadow:0 0 0 3px rgba(161,161,170,.20)}

/* ── FICHA DE CONTRIBUYENTE ── */
.persona{background:var(--sup);border:1px solid var(--bord);border-radius:12px;margin-bottom:14px;
overflow:hidden;box-shadow:var(--sombra)}
.p-cab{display:flex;align-items:center;gap:14px;padding:16px 20px;border-bottom:1px solid var(--bord)}
.mono{width:40px;height:40px;border-radius:10px;background:var(--z100);color:var(--z600);
border:1px solid var(--bord);display:grid;place-items:center;font-weight:600;font-size:13.5px;flex:none}
.p-cab h3{font-size:17px}
.p-cab .cc{font-size:12.5px;color:var(--muted);margin-top:2px;font-variant-numeric:tabular-nums}
.p-cab .anos{margin-left:auto;font-size:11.5px;color:var(--z400);white-space:nowrap}
.ano{display:grid;grid-template-columns:132px 1fr auto;gap:18px;align-items:center;
padding:14px 20px;border-bottom:1px solid var(--z100)}
.ano:last-child{border-bottom:none}
.ano:hover{background:var(--z50)}
.ag{font-weight:600;font-size:15.5px;letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.ag .pt{display:inline-block;margin-right:8px;font-size:10px;line-height:1;
vertical-align:1px}
.ag .est{display:block;font-size:9.5px;letter-spacing:.1em;font-weight:600;margin-top:4px}
.cifras{display:flex;gap:30px;flex-wrap:wrap}
.cif .l{font-size:9.5px;letter-spacing:.12em;color:var(--z400);font-weight:600;text-transform:uppercase}
.cif .v{font-size:15px;font-weight:600;margin-top:3px;letter-spacing:-.01em;
font-variant-numeric:tabular-nums}
.cif .v.fav{color:var(--verde)}
.acc{display:flex;gap:8px;white-space:nowrap}
a.btn{display:inline-block;background:var(--tinta);color:var(--sobre-tinta);text-decoration:none;font-size:12.5px;
font-weight:500;padding:8px 14px;border-radius:8px;transition:background .15s}
a.btn:hover{background:var(--tinta-2)}
a.btn.sec{background:var(--sup);color:var(--ink);border:1px solid var(--bord-2)}
a.btn.sec:hover{background:var(--z100);border-color:var(--z400)}
.alertitas{font-size:11.5px;color:var(--muted);margin-top:6px}
.pill{display:inline-block;font-size:9.5px;font-weight:600;letter-spacing:.06em;padding:2px 8px;
border-radius:20px;border:1px solid currentColor;margin-left:8px;vertical-align:2px}

/* ── DETALLE ── */
.migas{font-size:13px;margin-bottom:16px}
.migas a{color:var(--text2);text-decoration:none}
.migas a:hover{color:var(--ink);text-decoration:underline}
.cinta{display:flex;align-items:center;gap:14px;background:var(--sup);border:1px solid var(--bord);
border-left:3px solid var(--sem);border-radius:12px;padding:15px 18px;margin-bottom:22px;
flex-wrap:wrap;box-shadow:var(--sombra)}
.cinta .tit{font-weight:600;font-size:14.5px;color:var(--sem)}
.cinta .des{font-size:12.8px;color:var(--text2);flex:1}
table{border-collapse:collapse;width:100%;background:var(--sup);border:1px solid var(--bord);
border-radius:12px;overflow:hidden;margin:8px 0 22px;box-shadow:var(--sombra)}
caption{text-align:left;font-size:10px;letter-spacing:.14em;font-weight:600;color:var(--z500);
padding:0 2px 9px;text-transform:uppercase}
th{background:var(--z50);color:var(--z600);font-size:10.5px;text-align:left;padding:11px 14px;
font-weight:600;letter-spacing:.11em;text-transform:uppercase;border-bottom:1px solid var(--bord)}
td{padding:10px 14px;border-bottom:1px solid var(--z100);font-size:13.5px}
tr:last-child td{border-bottom:none}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
th.n{text-align:right}
td.cod{white-space:nowrap;font-variant-numeric:tabular-nums}
td b{font-weight:600}
.chip{font-size:9.5px;font-weight:600;color:#fff;padding:3px 9px;border-radius:20px;
white-space:nowrap;letter-spacing:.05em}
.ok{color:var(--verde);font-weight:600}.mal{color:var(--rojo);font-weight:600}
.aviso{background:var(--z50);border:1px solid var(--bord);border-radius:10px;padding:14px 17px;
font-size:12.8px;color:var(--text2);margin-top:22px;line-height:1.6}
.aviso b{color:var(--ink);font-weight:600}
.err{background:var(--rojo-f);border:1px solid var(--rojo-b);border-radius:10px;color:#7A271A;
padding:13px 17px;font-size:13.5px;margin-bottom:20px}
.ok-msg{background:var(--verde-f);border:1px solid var(--verde-b);border-radius:10px;color:#14532D;
padding:13px 17px;font-size:13.5px;margin-bottom:16px;white-space:pre-line}
.vacio{background:var(--sup);border:1px dashed var(--bord-2);border-radius:12px;padding:44px;
text-align:center;color:var(--muted);font-size:14px}
footer{margin:40px 0 24px;text-align:center;font-size:11.5px;color:var(--z400);line-height:1.7}
footer b{color:var(--z600);font-weight:600}
@media(max-width:760px){
  .ano{grid-template-columns:1fr;gap:10px}
  .quien{position:static;text-align:left;margin-top:12px}
  .stat{padding-right:20px;margin-right:20px}
}

/* ── FILO DE COLOR POR APARTADO ──
   Los libros de Excel ya distinguen los dos regímenes por color: verde
   petróleo el de renta, azul el del SIMPLE. La web usaba el mismo zinc para
   los dos y solo cambiaba la pestaña subrayada. Este filo reutiliza una señal
   que el usuario ya tiene aprendida del entregable. */
.filo{height:3px;width:100%}
.filo.renta{background:#0D6E64}
.filo.rst{background:#1F3864}

/* ── INTERRUPTOR DE MODO OSCURO ── */
.tema{position:absolute;right:28px;bottom:14px;z-index:3;background:none;border:none;
margin:0;padding:5px 8px;border-radius:7px;cursor:pointer;color:var(--z500);
font-size:15px;line-height:1;transition:background .15s,color .15s}
.tema:hover{background:var(--z100);color:var(--ink)}
.tema:focus-visible{outline:2px solid var(--z400);outline-offset:2px}

/* ── FOCO VISIBLE ──
   El teclado tiene que poder recorrer el sitio. Sin esto, tabular por la
   bandeja es avanzar a ciegas. */
a:focus-visible,button:focus-visible,select:focus-visible,
input:focus-visible,textarea:focus-visible{outline:2px solid var(--z400);
outline-offset:2px;border-radius:4px}

/* ── IMPRESIÓN ──
   El detalle de un caso se imprime o se guarda en PDF para archivarlo. Sin
   esto salía con cabecera, pestañas y botones — y sin el descargo, que es
   justamente lo que tiene que quedar en el papel. */
@media print{
  :root{--sup:#fff;--fondo:#fff;--ink:#000;--text2:#333;--muted:#555;
        --bord:#bbb;--bord-2:#999;--sombra:none}
  .hero,.nav-wrap,.filo,.tema,.quien,.subir,.peticiones,.acc,.acc-fila,
  form,button,.migas,#q,.barra .cuenta,.seccion form{display:none!important}
  body{background:#fff;font-size:10.5pt}
  .wrap{max-width:100%;margin:0;padding:0}
  table,.persona,.conf-caja,.seccion,.cinta{break-inside:avoid;box-shadow:none;
        border-color:#bbb}
  tr{break-inside:avoid}
  .descargo{border:1px solid #999;background:#fff}
  footer{margin-top:18px;border-top:1px solid #bbb;padding-top:10px;color:#000}
  a[href]::after{content:""}
}

/* ══ MODO OSCURO ══
   Se redefinen SOLO los tokens; ninguna regla de arriba se repite. La escala
   zinc se invierte y los colores del semáforo se aclaran, porque el verde
   #1C6F43 sobre fondo oscuro deja de leerse. El sitio sigue la preferencia del
   sistema y el interruptor de la cabecera manda sobre ella en los dos
   sentidos. */
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --tinta:#FAFAFA;--tinta-2:#E4E4E7;--sobre-tinta:#18181B;--sup:#18181B;
    --z50:#1F1F23;--z100:#27272A;--z200:#3F3F46;--z300:#52525B;--z400:#8B8B94;
    --z500:#A1A1AA;--z600:#D4D4D8;
    --verde:#4ADE80;--ambar:#FBBF24;--rojo:#FCA5A5;
    --rojo-f:#2A1616;--rojo-b:#7F2A22;--verde-f:#132419;--verde-b:#2C5C3E;
    --ambar-f:#241E10;--ambar-b:#5C4A1E;--ambar-t:#FBBF24;
    --fondo:#0F0F11;--zebra:#1F1F23;
    --sombra:0 1px 2px rgba(0,0,0,.5);
    color-scheme:dark;
  }
}
:root[data-theme="dark"]{
  --tinta:#FAFAFA;--tinta-2:#E4E4E7;--sobre-tinta:#18181B;--sup:#18181B;
  --z50:#1F1F23;--z100:#27272A;--z200:#3F3F46;--z300:#52525B;--z400:#8B8B94;
  --z500:#A1A1AA;--z600:#D4D4D8;
  --verde:#4ADE80;--ambar:#FBBF24;--rojo:#FCA5A5;
  --rojo-f:#2A1616;--rojo-b:#7F2A22;--verde-f:#132419;--verde-b:#2C5C3E;
  --ambar-f:#241E10;--ambar-b:#5C4A1E;--ambar-t:#FBBF24;
  --fondo:#0F0F11;--zebra:#1F1F23;
  --sombra:0 1px 2px rgba(0,0,0,.5);
  color-scheme:dark;
}
""" + legal.ESTILO

PIE_LOCAL = ('<b>RENTA IA</b> · versión local · los datos no salen de este equipo<br>'
             + legal.CORTO)
PIE_NUBE = ('<b>RENTA IA</b> · acceso restringido · información tributaria sujeta a '
            'reserva (art. 583 E.T.)<br>' + legal.CORTO)


# La «R» de la marca sobre la tinta del sitio, en un SVG incrustado en la
# propia página. Sin archivo que servir ni petición extra — y en Vercel, donde
# todo se enruta a la función, un /favicon.ico habría que atenderlo a mano.
FAVICON = (
    '<link rel="icon" href="data:image/svg+xml,'
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
    "%3Crect width='64' height='64' rx='14' fill='%2318181B'/%3E"
    "%3Ctext x='32' y='46' font-family='Segoe UI,system-ui,sans-serif' "
    "font-size='40' font-weight='600' fill='%23ffffff' "
    "text-anchor='middle'%3ER%3C/text%3E%3C/svg%3E\">"
    '<link rel="apple-touch-icon" href="data:image/svg+xml,'
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
    "%3Crect width='64' height='64' rx='14' fill='%2318181B'/%3E"
    "%3Ctext x='32' y='46' font-family='Segoe UI,system-ui,sans-serif' "
    "font-size='40' font-weight='600' fill='%23ffffff' "
    "text-anchor='middle'%3ER%3C/text%3E%3C/svg%3E\">")

# Va en el <head>, antes de la hoja de estilos, y a propósito: si se aplicara
# al final, la página pintaría un instante en claro antes de oscurecerse. Ese
# parpadeo blanco de madrugada es justo lo que el modo oscuro viene a evitar.
TEMA_TEMPRANO = """<script>
(function(){try{var t=localStorage.getItem('rentaia-tema');
if(t==='dark'||t==='light'){document.documentElement.setAttribute('data-theme',t);}
}catch(e){}})();
</script>"""

TEMA_SCRIPT = """<script>
(function(){
 var b=document.getElementById('tema');if(!b)return;
 var raiz=document.documentElement;
 function oscuro(){var t=raiz.getAttribute('data-theme');
   if(t)return t==='dark';
   return window.matchMedia('(prefers-color-scheme: dark)').matches;}
 function pintar(){var o=oscuro();
   b.textContent=o?'\\u2600':'\\u263D';
   b.setAttribute('aria-label',o?'Cambiar a modo claro':'Cambiar a modo oscuro');
   b.setAttribute('title',b.getAttribute('aria-label'));}
 b.addEventListener('click',function(){
   var nuevo=oscuro()?'light':'dark';
   raiz.setAttribute('data-theme',nuevo);
   try{localStorage.setItem('rentaia-tema',nuevo);}catch(e){}
   pintar();});
 pintar();
})();
</script>"""


def hero(sub, stats_html='', usuario='', nav='', rol=''):
    etiqueta = (f'<span class="rolete">{e(rol)}</span>' if rol else '')
    quien = (f'<div class="quien"><b>{e(usuario)}</b>'
             f'<a href="/cuenta">mi cuenta</a> · <a href="/salir">salir</a><br>'
             f'{etiqueta}</div>') if usuario else ''
    barra = f'<div class="nav-wrap"><div class="nav">{nav}</div></div>' if nav else ''
    return f"""<div class="hero">{quien}
<button class="tema" id="tema" type="button" aria-label="Cambiar el modo de color">&#9789;</button>
<div class="hero-in">
<div class="marca"><div class="logo" aria-hidden="true">R</div>
  <div><div class="wordmark">RENTA<span> IA</span></div><div class="lema">{LEMA}</div></div></div>
<div class="hero-sub">{sub}</div>{stats_html}
</div>{barra}</div>"""


def pagina(titulo, cuerpo, sub='', stats='', usuario='', pie=PIE_LOCAL, nav='',
           rol='', estilo_extra='', apartado='renta'):
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#FFFFFF" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0F0F11" media="(prefers-color-scheme: dark)">
<meta name="robots" content="noindex,nofollow">
{FAVICON}
<title>{e(titulo)} · {MARCA}</title>
{TEMA_TEMPRANO}
<style>{ESTILO}{estilo_extra}</style></head><body>
{hero(sub, stats, usuario, nav, rol)}
<div class="filo {e(apartado)}"></div>
<div class="wrap">{cuerpo}
<footer>{pie}</footer>
</div>
{TEMA_SCRIPT}
</body></html>"""


def formulario(cupo=None, token=''):
    """Zona de subida. `cupo` = (usadas, tope) para el usuario con límite.

    Con el cupo lleno **el formulario sigue ahí**, y no es un descuido: subir
    otra vez un contribuyente y un año que ya tiene cargados no crea una
    declaración nueva, la reemplaza, y por eso no cuesta cupo. Si se ocultara,
    quien subió el archivo equivocado se quedaría sin manera de corregirlo.
    """
    lleno = bool(cupo) and cupo[0] >= cupo[1]
    aviso_cupo = ''
    if lleno:
        aviso_cupo = (
            f'<div class="cupo" style="border-color:var(--ambar-b);'
            f'background:var(--ambar-f)"><b>Cupo completo:</b> '
            f'{cupo[0]} de {cupo[1]} declaraciones. No entran contribuyentes '
            f'nuevos hasta que el administrador amplíe el cupo, pero <b>sí se '
            f'puede volver a subir una declaración ya cargada</b> —por ejemplo, '
            f'si el archivo era el equivocado—: reemplazarla no consume cupo '
            f'nuevo.</div>')
    elif cupo:
        pct = int(cupo[0] * 100 / cupo[1]) if cupo[1] else 0
        aviso_cupo = (f'<div class="cupo">Cupo: <b>{cupo[0]} de {cupo[1]}</b> '
                      f'declaraciones procesadas.<div class="barrita">'
                      f'<i style="width:{pct}%"></i></div></div>')
    campo = f'<input type="hidden" name="_t" value="{e(token)}">' if token else ''
    return f"""
<div class="subir">
  <h2>Procesar una exógena</h2>
  <p>Arrastre el archivo <b>reporteExogena.xlsx</b> descargado del prevalidador MUISCA.
  RENTA IA lo lee, clasifica cada registro, valida los totales contra los topes precalculados
  por la DIAN y arma el libro de trabajo de 9 hojas. Si algo no cuadra, el caso queda en ROJO
  e indica exactamente qué partida falla.</p>
  <form method="post" action="/subir" enctype="multipart/form-data" id="f">{campo}
    <label class="zona" id="z">
      <input type="file" name="archivo" id="a" accept=".xlsx" required>
      <div class="ic">&#128196;</div>
      <div class="txt">Arrastre el archivo aquí o haga clic para elegirlo</div>
      <div class="arch" id="n"></div>
    </label>
    <button type="submit" id="b">Procesar y generar el libro</button>
    <div class="pasos"><span>1 &middot; Lee el reporte</span><span>2 &middot; Clasifica los registros</span>
    <span>3 &middot; Valida contra los topes DIAN</span><span>4 &middot; Genera el libro</span></div>
  </form>{aviso_cupo}
</div>
<script>
var z=document.getElementById('z'),a=document.getElementById('a'),
    n=document.getElementById('n'),f=document.getElementById('f'),b=document.getElementById('b');
a.onchange=function(){{n.textContent=a.files.length?a.files[0].name:''}};
['dragenter','dragover'].forEach(function(ev){{z.addEventListener(ev,function(x){{
  x.preventDefault();z.classList.add('hover')}})}});
['dragleave','drop'].forEach(function(ev){{z.addEventListener(ev,function(x){{
  x.preventDefault();z.classList.remove('hover')}})}});
z.addEventListener('drop',function(x){{a.files=x.dataTransfer.files;
  n.textContent=a.files.length?a.files[0].name:''}});
f.addEventListener('submit',function(){{b.disabled=true;b.textContent='Procesando…';}});
</script>
"""


BUSCADOR = """
<script>
var q=document.getElementById('q');
if(q){q.addEventListener('input',function(){
  var t=q.value.trim().toLowerCase(), n=0;
  document.querySelectorAll('.persona').forEach(function(p){
    var v=!t||p.dataset.busca.indexOf(t)>=0;
    p.style.display=v?'':'none'; if(v)n++;
  });
  document.getElementById('cuenta').textContent=n+(n===1?' contribuyente':' contribuyentes');
});}
</script>
"""

LEYENDA = ('<div class="aviso"><b>Cómo leer el semáforo.</b> '
           '<b>VERDE</b>: los totales reconstruidos reproducen los topes precalculados por la '
           'DIAN y no hay hallazgos altos. <b>AMARILLO</b>: los topes cuadran, pero hay alertas '
           'de severidad ALTA que deben resolverse. <b>ROJO</b>: los totales no cuadran — hay '
           'una partida mal clasificada y el caso no debe liberarse. El libro de 9 hojas se '
           'descarga y se termina en Excel con los certificados del contribuyente.</div>')


# El semáforo no puede comunicarse SOLO por color: uno de cada doce hombres no
# distingue el verde del rojo, y el punto de al lado del año era exactamente
# eso. Cada estado lleva ahora su propia forma, además del rótulo en texto.
SEM_FORMA = {'VERDE': '●', 'AMARILLO': '▲', 'ROJO': '■'}


def _dias_para_vencer(c):
    """Días que faltan para el plazo de esa declaración, o None.

    El calendario oficial ya está cargado en `plazos.py` y el libro escribe la
    fecha; en la bandeja no se veía, que es donde uno decide por cuál caso
    empezar en temporada.
    """
    try:
        import plazos
        C = c.get('C') or {}
        venc = plazos.vencimiento(C.get('ano_gravable'), C.get('ultimos_digitos'))
        if not venc:
            return None
        import datetime
        return (venc - datetime.date.today()).days
    except Exception:
        return None


def _fila_ano(c, mostrar_estado):
    if 'error' in c:
        return (f'<div class="ano"><div class="ag">{e(c["ano"])}</div>'
                f'<div><span class="mal">caso con error:</span> '
                f'<span class="alertitas">{e(c["error"])[:110]}</span></div>'
                f'<div class="acc"></div></div>')
    cal = c['calc']
    sem = cal['semaforo']
    color, etiqueta, _ = SEM[sem]
    saldo = cal['saldo']
    clase = 'fav' if saldo < 0 else ''
    rot = 'Saldo a favor' if saldo < 0 else 'Saldo a pagar'
    libro = (f'<a class="btn" href="/libro/{e(c["ref"])}">Libro</a>' if c.get('libro')
             else '<span class="alertitas">sin libro</span>')
    marca = ''
    if mostrar_estado:
        col, txt = ESTADO_ET.get(c.get('estado', 'borrador'), ESTADO_ET['borrador'])
        marca = f'<span class="pill" style="color:{col}">{txt.upper()}</span>'
    dias = _dias_para_vencer(c)
    plazo = ''
    if dias is not None:
        if dias < 0:
            plazo = (f'<span class="plazo vencido">vencida hace {abs(dias)} '
                     f'día(s)</span>')
        elif dias <= 30:
            plazo = f'<span class="plazo cerca">vence en {dias} día(s)</span>'
        else:
            plazo = f'<span class="plazo">vence en {dias} días</span>'
    return f"""<div class="ano">
  <div class="ag"><span class="pt" style="color:{color}" role="img"
      aria-label="{e(etiqueta)}">{SEM_FORMA.get(sem, '●')}</span>{e(c['ano'])}
    <span class="est" style="color:{color}">{SEM_CORTO[sem]}</span></div>
  <div><div class="cifras">
    <div class="cif"><div class="l">Ingresos</div><div class="v">{pesos(cal['ingresos'])}</div></div>
    <div class="cif"><div class="l">Impuesto</div><div class="v">{pesos(cal['impuesto'])}</div></div>
    <div class="cif"><div class="l">{rot}</div><div class="v {clase}">{pesos(abs(saldo))}</div></div>
  </div><div class="alertitas">{len(c['C'].get('alertas', []))} alertas &middot;
    {cal['n_altas']} de severidad alta{marca}{plazo}</div></div>
  <div class="acc"><a class="btn sec" href="/caso/{e(c['ref'])}">Revisar</a>{libro}</div>
</div>"""


ORDENES = (('nombre', 'Nombre'), ('vence', 'Lo que vence primero'),
           ('saldo', 'Saldo mayor'), ('reciente', 'Cargado más reciente'))


def _filtrar(lista, sem='', estado=''):
    """Aplica el filtro del semáforo y el del estado de revisión."""
    fuera = []
    for c in lista:
        if sem and (c.get('calc') or {}).get('semaforo') != sem:
            continue
        if estado and c.get('estado', 'borrador') != estado:
            continue
        fuera.append(c)
    return fuera


def _ordenar(grupos, orden):
    """Ordena las fichas de contribuyente. Por nombre, salvo que se pida otra."""
    if orden == 'vence':
        def clave(g):
            dias = [_dias_para_vencer(c) for c in g['filas']]
            dias = [d for d in dias if d is not None]
            # Sin fecha va al final: no es que no urja, es que no se sabe.
            return (min(dias) if dias else 10 ** 6, g['titulo'].lower())
        return sorted(grupos, key=clave)
    if orden == 'saldo':
        def clave(g):
            saldos = [abs((c.get('calc') or {}).get('saldo') or 0) for c in g['filas']]
            return (-max(saldos or [0]), g['titulo'].lower())
        return sorted(grupos, key=clave)
    if orden == 'reciente':
        return sorted(grupos, key=lambda g: max(
            (str(c.get('creado_en') or '') for c in g['filas']), default=''),
            reverse=True)
    return sorted(grupos, key=lambda g: g['titulo'].lower())


def _barra_filtros(conteo, sem, estado, orden):
    """Fichas de filtro y selector de orden, debajo del buscador."""
    def enlace(clave, valor, texto, activo):
        otros = []
        if clave != 'sem' and sem:
            otros.append('sem=' + sem)
        if clave != 'estado' and estado:
            otros.append('estado=' + estado)
        if orden and orden != 'nombre':
            otros.append('orden=' + orden)
        if valor:
            otros.append(clave + '=' + valor)
        url = '/?' + '&amp;'.join(otros) if otros else '/'
        cls = ' act' if activo else ''
        return f'<a class="chip-f{cls}" href="{url}">{texto}</a>'

    chips = [enlace('sem', '', 'Todas', not sem and not estado)]
    for clave, texto in (('VERDE', 'Listas'), ('AMARILLO', 'Con alertas'),
                         ('ROJO', 'No liberar')):
        if conteo.get(clave):
            chips.append(enlace('sem', clave, f'{texto} ({conteo[clave]})',
                                sem == clave))
    for clave, texto in (('borrador', 'Borrador'), ('en_revision', 'En revisión'),
                         ('liberada', 'Liberadas')):
        chips.append(enlace('estado', clave, texto, estado == clave))

    opciones = ''.join(
        f'<option value="{k}"{" selected" if orden == k else ""}>{t}</option>'
        for k, t in ORDENES)
    ocultos = ''.join(
        f'<input type="hidden" name="{k}" value="{e(v)}">'
        for k, v in (('sem', sem), ('estado', estado)) if v)
    return f"""<div class="filtros-bar">
  <div class="chips">{''.join(chips)}</div>
  <form method="get" action="/" class="orden">{ocultos}
    <label for="orden">Ordenar por</label>
    <select id="orden" name="orden" onchange="this.form.submit()">{opciones}</select>
    <noscript><button class="mini sec" type="submit">Aplicar</button></noscript>
  </form>
</div>"""


def vista_bandeja(lista, error='', extra='', usuario='', puede_subir=True,
                  cupo=None, pie=PIE_LOCAL, mostrar_estado=False, sub=None,
                  nav='', rol='', token='', aviso='', hecho='', solicitudes='',
                  sem='', estado='', orden='nombre'):
    conteo = {'VERDE': 0, 'AMARILLO': 0, 'ROJO': 0}
    for c in lista:
        if 'calc' in c:
            conteo[c['calc']['semaforo']] += 1
    total_personas = len(agrupar(lista))

    visibles = _filtrar(lista, sem, estado)
    grupos = _ordenar(agrupar(visibles), orden)

    def stat(clase, n, etiqueta, filtro=''):
        # Cada cifra del encabezado es AHORA el filtro que le corresponde.
        # Estaban calculadas desde el primer día y no llevaban a ninguna parte:
        # el contador las leía y después buscaba los rojos a ojo entre cien
        # fichas.
        url = ('/?sem=' + filtro) if filtro else '/'
        act = ' act' if (filtro and sem == filtro) else ''
        return (f'<a class="stat {clase}{act}" href="{url}">'
                f'<div class="n">{n}</div><div class="l">{etiqueta}</div></a>')

    stats = ('<div class="stats">'
             + stat('', total_personas, 'Contribuyentes')
             + stat('', len(lista), 'Declaraciones')
             + stat('v', conteo['VERDE'], 'Listas', 'VERDE')
             + stat('a', conteo['AMARILLO'], 'Con alertas', 'AMARILLO')
             + stat('r', conteo['ROJO'], 'No liberar', 'ROJO')
             + '</div>')

    fichas = []
    for g in grupos:
        filas = ''.join(_fila_ano(c, mostrar_estado) for c in g['filas'])
        busca = e((g['titulo'] + ' ' + str(g['ident'])).lower())
        fichas.append(f"""<div class="persona" data-busca="{busca}">
  <div class="p-cab"><div class="mono">{e(iniciales(g['titulo']))}</div>
    <div><h3>{e(g['titulo'])}</h3><div class="cc">{e(g['ident'])}</div></div>
    <div class="anos">{len(g['filas'])} año(s) gravable(s)</div></div>
  {filas}
</div>""")

    if fichas:
        listado = ''.join(fichas)
    elif lista:
        listado = ('<div class="vacio">Ningún caso cumple ese filtro. '
                   '<a href="/">Ver todos</a></div>')
    else:
        listado = ('<div class="vacio">Todavía no hay casos. Suba una exógena '
                   'para empezar.</div>')
    plural = 's' if len(grupos) != 1 else ''
    cuerpo = ((f'<div class="err">{e(error)}</div>' if error else '')
              + (f'<div class="ok-msg">{e(hecho)}</div>' if hecho else '')
              # Antes que nada: si alguien pide entrar a sus declaraciones, esa
              # decisión no puede quedar sepultada bajo el resto de la pantalla.
              + solicitudes
              + (f'<div class="aviso" style="margin:0 0 20px">{e(aviso)}</div>'
                 if aviso else '')
              + (formulario(cupo, token) if puede_subir else '')
              + extra
              + f'<div class="barra"><h2>Contribuyentes</h2>'
                f'<span class="cuenta" id="cuenta">{len(grupos)} contribuyente{plural}</span>'
                f'<label class="oculto" for="q">Buscar por nombre o cédula</label>'
                f'<input id="q" type="search" placeholder="Buscar por nombre o cédula…"></div>'
              + _barra_filtros(conteo, sem, estado, orden)
              + listado + BUSCADOR + LEYENDA)
    return pagina('Bandeja', cuerpo,
                  sub or 'BANDEJA DEL CONTADOR &nbsp;&middot;&nbsp; CADA CASO SE VALIDA '
                         'CONTRA LOS TOPES DE LA DIAN',
                  stats, usuario, pie, nav, rol)


def vista_confirmar(ref, C, calc, previa=None, cupo=None, token='', usuario='',
                    pie=PIE_LOCAL, nav='', rol='', error='', valores=None):
    """Paso 2 de la carga: esto salió, ¿lo genero?

    Existe por tres razones que se resuelven juntas:

      · **El cupo no se gasta por equivocarse de archivo.** Hasta que no se
        pulsa el botón de esta pantalla no se ha creado nada. Antes, subir el
        archivo del cliente que no era dejaba una cuenta de cupo 1 atascada, y
        solo el administrador podía destrabarla.
      · **Lo que la exógena no trae se pregunta ahora**, no después a mano en
        Excel: casado, hijos, hipoteca, ICETEX y residencia.
      · **El descargo se acepta aquí**, con las cifras delante, que es el único
        momento en que aceptarlo significa algo.
    """
    valores = valores or {}
    color, etiqueta, explica = SEM[calc['semaforo']]

    ficha = [
        ('Contribuyente', e(C.get('nombre_titulo', '—'))),
        ('Identificación', e(C.get('identificacion', '—'))),
        ('Año gravable', e(C.get('ano_gravable', '—'))),
        ('Registros leídos', f"{C.get('registros', '—')}"),
        ('Fuente', e(C.get('fuente', '—'))),
    ]
    filas_ficha = ''.join(
        f'<div class="cf"><div class="l">{k}</div><div class="v">{v}</div></div>'
        for k, v in ficha)

    saldo = calc['saldo']
    rot = 'Saldo a favor' if saldo < 0 else 'Saldo a pagar'
    cifras = [('Patrimonio líquido', pesos(calc['pat_liquido']), ''),
              ('Ingresos brutos', pesos(calc['ingresos']), ''),
              ('Renta líquida gravable', pesos(calc['rlg']), ''),
              ('Impuesto a cargo', pesos(calc['impuesto']), ''),
              (rot, pesos(abs(saldo)), ' fav' if saldo < 0 else '')]
    filas_cifras = ''.join(
        f'<div class="cf"><div class="l">{k}</div><div class="v{cl}">{v}</div></div>'
        for k, v, cl in cifras)

    # Reemplazo: **esta cuenta** ya cargó ese contribuyente y ese año. No es un
    # error —es reprocesar con el archivo corregido— y **no cuenta cupo otra
    # vez**, porque no se crea una fila nueva: se actualiza la que hay.
    #
    # Lo que hayan cargado otras cuentas no aparece aquí ni en ninguna otra
    # parte: cada una tiene su propia copia del caso y ninguna sabe de las
    # demás. `previa` solo puede ser lo suyo (ver `_previa_de` en api\index.py).
    aviso_previa = ''
    if previa:
        aviso_previa = (
            f'<div class="aviso" style="margin:0 0 18px;border-color:var(--ambar-b);'
            f'background:var(--ambar-f)"><b>Esta declaración ya está cargada.</b> '
            f'{e(C.get("nombre_titulo", ""))} · AG {e(C.get("ano_gravable", ""))}, '
            f'del {e(previa)}. Al continuar <b>se reemplaza</b> por esta: el libro '
            f'y el archivo se sustituyen y las alertas se recalculan. '
            f'<b>No consume cupo nuevo</b> —no se crea otra declaración, se '
            f'actualiza la que ya está— y las alertas marcadas como resueltas '
            f'se conservan.</div>')

    aviso_cupo = ''
    sin_cupo = bool(cupo) and not previa and cupo[0] >= cupo[1]
    if sin_cupo:
        aviso_cupo = (
            f'<div class="err" style="margin:0 0 18px"><b>Sin cupo disponible.</b> '
            f'Van {cupo[0]} de {cupo[1]} declaraciones y esta sería una nueva. '
            f'Para ampliar el cupo hay que escribir al administrador; lo ya '
            f'cargado sigue disponible y esta carga no se ha guardado.</div>')
    elif cupo and not previa:
        usadas, tope = cupo
        aviso_cupo = (f'<div class="cupo" style="margin:0 0 18px">Al generar, esta '
                      f'será la declaración <b>{usadas + 1} de {tope}</b> del cupo. '
                      f'Todavía no se ha contado: al cancelar, no se gasta.</div>')

    preguntas = []
    for clave, pregunta, detalle, _ in mod_perfil.PREGUNTAS:
        actual = valores.get('perfil_' + clave, '')
        opciones = ''.join(
            f'<option value="{v}"{" selected" if actual == v else ""}>'
            f'{v or "— sin responder —"}</option>' for v in mod_perfil.RESPUESTAS)
        tipo = 'number' if clave in mod_perfil.NUMERICAS else 'text'
        preguntas.append(f"""<div class="pregunta">
  <div class="q">{e(pregunta)}</div>
  <select name="perfil_{clave}" aria-label="{e(pregunta)}">{opciones}</select>
  <input type="{tipo}" name="detalle_{clave}" maxlength="120"
         placeholder="{e(detalle)}" value="{e(valores.get('detalle_' + clave, ''))}"
         aria-label="{e(detalle)}">
</div>""")

    cuerpo = f"""
<div class="migas"><a href="/">&larr; Volver a la bandeja</a></div>
{f'<div class="err">{e(error)}</div>' if error else ''}
<h1 style="font-size:22px;margin-bottom:6px">Esto encontró RENTA IA en el archivo</h1>
<p style="color:var(--text2);font-size:13.4px;margin-bottom:20px;max-width:80ch">
Revise que el contribuyente y el año sean los que corresponden. <b>Todavía no se ha
creado nada</b>: si algo no cuadra, cancele y no se consume cupo.</p>
{aviso_previa}{aviso_cupo}
<div class="conf-caja">
  <div class="conf-tit">El contribuyente</div>
  <div class="conf-rej">{filas_ficha}</div>
</div>
<div class="conf-caja">
  <div class="conf-tit">Las cifras que darían
    <span class="chip" style="background:{color}">{e(calc['semaforo'])}</span>
    <span style="color:{color};font-weight:600;font-size:12.5px">{e(etiqueta)}</span></div>
  <div class="conf-rej">{filas_cifras}</div>
  <p class="conf-pie">{e(explica)}. Son las cifras del validador sobre la exógena
  tal cual; el libro trae las casillas abiertas para los soportes.</p>
</div>
<form method="post" action="/confirmar/{e(ref)}" id="f">
  <input type="hidden" name="_t" value="{e(token)}">
  <div class="conf-caja">
    <div class="conf-tit">Lo que la exógena no dice</div>
    <p class="conf-pie" style="margin:0 0 14px">Ninguna de estas cinco cosas llega en
    el reporte de la DIAN y todas mueven la liquidación. <b>Pueden quedar en blanco</b>
    si todavía no están confirmadas con el contribuyente: el libro las deja abiertas,
    como hasta ahora.</p>
    {''.join(preguntas)}
  </div>
  {legal.bloque()}
  {legal.casilla()}
  <div class="acc-fila" style="justify-content:flex-start;margin-top:18px">
    <button type="submit" id="b"{' disabled' if sin_cupo else ''}>Generar el libro</button>
    <a class="mini sec" href="/confirmar/{e(ref)}/cancelar">Cancelar y descartar</a>
  </div>
</form>
<script>
var f=document.getElementById('f'),b=document.getElementById('b');
f.addEventListener('submit',function(){{b.disabled=true;b.textContent='Generando…';}});
</script>"""
    return pagina('Confirmar la carga', cuerpo,
                  'PASO 2 DE 2 &nbsp;&middot;&nbsp; REVISE Y CONFIRME &nbsp;&middot;&nbsp; '
                  'TODAVÍA NO SE HA CREADO NADA', '', usuario, pie, nav, rol)


def vista_caso(caso, tolerancia, usuario='', pie=PIE_LOCAL, mostrar_estado=False,
               nav='', rol='', acciones='', estilo_extra='', token='',
               puede_marcar=False):
    c, C = caso['calc'], caso['C']
    ref = caso['ref']
    color, etiqueta, explica = SEM[c['semaforo']]

    nombres = {'ingresos': 'Tope 1 &middot; Ingresos brutos',
               'patrimonio': 'Tope 2 &middot; Patrimonio bruto',
               'consumos': 'Tope 3 &middot; Consumos con tarjeta',
               'movimientos': 'Tope 4 &middot; Consignaciones',
               'compras': 'Tope 5 &middot; Compras'}
    mios = {'ingresos': c['ingresos'], 'patrimonio': c['pat_bruto'], 'consumos': c['consumos'],
            'movimientos': c['movimientos'], 'compras': c['compras']}
    filas_topes = []
    for k, lab in nombres.items():
        if k in c['difs_topes']:
            d = c['difs_topes'][k]
            tol = tolerancia(c['topes_dian'][k])
            estado = ('<span class="ok">EXACTO</span>' if d == 0 else
                      (f'<span class="ok">&plusmn; {pesos(abs(d))} &middot; redondeo</span>'
                       if abs(d) <= tol else f'<span class="mal">DIFERENCIA {pesos(d)}</span>'))
            filas_topes.append(f'<tr><td>{lab}</td><td class="n">{pesos(c["topes_dian"][k])}</td>'
                               f'<td class="n">{pesos(mios[k])}</td><td>{estado}</td></tr>')

    cifras = [
        ('Patrimonio bruto reconstruido', c['pat_bruto'], False),
        ('Deudas', c['deudas'], False),
        ('Patrimonio líquido', c['pat_liquido'], True),
        ('Ingresos brutos cédula general', c['ingresos'], False),
        ('(−) Rentas exentas y deducciones aceptadas', -c['exentas_aceptadas'], False),
        ('(−) Deducción del 1% por factura electrónica', -c['ded_1pct'], False),
        ('Renta líquida gravable', c['rlg'], True),
        (None, None, False),
        ('Impuesto a cargo', c['impuesto'], True),
        ('(−) Retenciones en la fuente', -c['retenciones'], False),
        ('(+) Anticipo del año siguiente', c['anticipo'], False),
    ]
    filas_cifras = []
    for lab, v, fuerte in cifras:
        if lab is None:
            uvt = f'{c["base_uvt"]:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
            filas_cifras.append(f'<tr><td>Base gravable en UVT ({e(C["ano_gravable"])})</td>'
                                f'<td class="n">{uvt} UVT</td></tr>')
            continue
        peso = ' style="font-weight:700"' if fuerte else ''
        filas_cifras.append(f'<tr{peso}><td>{e(lab)}</td><td class="n">{pesos(v)}</td></tr>')
    saldo = c['saldo']
    rot = 'SALDO A FAVOR' if saldo < 0 else 'SALDO A PAGAR'
    col = VERDE if saldo < 0 else TINTA
    filas_cifras.append(f'<tr style="font-weight:700;color:{col}"><td>{rot}</td>'
                        f'<td class="n">{pesos(abs(saldo))}</td></tr>')

    # Las alertas pueden venir de la tabla (diccionarios, con la marca de
    # revisión) o del JSON del caso (tuplas, como las dejó el clasificador).
    # La bandeja local no tiene base de datos y sigue usando lo segundo.
    crudas = caso.get('alertas')
    if crudas is None:
        crudas = C.get('alertas', [])
    alertas = [a if isinstance(a, dict) else
               {'codigo': a[0], 'severidad': a[1], 'hallazgo': a[2],
                'detalle': a[3], 'accion': a[4]} for a in crudas]
    sin_resolver_altas = sum(1 for a in alertas
                             if a.get('severidad') == 'ALTA' and not a.get('resuelta'))

    filas_alertas = []
    for a in alertas:
        sev = a.get('severidad') or 'INFORMATIVO'
        resuelta = bool(a.get('resuelta'))
        clase = ' class="resuelta"' if resuelta else ''
        marca = ''
        if resuelta:
            nota = (a.get('nota_contador') or '').strip()
            cuando = (a.get('resuelta_en') or '')[:10]
            marca = (f'<div class="nota-res"><b>Resuelta</b>'
                     f'{" · " + e(cuando) if cuando else ""}'
                     f'{"<br>" + e(nota) if nota else ""}</div>')
        control = ''
        if puede_marcar and a.get('id'):
            if resuelta:
                control = (
                    f'<form method="post" action="/caso/{e(ref)}/alerta">'
                    f'<input type="hidden" name="_t" value="{e(token)}">'
                    f'<input type="hidden" name="alerta" value="{e(a["id"])}">'
                    f'<input type="hidden" name="resuelta" value="0">'
                    f'<button class="mini sec" type="submit">Reabrir</button></form>')
            else:
                control = (
                    f'<form method="post" action="/caso/{e(ref)}/alerta" class="marcar">'
                    f'<input type="hidden" name="_t" value="{e(token)}">'
                    f'<input type="hidden" name="alerta" value="{e(a["id"])}">'
                    f'<input type="hidden" name="resuelta" value="1">'
                    f'<input type="text" name="nota" maxlength="500" '
                    f'placeholder="Cómo se resolvió (opcional)" '
                    f'aria-label="Nota de cómo se resolvió la alerta {e(a.get("codigo", ""))}">'
                    f'<button class="mini sec" type="submit">Dar por resuelta</button>'
                    f'</form>')
        filas_alertas.append(
            f'<tr{clase}><td class="cod"><b>{e(a.get("codigo", ""))}</b></td>'
            f'<td><span class="chip" style="background:{SEV_COLOR.get(sev, GRIS)}">{e(sev)}</span></td>'
            f'<td><b>{e(a.get("hallazgo", ""))}</b><br>'
            f'<span style="color:var(--text2);font-size:12.5px">{e(a.get("detalle", ""))}</span><br>'
            f'<span style="color:var(--muted);font-size:12.5px"><i>&rarr; '
            f'{e(a.get("accion", ""))}</i></span>{marca}{control}</td></tr>')

    contador_altas = ''
    if puede_marcar and alertas:
        resueltas = sum(1 for a in alertas if a.get('resuelta'))
        contador_altas = (f' &nbsp;&middot;&nbsp; {resueltas} de {len(alertas)} '
                          f'marcadas como resueltas')
        if sin_resolver_altas:
            contador_altas += (f' &nbsp;&middot;&nbsp; <span style="color:{ROJO}">'
                               f'{sin_resolver_altas} ALTA(S) SIN RESOLVER</span>')

    libro = (f'<a class="btn" href="/libro/{e(ref)}">Descargar libro de 9 hojas</a>'
             if caso.get('libro') else '')
    marca = ''
    if mostrar_estado:
        colr, txt = ESTADO_ET.get(caso.get('estado', 'borrador'), ESTADO_ET['borrador'])
        marca = f'<span class="pill" style="color:{colr}">{txt.upper()}</span>'
    cuerpo = f"""
<div class="migas"><a href="/">&larr; Volver a la bandeja</a></div>
<div class="cinta" style="--sem:{color}">
  <span class="chip" style="background:{color}">{e(c['semaforo'])}</span>
  <span class="tit">{e(etiqueta)}</span><span class="des">{e(explica)}{marca}</span>{libro}</div>
<table><caption>Validación contra los topes precalculados por la DIAN</caption>
<thead><tr><th>Tope</th><th class="n">DIAN</th><th class="n">Reconstruido</th><th>Estado</th></tr></thead>
<tbody>{''.join(filas_topes)}</tbody></table>
<table><caption>Cifras clave</caption>
<thead><tr><th>Concepto</th><th class="n">Valor</th></tr></thead>
<tbody>{''.join(filas_cifras)}</tbody></table>
<table><caption>Hallazgos por resolver antes de liberar{contador_altas}</caption>
<thead><tr><th style="width:66px">Cód.</th><th style="width:112px">Severidad</th>
<th>Hallazgo &middot; detalle &middot; acción</th></tr></thead>
<tbody>{''.join(filas_alertas)}</tbody></table>
<div class="aviso"><b>Estas cifras las calcula el validador</b> con los datos de la exógena tal cual.
El libro de Excel es el papel de trabajo definitivo: sus casillas de fondo crema quedan abiertas
para los certificados del contribuyente, y al diligenciarlas el libro se recalcula solo. Esta vista
no reemplaza esa revisión.</div>
{legal.bloque(destacado=False)}{acciones}"""
    return pagina(C.get('nombre_titulo', caso['persona']), cuerpo,
                  f"{e(C.get('identificacion', ''))} &nbsp;&middot;&nbsp; AÑO GRAVABLE "
                  f"{e(C.get('ano_gravable', ''))} &nbsp;&middot;&nbsp; "
                  f"{e(C.get('fuente', '')).upper()}", '', usuario, pie, nav, rol,
                  estilo_extra)
