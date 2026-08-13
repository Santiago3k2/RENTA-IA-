# -*- coding: utf-8 -*-
r"""El apartado RST de la web: bandeja de recibos del SIMPLE y detalle de uno.

Comparte identidad y hoja de estilos con el apartado de Renta (`web\render.py`)
a propósito: son dos regímenes, no dos aplicaciones. Lo único que cambia es lo
que se muestra —aquí el período es un bimestre y las cifras son las del
Formulario 2593— y el semáforo, que en el SIMPLE sale de razones que deben dar
exactas en vez de los topes precalculados de la DIAN.
"""
import legal
import render
from render import AMBAR, AZUL, ESTADO_ET, GRIS, ROJO, VERDE, e, pesos

PRIORIDAD_COLOR = {'ALTA': ROJO, 'MEDIA': AMBAR, 'BAJA': GRIS}

SEM_RST = {
    'VERDE': (VERDE, 'Listo para revisar',
              'Las razones del IVA cuadran y no hay alertas altas'),
    'AMARILLO': (AMBAR, 'Alertas por resolver',
                 'Las comprobaciones cuadran, pero hay puntos de prioridad ALTA'),
    'ROJO': (ROJO, 'No presentar',
             'Alguna comprobación no cuadra: hay partidas mal leídas o mal clasificadas'),
}
SEM_CORTO = {'VERDE': 'LISTO', 'AMARILLO': 'CON ALERTAS', 'ROJO': 'NO PRESENTAR'}

SUB = ('RÉGIMEN SIMPLE DE TRIBUTACIÓN &nbsp;&middot;&nbsp; ANTICIPO BIMESTRAL '
       '&nbsp;&middot;&nbsp; FORMULARIO 2593')


def _uvt(v):
    return f'{float(v):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _pct(v):
    return f'{float(v) * 100:,.2f}'.replace('.', ',') + ' %'


def _entero(v):
    return f'{int(v):,}'.replace(',', '.')


# ─────────────────────────────────────────────────────────── bandeja

def _fila_recibo(c, mostrar_estado):
    f = c['fila']
    sem = c.get('semaforo') or 'AMARILLO'
    color = SEM_RST.get(sem, SEM_RST['AMARILLO'])[0]
    libro = (f'<a class="btn" href="/rst/libro/{e(c["ref"])}">Libro</a>'
             if f.get('libro_path') else '<span class="alertitas">sin libro</span>')
    marca = ''
    if mostrar_estado:
        col, txt = ESTADO_ET.get(c.get('estado', 'borrador'), ESTADO_ET['borrador'])
        marca = f'<span class="pill" style="color:{col}">{txt.upper()}</span>'
    return f"""<div class="ano">
  <div class="ag"><span class="pt" style="background:{color}"></span>{e(c['periodo'])}
    <span class="est" style="color:{color}">{SEM_CORTO.get(sem, sem)}</span></div>
  <div><div class="cifras">
    <div class="cif"><div class="l">Base del anticipo</div>
      <div class="v">{pesos(f.get('base') or 0)}</div></div>
    <div class="cif"><div class="l">Anticipo neto</div>
      <div class="v">{pesos(f.get('anticipo_neto') or 0)}</div></div>
    <div class="cif"><div class="l">Total a pagar</div>
      <div class="v">{pesos(f.get('total_pagar') or 0)}</div></div>
  </div><div class="alertitas">Año gravable {e(c['ano'])} &middot; grupo {e(f.get('grupo'))}
    &middot; {e(f.get('municipio') or '—')}{marca}</div></div>
  <div class="acc"><a class="btn sec" href="/rst/{e(c['ref'])}">Revisar</a>{libro}</div>
</div>"""


def _agrupar(lista):
    """Por contribuyente, con los bimestres adentro."""
    grupos = {}
    for c in lista:
        g = grupos.setdefault(c['persona'], {'titulo': c['persona'],
                                             'ident': c['identificacion'], 'filas': []})
        g['filas'].append(c)
    return sorted(grupos.values(), key=lambda g: g['titulo'].lower())


def vista_bandeja(lista, error='', usuario='', pie=render.PIE_LOCAL,
                  mostrar_estado=False, nav='', rol='', token='', hecho='',
                  puede_subir=True, cupo=None):
    grupos = _agrupar(lista)
    conteo = {'VERDE': 0, 'AMARILLO': 0, 'ROJO': 0}
    total = 0
    for c in lista:
        conteo[c.get('semaforo') or 'AMARILLO'] = conteo.get(c.get('semaforo') or 'AMARILLO', 0) + 1
        total += c['fila'].get('total_pagar') or 0

    stats = f"""<div class="stats">
<div class="stat"><div class="n">{len(grupos)}</div><div class="l">Contribuyentes</div></div>
<div class="stat"><div class="n">{len(lista)}</div><div class="l">Recibos 2593</div></div>
<div class="stat v"><div class="n">{conteo['VERDE']}</div><div class="l">Listos</div></div>
<div class="stat a"><div class="n">{conteo['AMARILLO']}</div><div class="l">Con alertas</div></div>
<div class="stat r"><div class="n">{conteo['ROJO']}</div><div class="l">No presentar</div></div>
</div>"""

    fichas = []
    for g in grupos:
        filas = ''.join(_fila_recibo(c, mostrar_estado) for c in g['filas'])
        busca = e((g['titulo'] + ' ' + str(g['ident'])).lower())
        fichas.append(f"""<div class="persona" data-busca="{busca}">
  <div class="p-cab"><div class="mono">{e(render.iniciales(g['titulo']))}</div>
    <div><h3>{e(g['titulo'])}</h3><div class="cc">NIT {e(g['ident'])}</div></div>
    <div class="anos">{len(g['filas'])} bimestre(s)</div></div>
  {filas}
</div>""")

    listado = ''.join(fichas) if fichas else (
        '<div class="vacio">Todavía no hay recibos del SIMPLE. Suba un consolidado '
        'de facturación electrónica para empezar.</div>')
    plural = 's' if len(grupos) != 1 else ''
    cuerpo = ((f'<div class="err">{e(error)}</div>' if error else '')
              + (f'<div class="ok-msg">{e(hecho)}</div>' if hecho else '')
              + (formulario(token, cupo) if puede_subir else '')
              + f'<div class="barra"><h2>Contribuyentes del SIMPLE</h2>'
                f'<span class="cuenta" id="cuenta">{len(grupos)} contribuyente{plural}</span>'
                f'<input id="q" type="search" placeholder="Buscar por nombre o NIT…"></div>'
              + listado + render.BUSCADOR)
    return render.pagina('RST', cuerpo, SUB, stats, usuario, pie, nav, rol,
                         apartado='rst')


def formulario(token='', cupo=None):
    """Zona de carga del consolidado + la ficha del contribuyente.

    La ficha son los datos que el archivo de la DIAN no trae y el motor no puede
    adivinar: el grupo de actividad (que es una decisión de criterio, no un
    dato) y la tarifa consolidada de ICA del municipio.
    """
    if cupo and cupo[0] >= cupo[1]:
        return (f'<div class="subir"><h2>Procesar un bimestre del SIMPLE</h2>'
                f'<p>Su cupo está completo: ha procesado <b>{cupo[0]} de {cupo[1]}</b>. '
                f'Puede seguir consultando lo que ya cargó; para ampliarlo, escriba '
                f'al administrador.</p></div>')
    # El grupo NO viene preseleccionado a propósito: define la tarifa y puede
    # duplicar el impuesto. Dejar uno por defecto hacía que se liquidara con él
    # sin que nadie lo hubiera decidido.
    grupos = ('<option value="" disabled selected>Elija el grupo…</option>' + ''.join(
        f'<option value="{n}">Grupo {n} — {e(t)}</option>'
        for n, t in sorted(_GRUPOS.items())))
    # El bimestre sale de las fechas del archivo. Antes quedaba preseleccionado
    # el 1 y un archivo de mayo-junio se liquidaba como enero-febrero: cero
    # facturas dentro del período y un libro entero en ceros.
    bimestres = ('<option value="" selected>Detectar del archivo</option>' + ''.join(
        f'<option value="{n}">{n} — {e(t)}</option>'
        for n, t in sorted(_BIMESTRES.items())))
    return f"""<div class="subir"><h2>Procesar un bimestre del SIMPLE</h2>
<p>Suba el <b>consolidado de documentos electrónicos</b> de la DIAN y complete lo que
ese archivo no trae. El motor liquida el anticipo, arma el libro de 9 hojas y valida
que el IVA sea el 19&nbsp;% de los ingresos gravados y la ReteIVA el 15&nbsp;% del IVA.</p>
<form method="post" action="/rst/subir" enctype="multipart/form-data" class="rst-form">
  <input type="hidden" name="_t" value="{e(token)}">
  <div class="rst-campos">
    <label>Razón social<input name="nombre" required placeholder="Razón social como está en el RUT"></label>
    <label>NIT<input name="nit" required placeholder="sin puntos ni guiones"></label>
    <label>DV<input name="dv" placeholder="del RUT"></label>
    <label>Año gravable<input name="ano" type="number" value="2026" required></label>
    <label>Bimestre<select name="bimestre">{bimestres}</select></label>
    <label class="ancho">Grupo de actividad SIMPLE<select name="grupo" required>{grupos}</select></label>
    <label>Municipio<input name="municipio" required placeholder="donde se ejerce la actividad"></label>
    <label>Código DANE<input name="cod_dane" placeholder="código DANE"></label>
    <label>Departamento<input name="depto" placeholder="departamento"></label>
    <label>Tarifa de ICA (por mil)<input name="tarifa_ica" required placeholder="12,5"></label>
    <label>CIIU<input name="ciiu" placeholder="código CIIU del RUT"></label>
    <label>Responsable de IVA<select name="responsable_iva">
      <option value="1" selected>Sí</option><option value="0">No</option></select></label>
    <label class="ancho">Aporte a pensión pagado en el bimestre (total, 16&nbsp;% del IBC)
      <input name="aporte_pension_total" placeholder="de la planilla PILA — 0 si no hubo"></label>
  </div>
  {legal.bloque()}
  {legal.casilla()}
  <div class="rst-archivo">
    <input type="file" name="archivo" accept=".xlsx" required>
    <button type="submit">Procesar el bimestre</button>
  </div>
  <p class="rst-nota">El <b>bimestre sale de las fechas del archivo</b>: no hace falta
  acertarlo. Si el archivo trae más de un período, se liquida el que tenga más documentos
  y el recibo avisa de los otros. Suba el archivo <b>tal como lo descarga de la DIAN</b>, con las hojas
  <code>Rp_Doc_…</code> (emitidos) y <code>Rp_Docpras</code> (recibidos): el motor deriva de
  ahí el desglose de ingresos, las compras y la conciliación de ReteIVA. No hace falta
  prepararlo antes. Si el archivo ya trae hojas <code>F.VENTA</code> o <code>F.COMPRA</code>
  trabajadas a mano, se respetan. El <b>aporte a pensión</b> no está en la facturación
  electrónica: sin él el anticipo sale más alto de lo debido.</p>
</form></div>"""


_GRUPOS = {1: 'Tiendas, mini/micro-mercados y peluquería',
           2: 'Comercio, industria, servicios técnicos y demás',
           3: 'Servicios profesionales, consultoría y científicos',
           4: 'Expendio de comidas y bebidas, y transporte'}
_BIMESTRES = {1: 'Enero y Febrero', 2: 'Marzo y Abril', 3: 'Mayo y Junio',
              4: 'Julio y Agosto', 5: 'Septiembre y Octubre', 6: 'Noviembre y Diciembre'}


# ─────────────────────────────────────────────────────────── detalle

def vista_recibo(caso, usuario='', pie=render.PIE_LOCAL, mostrar_estado=False,
                 nav='', rol='', acciones='', estilo_extra=''):
    f = caso['fila']
    sem = caso.get('semaforo') or 'AMARILLO'
    color, etiqueta, explica = SEM_RST.get(sem, SEM_RST['AMARILLO'])

    filas_val = []
    for v in (f.get('validaciones') or []):
        if v.get('formato') == '%':
            valor, esperado = _pct(v['valor']), _pct(v['esperado'])
        elif v.get('formato') == 'n':      # conteos: ni pesos ni porcentaje
            valor, esperado = _entero(v['valor']), _entero(v['esperado'])
        else:
            valor, esperado = pesos(v['valor']), pesos(v['esperado'])
        estado = ('<span class="ok">CUADRA</span>' if v.get('ok')
                  else '<span class="mal">REVISAR</span>')
        filas_val.append(
            f'<tr><td>{e(v["nombre"])}<br>'
            f'<span style="color:var(--muted);font-size:12.5px">{e(v["nota"])}</span></td>'
            f'<td class="n">{esperado}</td><td class="n">{valor}</td><td>{estado}</td></tr>')

    cifras = [
        ('Ingresos brutos gravados con IVA (cas. 25)', f.get('ingresos_gravados'), False),
        ('Ingresos brutos no gravados (cas. 26)', f.get('ingresos_no_gravados'), False),
        ('Base del anticipo (cas. 29)', f.get('base'), True),
        (None, None, False),
        ('Anticipo SIMPLE consolidado (cas. 30)', f.get('anticipo_consolidado'), False),
        ('(−) Componente de ICA, se gira al municipio (cas. 43)', -(f.get('ica') or 0), False),
        ('(−) Descuento por aportes a pensión del empleador (cas. 44)',
         -(f.get('descuento_pension') or 0), False),
        ('ANTICIPO NETO A PAGAR (cas. 49)', f.get('anticipo_neto'), True),
        (None, None, False),
        ('IVA generado (cas. 77)', f.get('iva_generado'), False),
        ('(−) Impuestos descontables (cas. 78)', -(float(f.get('iva_descontable') or 0)), False),
        ('(−) Retenciones de IVA practicadas (cas. 80)', -(float(f.get('reteiva') or 0)), False),
        ('TOTAL IVA A PAGAR (cas. 74)', f.get('iva_pagar'), True),
    ]
    filas_cifras = []
    for lab, v, fuerte in cifras:
        if lab is None:
            filas_cifras.append(
                f'<tr><td>Base en UVT &middot; tarifa aplicada</td>'
                f'<td class="n">{_uvt(f.get("base_uvt") or 0)} UVT &middot; '
                f'{_pct(f.get("tarifa") or 0)}</td></tr>')
            continue
        peso = ' style="font-weight:700"' if fuerte else ''
        filas_cifras.append(f'<tr{peso}><td>{e(lab)}</td>'
                            f'<td class="n">{pesos(v or 0)}</td></tr>')
    filas_cifras.append(
        f'<tr style="font-weight:700;color:{AZUL}"><td>TOTAL A PAGAR, APROXIMADO AL MIL '
        f'(cas. 81)</td><td class="n">{pesos(f.get("total_pagar") or 0)}</td></tr>')

    filas_alertas = []
    for a in caso.get('alertas', []):
        col = PRIORIDAD_COLOR.get(a.get('prioridad'), GRIS)
        filas_alertas.append(
            f'<tr><td class="cod"><b>{e(a.get("orden") or "")}</b></td>'
            f'<td><span class="chip" style="background:{col}">{e(a.get("prioridad"))}</span></td>'
            f'<td><b>{e(a.get("tema"))}</b><br>'
            f'<span style="color:var(--text2);font-size:12.5px">{e(a.get("texto"))}</span></td></tr>')

    libro = (f'<a class="btn" href="/rst/libro/{e(caso["ref"])}">Descargar libro de 9 hojas</a>'
             if f.get('libro_path') else '')
    plazo = (f.get('ficha') or {}).get('_plazo') or ''
    aviso_plazo = (f'<div class="aviso" style="margin-bottom:18px"><b>Plazo:</b> {e(plazo)}</div>'
                   if plazo else '')
    marca = ''
    if mostrar_estado:
        colr, txt = ESTADO_ET.get(caso.get('estado', 'borrador'), ESTADO_ET['borrador'])
        marca = f'<span class="pill" style="color:{colr}">{txt.upper()}</span>'

    cuerpo = f"""
<div class="migas"><a href="/rst">&larr; Volver a los recibos del SIMPLE</a></div>
{aviso_plazo}
<div class="cinta" style="--sem:{color}">
  <span class="chip" style="background:{color}">{e(sem)}</span>
  <span class="tit">{e(etiqueta)}</span><span class="des">{e(explica)}{marca}</span>{libro}</div>
<table><caption>Comprobaciones automáticas &middot; de aquí sale el semáforo</caption>
<thead><tr><th>Comprobación</th><th class="n">Esperado</th><th class="n">Obtenido</th>
<th>Estado</th></tr></thead>
<tbody>{''.join(filas_val)}</tbody></table>
<table><caption>Casillas del Formulario 2593</caption>
<thead><tr><th>Concepto</th><th class="n">Valor</th></tr></thead>
<tbody>{''.join(filas_cifras)}</tbody></table>
<table><caption>Puntos por verificar antes de presentar</caption>
<thead><tr><th style="width:56px">#</th><th style="width:104px">Prioridad</th>
<th>Tema &middot; qué revisar</th></tr></thead>
<tbody>{''.join(filas_alertas)}</tbody></table>
<div class="aviso"><b>El libro de Excel es el papel de trabajo definitivo.</b> Sus casillas
de fondo crema quedan abiertas —la tarifa de ICA, la planilla de pensión del mes anterior,
el saldo a favor del bimestre— y al diligenciarlas toda la liquidación se recalcula sola.
Esta vista no reemplaza esa revisión.</div>
{legal.bloque(destacado=False)}{acciones}"""
    return render.pagina(
        caso['persona'], cuerpo,
        f"NIT {e(caso['identificacion'])} &nbsp;&middot;&nbsp; AÑO GRAVABLE {e(caso['ano'])}"
        f" &nbsp;&middot;&nbsp; {e(caso['periodo']).upper()} &nbsp;&middot;&nbsp; GRUPO "
        f"{e(f.get('grupo'))}", '', usuario, pie, nav, rol, estilo_extra,
        apartado='rst')


ESTILO = """
.rst-form{margin-top:14px}
.rst-campos{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.rst-campos label{display:flex;flex-direction:column;gap:5px;font-size:12px;
  letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.rst-campos label.ancho{grid-column:span 2}
.rst-campos input,.rst-campos select{padding:9px 10px;border:1px solid var(--bord);
  border-radius:8px;font:inherit;font-size:14px;text-transform:none;letter-spacing:0;
  color:var(--ink);background:var(--sup)}
.rst-archivo{display:flex;gap:12px;align-items:center;margin-top:16px;flex-wrap:wrap}
.rst-archivo button{padding:11px 20px;border:0;border-radius:8px;background:#18181B;
  color:#fff;font:inherit;font-weight:600;cursor:pointer}
.rst-nota{margin-top:12px;font-size:12.5px;color:var(--muted);line-height:1.6}
.rst-nota code{background:#F4F4F5;padding:1px 5px;border-radius:4px;font-size:12px}
"""
