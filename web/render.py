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
:root{
--tinta:#18181B;--tinta-2:#27272A;
--z50:#FAFAFA;--z100:#F4F4F5;--z200:#E4E4E7;--z300:#D4D4D8;--z400:#A1A1AA;
--z500:#71717A;--z600:#52525B;
--verde:#1C6F43;--ambar:#8D6209;--rojo:#B42318;
--rojo-f:#FEF3F2;--rojo-b:#FECDCA;--verde-f:#F3F8F5;--verde-b:#CFE3D8;
--ink:var(--tinta);--muted:var(--z500);--text2:var(--z600);
--bord:var(--z200);--bord-2:var(--z300);--zebra:var(--z50);--fondo:var(--z50);
--sombra:0 1px 2px rgba(9,9,11,.04);
}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-font-smoothing:antialiased}
body{font-family:ui-sans-serif,system-ui,'Segoe UI',-apple-system,'Helvetica Neue',sans-serif;
background:var(--fondo);color:var(--ink);font-size:14.5px;line-height:1.55}
h1,h2,h3{font-weight:600;letter-spacing:-.018em;line-height:1.25}
a{color:var(--ink);text-underline-offset:2px}

/* ── CABECERA ── */
.hero{background:#fff;border-bottom:1px solid var(--bord);position:relative}
.hero-in{max-width:1120px;margin:0 auto;padding:26px 28px 22px;position:relative;z-index:1}
.marca{display:flex;align-items:center;gap:14px}
.logo{width:40px;height:40px;border-radius:10px;background:var(--tinta);color:#fff;
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
.stats{display:flex;margin-top:20px;border-top:1px solid var(--bord);padding-top:16px;flex-wrap:wrap}
.stat{padding-right:32px;margin-right:32px;border-right:1px solid var(--bord)}
.stat:last-child{border-right:none;margin-right:0;padding-right:0}
.stat .n{font-size:24px;font-weight:600;line-height:1.1;letter-spacing:-.03em;
font-variant-numeric:tabular-nums}
.stat .l{font-size:10px;letter-spacing:.13em;color:var(--z500);text-transform:uppercase;
margin-top:4px;font-weight:600}
.stat.v .n{color:var(--verde)}.stat.a .n{color:var(--ambar)}.stat.r .n{color:var(--rojo)}

.wrap{max-width:1120px;margin:26px auto 60px;padding:0 28px}

/* ── SUBIDA ── */
.subir{background:#fff;border:1px solid var(--bord);border-radius:12px;padding:22px 24px;
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
button{margin-top:16px;background:var(--tinta);color:#fff;border:none;font-size:13.5px;font-weight:500;
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

/* ── BUSCADOR ── */
.barra{display:flex;align-items:center;gap:14px;margin-bottom:14px;flex-wrap:wrap}
.barra h2{font-size:19px;flex:1}
.barra .cuenta{font-size:12.5px;color:var(--muted)}
#q{border:1px solid var(--bord);border-radius:8px;padding:9px 13px;font-size:13.5px;
font-family:inherit;width:270px;background:#fff;color:var(--ink);box-shadow:var(--sombra);
transition:border-color .15s,box-shadow .15s}
#q::placeholder{color:var(--z400)}
#q:focus{outline:none;border-color:var(--z400);box-shadow:0 0 0 3px rgba(161,161,170,.20)}

/* ── FICHA DE CONTRIBUYENTE ── */
.persona{background:#fff;border:1px solid var(--bord);border-radius:12px;margin-bottom:14px;
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
.ag .pt{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:8px;vertical-align:1px}
.ag .est{display:block;font-size:9.5px;letter-spacing:.1em;font-weight:600;margin-top:4px}
.cifras{display:flex;gap:30px;flex-wrap:wrap}
.cif .l{font-size:9.5px;letter-spacing:.12em;color:var(--z400);font-weight:600;text-transform:uppercase}
.cif .v{font-size:15px;font-weight:600;margin-top:3px;letter-spacing:-.01em;
font-variant-numeric:tabular-nums}
.cif .v.fav{color:var(--verde)}
.acc{display:flex;gap:8px;white-space:nowrap}
a.btn{display:inline-block;background:var(--tinta);color:#fff;text-decoration:none;font-size:12.5px;
font-weight:500;padding:8px 14px;border-radius:8px;transition:background .15s}
a.btn:hover{background:var(--tinta-2)}
a.btn.sec{background:#fff;color:var(--ink);border:1px solid var(--bord-2)}
a.btn.sec:hover{background:var(--z100);border-color:var(--z400)}
.alertitas{font-size:11.5px;color:var(--muted);margin-top:6px}
.pill{display:inline-block;font-size:9.5px;font-weight:600;letter-spacing:.06em;padding:2px 8px;
border-radius:20px;border:1px solid currentColor;margin-left:8px;vertical-align:2px}

/* ── DETALLE ── */
.migas{font-size:13px;margin-bottom:16px}
.migas a{color:var(--text2);text-decoration:none}
.migas a:hover{color:var(--ink);text-decoration:underline}
.cinta{display:flex;align-items:center;gap:14px;background:#fff;border:1px solid var(--bord);
border-left:3px solid var(--sem);border-radius:12px;padding:15px 18px;margin-bottom:22px;
flex-wrap:wrap;box-shadow:var(--sombra)}
.cinta .tit{font-weight:600;font-size:14.5px;color:var(--sem)}
.cinta .des{font-size:12.8px;color:var(--text2);flex:1}
table{border-collapse:collapse;width:100%;background:#fff;border:1px solid var(--bord);
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
.vacio{background:#fff;border:1px dashed var(--bord-2);border-radius:12px;padding:44px;
text-align:center;color:var(--muted);font-size:14px}
footer{margin:40px 0 24px;text-align:center;font-size:11.5px;color:var(--z400);line-height:1.7}
footer b{color:var(--z600);font-weight:600}
@media(max-width:760px){
  .ano{grid-template-columns:1fr;gap:10px}
  .quien{position:static;text-align:left;margin-top:12px}
  .stat{padding-right:20px;margin-right:20px}
}
"""

PIE_LOCAL = ('<b>RENTA IA</b> · versión local · los datos no salen de este equipo<br>'
             'Documento de trabajo: la liquidación se revisa y se libera antes de '
             'presentarla a la DIAN')
PIE_NUBE = ('<b>RENTA IA</b> · acceso restringido · información tributaria sujeta a '
            'reserva (art. 583 E.T.)<br>Documento de trabajo: la liquidación se revisa '
            'y se libera antes de presentarla a la DIAN')


def hero(sub, stats_html='', usuario=''):
    quien = (f'<div class="quien"><b>{e(usuario)}</b>sesión activa · '
             f'<a href="/salir">salir</a></div>') if usuario else ''
    return f"""<div class="hero">{quien}<div class="hero-in">
<div class="marca"><div class="logo">R</div>
  <div><div class="wordmark">RENTA<span> IA</span></div><div class="lema">{LEMA}</div></div></div>
<div class="hero-sub">{sub}</div>{stats_html}
</div></div>"""


def pagina(titulo, cuerpo, sub='', stats='', usuario='', pie=PIE_LOCAL):
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#FFFFFF">
<title>{e(titulo)} · {MARCA}</title><style>{ESTILO}</style></head><body>
{hero(sub, stats, usuario)}
<div class="wrap">{cuerpo}
<footer>{pie}</footer>
</div></body></html>"""


def formulario(cupo=None):
    """Zona de subida. `cupo` = (usadas, tope) para el usuario con límite."""
    if cupo and cupo[0] >= cupo[1]:
        return (f'<div class="subir"><h2>Procesar una exógena</h2>'
                f'<p>Su cupo de prueba está completo: ha procesado '
                f'<b>{cupo[0]} de {cupo[1]}</b> declaraciones. Puede seguir '
                f'consultando las que ya cargó; para ampliar el cupo, escriba al '
                f'contador.</p></div>')
    aviso_cupo = ''
    if cupo:
        pct = int(cupo[0] * 100 / cupo[1]) if cupo[1] else 0
        aviso_cupo = (f'<div class="cupo">Cupo de prueba: <b>{cupo[0]} de {cupo[1]}</b> '
                      f'declaraciones procesadas.<div class="barrita">'
                      f'<i style="width:{pct}%"></i></div></div>')
    return f"""
<div class="subir">
  <h2>Procesar una exógena</h2>
  <p>Arrastre el archivo <b>reporteExogena.xlsx</b> descargado del prevalidador MUISCA.
  RENTA IA lo lee, clasifica cada registro, valida los totales contra los topes precalculados
  por la DIAN y arma el libro de trabajo de 9 hojas. Si algo no cuadra, el caso queda en ROJO
  y le dice exactamente qué partida falla.</p>
  <form method="post" action="/subir" enctype="multipart/form-data" id="f">
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


def _fila_ano(c, mostrar_estado):
    if 'error' in c:
        return (f'<div class="ano"><div class="ag">{e(c["ano"])}</div>'
                f'<div><span class="mal">caso con error:</span> '
                f'<span class="alertitas">{e(c["error"])[:110]}</span></div>'
                f'<div class="acc"></div></div>')
    cal = c['calc']
    color, _, _ = SEM[cal['semaforo']]
    saldo = cal['saldo']
    clase = 'fav' if saldo < 0 else ''
    rot = 'Saldo a favor' if saldo < 0 else 'Saldo a pagar'
    libro = (f'<a class="btn" href="/libro/{e(c["ref"])}">Libro</a>' if c.get('libro')
             else '<span class="alertitas">sin libro</span>')
    marca = ''
    if mostrar_estado:
        col, txt = ESTADO_ET.get(c.get('estado', 'borrador'), ESTADO_ET['borrador'])
        marca = f'<span class="pill" style="color:{col}">{txt.upper()}</span>'
    return f"""<div class="ano">
  <div class="ag"><span class="pt" style="background:{color}"></span>{e(c['ano'])}
    <span class="est" style="color:{color}">{SEM_CORTO[cal['semaforo']]}</span></div>
  <div><div class="cifras">
    <div class="cif"><div class="l">Ingresos</div><div class="v">{pesos(cal['ingresos'])}</div></div>
    <div class="cif"><div class="l">Impuesto</div><div class="v">{pesos(cal['impuesto'])}</div></div>
    <div class="cif"><div class="l">{rot}</div><div class="v {clase}">{pesos(abs(saldo))}</div></div>
  </div><div class="alertitas">{len(c['C'].get('alertas', []))} alertas &middot;
    {cal['n_altas']} de severidad alta{marca}</div></div>
  <div class="acc"><a class="btn sec" href="/caso/{e(c['ref'])}">Revisar</a>{libro}</div>
</div>"""


def vista_bandeja(lista, error='', extra='', usuario='', puede_subir=True,
                  cupo=None, pie=PIE_LOCAL, mostrar_estado=False, sub=None):
    grupos = agrupar(lista)
    conteo = {'VERDE': 0, 'AMARILLO': 0, 'ROJO': 0}
    for c in lista:
        if 'calc' in c:
            conteo[c['calc']['semaforo']] += 1

    stats = f"""<div class="stats">
<div class="stat"><div class="n">{len(grupos)}</div><div class="l">Contribuyentes</div></div>
<div class="stat"><div class="n">{len(lista)}</div><div class="l">Declaraciones</div></div>
<div class="stat v"><div class="n">{conteo['VERDE']}</div><div class="l">Listas</div></div>
<div class="stat a"><div class="n">{conteo['AMARILLO']}</div><div class="l">Con alertas</div></div>
<div class="stat r"><div class="n">{conteo['ROJO']}</div><div class="l">No liberar</div></div>
</div>"""

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

    listado = ''.join(fichas) if fichas else (
        '<div class="vacio">Todavía no hay casos. Suba una exógena para empezar.</div>')
    plural = 's' if len(grupos) != 1 else ''
    cuerpo = ((f'<div class="err">{e(error)}</div>' if error else '')
              + (formulario(cupo) if puede_subir else '')
              + extra
              + f'<div class="barra"><h2>Contribuyentes</h2>'
                f'<span class="cuenta" id="cuenta">{len(grupos)} contribuyente{plural}</span>'
                f'<input id="q" type="search" placeholder="Buscar por nombre o cédula…"></div>'
              + listado + BUSCADOR + LEYENDA)
    return pagina('Bandeja', cuerpo,
                  sub or 'BANDEJA DEL CONTADOR &nbsp;&middot;&nbsp; CADA CASO SE VALIDA '
                         'CONTRA LOS TOPES DE LA DIAN',
                  stats, usuario, pie)


def vista_caso(caso, tolerancia, usuario='', pie=PIE_LOCAL, mostrar_estado=False):
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

    filas_alertas = []
    for a in C.get('alertas', []):
        cod, sev, hallazgo, detalle, accion = a[0], a[1], a[2], a[3], a[4]
        filas_alertas.append(
            f'<tr><td class="cod"><b>{e(cod)}</b></td>'
            f'<td><span class="chip" style="background:{SEV_COLOR.get(sev, GRIS)}">{e(sev)}</span></td>'
            f'<td><b>{e(hallazgo)}</b><br>'
            f'<span style="color:var(--text2);font-size:12.5px">{e(detalle)}</span><br>'
            f'<span style="color:var(--muted);font-size:12.5px"><i>&rarr; {e(accion)}</i></span></td></tr>')

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
<table><caption>Hallazgos por resolver antes de liberar</caption>
<thead><tr><th style="width:66px">Cód.</th><th style="width:112px">Severidad</th>
<th>Hallazgo &middot; detalle &middot; acción</th></tr></thead>
<tbody>{''.join(filas_alertas)}</tbody></table>
<div class="aviso"><b>Estas cifras las calcula el validador</b> con los datos de la exógena tal cual.
El libro de Excel es el papel de trabajo definitivo: sus casillas de fondo crema quedan abiertas
para los certificados del contribuyente, y al diligenciarlas el libro se recalcula solo. Esta vista
no reemplaza esa revisión.</div>"""
    return pagina(C.get('nombre_titulo', caso['persona']), cuerpo,
                  f"{e(C.get('identificacion', ''))} &nbsp;&middot;&nbsp; AÑO GRAVABLE "
                  f"{e(C.get('ano_gravable', ''))} &nbsp;&middot;&nbsp; "
                  f"{e(C.get('fuente', '')).upper()}", '', usuario, pie)
