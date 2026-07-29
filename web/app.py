# -*- coding: utf-8 -*-
"""RENTA IA — bandeja del contador.

Sin dependencias externas: solo la librería estándar. Descubre los casos en
..\\clientes\\<Contribuyente>\\AG<año>\\datos.py, los agrupa por contribuyente,
calcula sus cifras con el validador (calculos.py), les asigna semáforo y permite
descargar el libro generado.

Uso:  python app.py        →  http://localhost:8765
"""
import html
import os
import re
import sys
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

BASE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(BASE)
sys.path.insert(0, os.path.join(RAIZ, 'generador'))

import autogen
import calculos

PUERTO = 8765
SUBIDAS = os.path.join(RAIZ, 'subidas')
os.makedirs(SUBIDAS, exist_ok=True)

MARCA = 'RENTA IA'
LEMA = 'Declaraciones de renta de personas naturales, desde la exógena de la DIAN'

SEM = {
    'VERDE':    ('#1C6F43', 'Listo para revisar',   'Los topes de la DIAN cuadran y no hay alertas altas'),
    'AMARILLO': ('#8D6209', 'Alertas por resolver', 'Los topes cuadran, pero hay hallazgos de severidad ALTA'),
    'ROJO':     ('#A32C33', 'No liberar',           'Los totales no reconstruyen los topes: clasificación incompleta'),
}
SEM_CORTO = {'VERDE': 'LISTO', 'AMARILLO': 'CON ALERTAS', 'ROJO': 'NO LIBERAR'}
SEV_COLOR = {'ALTA': '#A32C33', 'MEDIA': '#8D6209', 'VERIFICADO': '#1C6F43',
             'NORMATIVO': '#1D5A8C', 'INFORMATIVO': '#6A8085'}


def pesos(v):
    s = '−' if v < 0 else ''
    return f'{s}$ {abs(int(round(v))):,}'.replace(',', '.')


def e(t):
    return html.escape(str(t), quote=True)


def iniciales(nombre):
    palabras = [p for p in str(nombre).split() if len(p) > 2]
    return ''.join(p[0] for p in palabras[:2]).upper() or '?'


# ─────────────────────────── datos ───────────────────────────

def casos():
    """Lista plana de casos; cada uno es un año gravable de un contribuyente."""
    out = []
    cdir = os.path.join(RAIZ, 'clientes')
    if not os.path.isdir(cdir):
        return out
    for persona in sorted(os.listdir(cdir)):
        pdir = os.path.join(cdir, persona)
        if not os.path.isdir(pdir):
            continue
        for ano in sorted(os.listdir(pdir), reverse=True):
            adir = os.path.join(pdir, ano)
            dpath = os.path.join(adir, 'datos.py')
            if not os.path.isfile(dpath):
                continue
            libro = None
            for f in sorted(os.listdir(adir)):
                if f.lower().endswith('.xlsx') and f.startswith('Declaracion'):
                    libro = f
            reg = {'persona': persona, 'ano': ano, 'dir': adir, 'libro': libro}
            try:
                reg['calc'] = calculos.calcular(dpath)
                reg['C'] = reg['calc']['cliente']
            except Exception as ex:
                reg['error'] = str(ex)
            out.append(reg)
    return out


def agrupar(lista):
    """Agrupa los casos por contribuyente, año más reciente primero."""
    grupos = {}
    for i, c in enumerate(lista):
        g = grupos.setdefault(c['persona'], {'persona': c['persona'], 'filas': []})
        g['filas'].append((i, c))
        if 'C' in c and 'ident' not in g:
            g['ident'] = c['C']['identificacion']
            g['titulo'] = c['C']['nombre_titulo']
    for g in grupos.values():
        g.setdefault('ident', '—')
        g.setdefault('titulo', g['persona'])
        g['filas'].sort(key=lambda x: x[1]['ano'], reverse=True)
    return sorted(grupos.values(), key=lambda g: g['titulo'])


# ─────────────────────────── estilos ───────────────────────────

ESTILO = """
:root{--ink:#12262B;--teal:#0D6E64;--teal-2:#0A5A52;--acc:#48B9AA;--teal-t:#E3EFED;
--zebra:#F7FAF9;--bord:#DCE5E3;--bord-2:#B3C3C0;--muted:#6A8085;--text2:#3D5459;
--crema:#FDF6E7;--crema-b:#D9BE86;--fondo:#F4F7F6;}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-font-smoothing:antialiased}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--fondo);color:var(--ink);
font-size:15px;line-height:1.5}
a{color:var(--teal)}

/* ── HERO ── */
.hero{background:linear-gradient(135deg,#12262B 0%,#123A3A 55%,#0D6E64 140%);color:#fff;
position:relative;overflow:hidden}
.hero::after{content:'';position:absolute;right:-120px;top:-140px;width:460px;height:460px;
border-radius:50%;background:radial-gradient(circle,rgba(72,185,170,.22),transparent 68%)}
.hero-in{max-width:1120px;margin:0 auto;padding:30px 28px 26px;position:relative;z-index:1}
.marca{display:flex;align-items:center;gap:13px}
.logo{width:42px;height:42px;border-radius:9px;background:linear-gradient(150deg,var(--acc),var(--teal));
display:grid;place-items:center;font-family:Georgia,serif;font-weight:700;font-size:19px;color:#04231F;
box-shadow:0 3px 14px rgba(72,185,170,.35);flex:none}
.wordmark{font-family:Georgia,serif;font-size:29px;font-weight:700;letter-spacing:-.4px;line-height:1.1}
.wordmark span{color:var(--acc)}
.lema{color:#9FBDB8;font-size:13px;margin-top:2px}
.hero-sub{color:#8FA9A6;font-size:12.5px;margin-top:14px;letter-spacing:.02em}
.stats{display:flex;margin-top:22px;border-top:1px solid rgba(255,255,255,.13);padding-top:16px;
flex-wrap:wrap}
.stat{padding-right:34px;margin-right:34px;border-right:1px solid rgba(255,255,255,.13)}
.stat:last-child{border-right:none;margin-right:0;padding-right:0}
.stat .n{font-size:25px;font-weight:700;font-family:Georgia,serif;line-height:1.1}
.stat .l{font-size:10.5px;letter-spacing:.13em;color:#8FA9A6;text-transform:uppercase;
margin-top:3px;font-weight:600}
.stat.v .n{color:#5FD3A8}.stat.a .n{color:#E8B84B}.stat.r .n{color:#F08A8F}

.wrap{max-width:1120px;margin:24px auto 60px;padding:0 28px}

/* ── SUBIDA ── */
.subir{background:#fff;border:1px solid var(--bord);border-radius:10px;padding:22px 24px;
margin-bottom:26px;box-shadow:0 1px 3px rgba(18,38,43,.05)}
.subir h2{font-family:Georgia,serif;font-size:19px}
.subir p{font-size:13.2px;color:var(--text2);margin:5px 0 15px;max-width:82ch}
.zona{display:block;border:2px dashed var(--crema-b);background:var(--crema);padding:26px;
text-align:center;border-radius:8px;cursor:pointer;transition:.15s}
.zona:hover,.zona.hover{border-color:var(--teal);background:var(--teal-t)}
.zona input{display:none}
.zona .ic{font-size:26px;line-height:1}
.zona .txt{font-size:14px;color:#5C4A15;margin-top:7px}
.zona.hover .txt{color:var(--teal-2)}
.zona .arch{font-weight:700;color:var(--teal);margin-top:7px;font-size:13px}
button{margin-top:15px;background:var(--teal);color:#fff;border:none;font-size:14px;font-weight:600;
padding:10px 22px;border-radius:6px;cursor:pointer;font-family:inherit;transition:.15s}
button:hover{background:var(--teal-2)}
button:disabled{background:var(--muted);cursor:progress}
.pasos{display:flex;gap:7px;font-size:11.5px;color:var(--muted);margin-top:14px;flex-wrap:wrap}
.pasos span{background:var(--zebra);border:1px solid var(--bord);padding:4px 11px;border-radius:20px}

/* ── BUSCADOR ── */
.barra{display:flex;align-items:center;gap:14px;margin-bottom:14px;flex-wrap:wrap}
.barra h2{font-family:Georgia,serif;font-size:20px;flex:1}
.barra .cuenta{font-size:12.5px;color:var(--muted)}
#q{border:1px solid var(--bord);border-radius:7px;padding:9px 13px;font-size:13.5px;
font-family:inherit;width:270px;background:#fff;color:var(--ink)}
#q:focus{outline:2px solid var(--acc);outline-offset:-1px;border-color:transparent}

/* ── FICHA DE CONTRIBUYENTE ── */
.persona{background:#fff;border:1px solid var(--bord);border-radius:10px;margin-bottom:16px;
overflow:hidden;box-shadow:0 1px 3px rgba(18,38,43,.05)}
.p-cab{display:flex;align-items:center;gap:14px;padding:16px 20px;border-bottom:1px solid var(--bord)}
.mono{width:42px;height:42px;border-radius:10px;background:var(--teal-t);color:var(--teal);
display:grid;place-items:center;font-family:Georgia,serif;font-weight:700;font-size:15px;flex:none}
.p-cab h3{font-family:Georgia,serif;font-size:18.5px;line-height:1.25}
.p-cab .cc{font-size:12.5px;color:var(--muted);margin-top:1px}
.p-cab .anos{margin-left:auto;font-size:11.5px;color:var(--muted);white-space:nowrap}
.ano{display:grid;grid-template-columns:132px 1fr auto;gap:18px;align-items:center;
padding:14px 20px;border-bottom:1px solid var(--zebra)}
.ano:last-child{border-bottom:none}
.ano:hover{background:var(--zebra)}
.ag{font-family:Georgia,serif;font-weight:700;font-size:16px}
.ag .pt{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px;vertical-align:1px}
.ag .est{display:block;font-size:9.5px;letter-spacing:.09em;font-weight:700;margin-top:3px}
.cifras{display:flex;gap:30px;flex-wrap:wrap}
.cif .l{font-size:9.5px;letter-spacing:.11em;color:var(--muted);font-weight:700;text-transform:uppercase}
.cif .v{font-size:15.5px;font-weight:700;margin-top:2px;font-variant-numeric:tabular-nums}
.cif .v.fav{color:#1C6F43}
.acc{display:flex;gap:8px;white-space:nowrap}
a.btn{display:inline-block;background:var(--teal);color:#fff;text-decoration:none;font-size:12.5px;
font-weight:600;padding:8px 14px;border-radius:6px;transition:.15s}
a.btn:hover{background:var(--teal-2)}
a.btn.sec{background:#fff;color:var(--teal);border:1px solid var(--bord-2)}
a.btn.sec:hover{background:var(--teal-t);border-color:var(--teal)}
.alertitas{font-size:11.5px;color:var(--muted);margin-top:5px}

/* ── DETALLE ── */
.migas{font-size:13px;margin-bottom:16px}
.cinta{display:flex;align-items:center;gap:14px;background:#fff;border:1px solid var(--bord);
border-left:5px solid var(--sem);border-radius:9px;padding:14px 18px;margin-bottom:22px;flex-wrap:wrap}
.cinta .tit{font-weight:700;font-size:14.5px;color:var(--sem)}
.cinta .des{font-size:12.5px;color:var(--text2);flex:1}
table{border-collapse:collapse;width:100%;background:#fff;border:1px solid var(--bord);
border-radius:9px;overflow:hidden;margin:8px 0 22px}
caption{text-align:left;font-size:10.5px;letter-spacing:.13em;font-weight:700;color:var(--teal);
padding:0 2px 8px;text-transform:uppercase}
th{background:var(--teal);color:#fff;font-size:11.5px;text-align:left;padding:9px 14px;
font-weight:600;letter-spacing:.03em}
td{padding:9px 14px;border-bottom:1px solid var(--zebra);font-size:13.5px}
tr:last-child td{border-bottom:none}
tbody tr:nth-child(even) td{background:#FBFCFC}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
th.n{text-align:right}
.chip{font-size:9.5px;font-weight:700;color:#fff;padding:3px 9px;border-radius:20px;
white-space:nowrap;letter-spacing:.05em}
.ok{color:#1C6F43;font-weight:700}.mal{color:#A32C33;font-weight:700}
.aviso{background:var(--crema);border:1px solid var(--crema-b);border-radius:8px;padding:13px 17px;
font-size:12.8px;color:#5C4A15;margin-top:22px;line-height:1.55}
.err{background:#F8EAEA;border:1px solid #A32C33;border-radius:8px;color:#7A1F24;padding:13px 17px;
font-size:13.5px;margin-bottom:20px}
.vacio{background:#fff;border:1px dashed var(--bord-2);border-radius:10px;padding:40px;
text-align:center;color:var(--muted);font-size:14px}
footer{margin:40px 0 24px;text-align:center;font-size:11.5px;color:var(--muted);line-height:1.7}
footer b{color:var(--text2)}
"""


def hero(sub, stats_html=''):
    return f"""<div class="hero"><div class="hero-in">
<div class="marca"><div class="logo">R</div>
  <div><div class="wordmark">RENTA<span> IA</span></div><div class="lema">{LEMA}</div></div></div>
<div class="hero-sub">{sub}</div>{stats_html}
</div></div>"""


def pagina(titulo, cuerpo, sub='', stats=''):
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(titulo)} · {MARCA}</title><style>{ESTILO}</style></head><body>
{hero(sub, stats)}
<div class="wrap">{cuerpo}
<footer><b>{MARCA}</b> · versión local · los datos no salen de este equipo<br>
Documento de trabajo: la liquidación se revisa y se libera antes de presentarla a la DIAN</footer>
</div></body></html>"""


# ─────────────────────────── vistas ───────────────────────────

FORMULARIO = """
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
  </form>
</div>
<script>
var z=document.getElementById('z'),a=document.getElementById('a'),
    n=document.getElementById('n'),f=document.getElementById('f'),b=document.getElementById('b');
a.onchange=function(){n.textContent=a.files.length?a.files[0].name:''};
['dragenter','dragover'].forEach(function(ev){z.addEventListener(ev,function(x){
  x.preventDefault();z.classList.add('hover')})});
['dragleave','drop'].forEach(function(ev){z.addEventListener(ev,function(x){
  x.preventDefault();z.classList.remove('hover')})});
z.addEventListener('drop',function(x){a.files=x.dataTransfer.files;
  n.textContent=a.files.length?a.files[0].name:''});
f.addEventListener('submit',function(){b.disabled=true;b.textContent='Procesando…';});
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


def vista_bandeja(lista, error=''):
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
        filas = []
        for i, c in g['filas']:
            if 'error' in c:
                filas.append(f'<div class="ano"><div class="ag">{e(c["ano"])}</div>'
                             f'<div><span class="mal">datos.py con error:</span> '
                             f'<span class="alertitas">{e(c["error"])[:110]}</span></div>'
                             f'<div class="acc"></div></div>')
                continue
            cal = c['calc']
            color, etiqueta, _ = SEM[cal['semaforo']]
            saldo = cal['saldo']
            clase = 'fav' if saldo < 0 else ''
            rot = 'Saldo a favor' if saldo < 0 else 'Saldo a pagar'
            libro = (f'<a class="btn" href="/libro/{i}">Libro</a>' if c['libro']
                     else '<span class="alertitas">sin libro</span>')
            filas.append(f"""<div class="ano">
  <div class="ag"><span class="pt" style="background:{color}"></span>{e(c['ano'])}
    <span class="est" style="color:{color}">{SEM_CORTO[cal['semaforo']]}</span></div>
  <div><div class="cifras">
    <div class="cif"><div class="l">Ingresos</div><div class="v">{pesos(cal['ingresos'])}</div></div>
    <div class="cif"><div class="l">Impuesto</div><div class="v">{pesos(cal['impuesto'])}</div></div>
    <div class="cif"><div class="l">{rot}</div><div class="v {clase}">{pesos(abs(saldo))}</div></div>
  </div><div class="alertitas">{len(c['C']['alertas'])} alertas &middot; {cal['n_altas']} de severidad alta</div></div>
  <div class="acc"><a class="btn sec" href="/caso/{i}">Revisar</a>{libro}</div>
</div>""")
        busca = e((g['titulo'] + ' ' + str(g['ident'])).lower())
        fichas.append(f"""<div class="persona" data-busca="{busca}">
  <div class="p-cab"><div class="mono">{e(iniciales(g['titulo']))}</div>
    <div><h3>{e(g['titulo'])}</h3><div class="cc">{e(g['ident'])}</div></div>
    <div class="anos">{len(g['filas'])} año(s) gravable(s)</div></div>
  {''.join(filas)}
</div>""")

    listado = ''.join(fichas) if fichas else (
        '<div class="vacio">Todavía no hay casos. Suba una exógena para empezar.</div>')
    plural = 's' if len(grupos) != 1 else ''
    cuerpo = ((f'<div class="err">{e(error)}</div>' if error else '')
              + FORMULARIO
              + f'<div class="barra"><h2>Contribuyentes</h2>'
                f'<span class="cuenta" id="cuenta">{len(grupos)} contribuyente{plural}</span>'
                f'<input id="q" type="search" placeholder="Buscar por nombre o cédula…"></div>'
              + listado + BUSCADOR
              + '<div class="aviso"><b>Cómo leer el semáforo.</b> '
                '<b>VERDE</b>: los totales reconstruidos reproducen los topes precalculados por la '
                'DIAN y no hay hallazgos altos. <b>AMARILLO</b>: los topes cuadran, pero hay alertas '
                'de severidad ALTA que deben resolverse. <b>ROJO</b>: los totales no cuadran — hay '
                'una partida mal clasificada y el caso no debe liberarse. El libro de 9 hojas se '
                'descarga y se termina en Excel con los certificados del contribuyente.</div>')
    return pagina('Bandeja', cuerpo,
                  'BANDEJA DEL CONTADOR &nbsp;&middot;&nbsp; CADA CASO SE VALIDA CONTRA LOS TOPES DE LA DIAN',
                  stats)


def vista_caso(i, caso):
    c, C = caso['calc'], caso['C']
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
            tol = calculos.clasificador.tolerancia(c['topes_dian'][k])
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
    col = '#1C6F43' if saldo < 0 else '#12262B'
    filas_cifras.append(f'<tr style="font-weight:700;color:{col}"><td>{rot}</td>'
                        f'<td class="n">{pesos(abs(saldo))}</td></tr>')

    filas_alertas = []
    for cod, sev, hallazgo, detalle, accion in C['alertas']:
        filas_alertas.append(
            f'<tr><td><b>{e(cod)}</b></td>'
            f'<td><span class="chip" style="background:{SEV_COLOR.get(sev, "#6A8085")}">{e(sev)}</span></td>'
            f'<td><b>{e(hallazgo)}</b><br>'
            f'<span style="color:var(--text2);font-size:12.5px">{e(detalle)}</span><br>'
            f'<span style="color:var(--muted);font-size:12.5px"><i>&rarr; {e(accion)}</i></span></td></tr>')

    libro = (f'<a class="btn" href="/libro/{i}">Descargar libro de 9 hojas</a>'
             if caso['libro'] else '')
    cuerpo = f"""
<div class="migas"><a href="/">&larr; Volver a la bandeja</a></div>
<div class="cinta" style="--sem:{color}">
  <span class="chip" style="background:{color}">{e(c['semaforo'])}</span>
  <span class="tit">{e(etiqueta)}</span><span class="des">{e(explica)}</span>{libro}</div>
<table><caption>Validación contra los topes precalculados por la DIAN</caption>
<thead><tr><th>Tope</th><th class="n">DIAN</th><th class="n">Reconstruido</th><th>Estado</th></tr></thead>
<tbody>{''.join(filas_topes)}</tbody></table>
<table><caption>Cifras clave</caption>
<thead><tr><th>Concepto</th><th class="n">Valor</th></tr></thead>
<tbody>{''.join(filas_cifras)}</tbody></table>
<table><caption>Hallazgos por resolver antes de liberar</caption>
<thead><tr><th style="width:46px">Cód.</th><th style="width:112px">Severidad</th>
<th>Hallazgo &middot; detalle &middot; acción</th></tr></thead>
<tbody>{''.join(filas_alertas)}</tbody></table>
<div class="aviso"><b>Estas cifras las calcula el validador</b> con los datos de la exógena tal cual.
El libro de Excel es el papel de trabajo definitivo: sus casillas de fondo crema quedan abiertas
para los certificados del contribuyente, y al diligenciarlas el libro se recalcula solo. Esta vista
no reemplaza esa revisión.</div>"""
    return pagina(C['nombre_titulo'], cuerpo,
                  f"{e(C['identificacion'])} &nbsp;&middot;&nbsp; AÑO GRAVABLE {e(C['ano_gravable'])}"
                  f" &nbsp;&middot;&nbsp; {e(C['fuente']).upper()}")


# ─────────────────────────── servidor ───────────────────────────

def _multipart(cuerpo, content_type):
    """Extrae (nombre_archivo, bytes) de un multipart/form-data. Sin cgi."""
    m = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', content_type or '')
    if not m:
        raise ValueError('Envío sin boundary.')
    frontera = ('--' + (m.group(1) or m.group(2)).strip()).encode()
    for parte in cuerpo.split(frontera):
        if b'\r\n\r\n' not in parte:
            continue
        cab, datos = parte.split(b'\r\n\r\n', 1)
        fn = re.search(r'filename="([^"]*)"', cab.decode('utf-8', 'replace'))
        if fn and fn.group(1):
            return fn.group(1), datos.rstrip(b'\r\n-')
    raise ValueError('No se recibió ningún archivo.')


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
                return self._html(vista_bandeja(casos()))
            if ruta.startswith('/caso/'):
                lista = casos()
                caso = lista[int(ruta.split('/')[2])]
                if 'error' in caso:
                    return self._html(pagina('Error', f'<div class="err">{e(caso["error"])}</div>'
                                             '<p><a href="/">&larr; Volver</a></p>'), 500)
                return self._html(vista_caso(int(ruta.split('/')[2]), caso))
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
            self._html(pagina('No encontrado', '<div class="vacio">Esa página no existe. '
                                               '<a href="/">Volver a la bandeja</a></div>'), 404)
        except Exception as ex:
            self._html(pagina('Error', f'<div class="err">{e(ex)}</div>'
                                       '<p><a href="/">&larr; Volver</a></p>'), 500)

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != '/subir':
            return self._html(pagina('No encontrado', '<p><a href="/">&larr; Volver</a></p>'), 404)
        try:
            largo = int(self.headers.get('Content-Length') or 0)
            if largo <= 0:
                raise ValueError('El envío llegó vacío.')
            if largo > 25 * 1024 * 1024:
                raise ValueError('El archivo supera los 25 MB.')
            nombre, datos = _multipart(self.rfile.read(largo), self.headers.get('Content-Type'))
            if not nombre.lower().endswith('.xlsx'):
                raise ValueError(
                    f'«{nombre}» no es un .xlsx. Si su reporte está en el formato .xls antiguo, '
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
            self._html(vista_bandeja(casos(), f'No se pudo procesar el archivo: {ex}'), 400)

    def log_message(self, fmt, *args):
        pass


if __name__ == '__main__':
    servidor = ThreadingHTTPServer(('127.0.0.1', PUERTO), Handler)
    servidor.daemon_threads = True
    print(f'{MARCA} → http://localhost:{PUERTO}')
    servidor.serve_forever()
