# -*- coding: utf-8 -*-
"""Hoja 3 · Ingresos — notas 11 y 13, alimentada por datos.py."""
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from build_lib import *

AUT = 'Generador renta'


def build(wb, A, C, T):
    ws = wb.create_sheet('3. Ingresos')
    ws.sheet_properties.tabColor = BLUE[2:]
    s = Sheet(ws, 'B', 'G', BLUE, BLUE_T)
    s.widths({'A': 2.3, 'B': 31.0, 'C': 41.0, 'D': 16.5,
              'E': 16.5, 'F': 15.0, 'G': 16.5})
    UVT = "'1. Resumen'!$G$9"

    s.band('03  ·  RENGLONES R32 / R33 / R36 / R58 / R74',
           'Ingresos por cédula',
           T['sub_ingresos'], h_desc=44.0)
    s.legend('Las casillas con fondo crema son editables: «Certificado» viene prediligenciado con lo reportado —reemplácelo por el valor del certificado— y las casillas de costos y deducciones quedan abiertas.')

    HEAD = [('B', None, 'Pagador', 'left'), ('C', None, 'Concepto', 'left'),
            ('D', None, 'Reportado', 'right'), ('E', None, 'Certificado', 'right'),
            ('F', None, 'Diferencia', 'right'), ('G', None, 'Ingreso', 'right')]

    def partidas(rows):
        r0 = s.r
        if not rows:
            r = s.datarow(h=20.0)
            s.txt(r, 'B', 'Sin registros informados en la exógena', 'F', sz=9.0, i=True, color=MUTED, v='center')
            s.money(r, 'G', 0)
            return r0, r
        for i, (pag, con, val) in enumerate(rows):
            r = s.datarow(zebra=bool(i % 2), h=24.0)
            s.txt(r, 'B', pag, v='center')
            s.txt(r, 'C', con, sz=9.0, color=TEXT2, v='center')
            s.money(r, 'D', val)
            s.mark_input(r, 'E')
            s.money(r, 'E', val)
            s.money(r, 'F', f'=E{r}-D{r}', color=MUTED)
            s.money(r, 'G', f'=D{r}')
        r1 = s.r - 1
        ws.conditional_formatting.add(
            f'F{r0}:F{r1}',
            FormulaRule(formula=[f'F{r0}<>0'], font=Font(bold=True, color=RED)))
        return r0, r1

    # ══════════════ RENTAS DE TRABAJO — R32 ══════════════
    s.section('RENTAS DE TRABAJO — R32 (ART. 103 E.T.)')
    s.head(HEAD)
    t0, t1 = partidas(C['rentas_trabajo'])
    if C['rentas_trabajo']:
        ws[f'E{t0}'].comment = Comment(
            'NOTA 11 — «Reportado» es la información del prevalidador DIAN.\n'
            'Esta casilla es editable: escriba el valor del certificado de ingresos\n'
            'y retenciones (formulario 220). La columna «Diferencia» se calcula sola\n'
            'y «Ingreso» conserva el valor reportado.', AUT, 320, 100)
    if T.get('nota_trabajo'):
        s.note(T['nota_trabajo'], h=29.25)
    A['r32'] = s.subtotal('Subtotal rentas de trabajo (R32)', f'=SUM(G{t0}:G{t1})')
    s.gap()

    # ── INCRNGO de las rentas de trabajo (NOTA 13) ──
    s.section('INGRESOS NO CONSTITUTIVOS DE RENTA — R33  ·  RENTAS DE TRABAJO')
    s.head([('B', None, 'Pagador', 'left'), ('C', None, 'Concepto', 'left'),
            ('D', None, 'Reportado', 'right'), ('E', None, 'Certificado', 'right'),
            ('F', None, 'Diferencia', 'right'), ('G', None, 'Valor', 'right')])
    n0, n1 = partidas(C['incrngo_trabajo'])
    s.note('Arts. 55 y 56 E.T. — los aportes obligatorios a pensión y salud del trabajador son ingreso no constitutivo de renta ni ganancia ocasional y no se someten al límite del 40%.')
    A['r33'] = s.subtotal('Subtotal INCRNGO de rentas de trabajo (R33)', f'=SUM(G{n0}:G{n1})')
    s.gap()

    # ── Rentas exentas de las rentas de trabajo (NOTA 13) ──
    s.section('RENTAS EXENTAS DE LAS RENTAS DE TRABAJO — SUJETAS AL LÍMITE DEL ART. 336 NUM. 3')
    s.head([('B', 'C', 'Concepto', 'left'), ('D', None, 'Base de cálculo', 'right'),
            ('E', 'F', 'Regla aplicada', 'left'), ('G', None, 'Valor', 'right')])
    x0 = s.r
    r = s.datarow(h=24.0)
    s.txt(r, 'B', 'R36 · Cesantías e intereses de cesantías exentos — art. 206 num. 4', 'C', v='center')
    idx = C.get('indices_cesantias_exentas', [])
    base_ces = '=' + '+'.join(f'G{t0 + i}' for i in idx) if idx else 0
    s.money(r, 'D', base_ces)
    s.txt(r, 'E', 'Exención plena · muy por debajo de 350 UVT mensuales', 'F', sz=8.0, i=True, color=MUTED, v='center')
    s.money(r, 'G', f'=D{r}')
    A['x_ces'] = r
    r = s.datarow(zebra=True, h=24.0)
    s.txt(r, 'B', 'Renta exenta del 25% — art. 206 num. 10', 'C', v='center')
    excl = C.get('base_25_excluir', 0)   # honorarios R43 sujetos a costos: fuera de la base
    s.money(r, 'D', f'=G{A["r32"]}-G{A["r33"]}-G{A["x_ces"]}' + (f'-{excl}' if excl else ''))
    s.txt(r, 'E', '25% de la base · tope anual de 790 UVT' + (' · excluye honorarios R43 sujetos a costos' if excl else ''),
          'F', sz=8.0, i=True, color=MUTED, v='center')
    s.money(r, 'G', f'=ROUND(MIN(D{r}*0.25,790*{UVT}),0)')
    A['x_25'] = r
    r = s.datarow(h=24.0)
    s.txt(r, 'B', 'Otras rentas exentas de las rentas de trabajo', 'C', v='center')
    s.txt(r, 'E', 'Aportes voluntarios a pensión y cuentas AFC · arts. 126-1 y 126-4', 'F', sz=8.0, i=True, color=MUTED, v='center')
    s.mark_input(r, 'G'); s.money(r, 'G', 0)
    A['x_otras'] = r
    x1 = s.r - 1
    s.note('NOTA 13 — Las rentas exentas de trabajo se detallan aquí, pero se imputan en la hoja «6. Liquidación» dentro del límite conjunto del art. 336 num. 3 (40% de la renta líquida, tope 1.340 UVT).', h=22.0)
    A['exentas_trab'] = s.subtotal('Subtotal rentas exentas de trabajo', f'=SUM(G{x0}:G{x1})')
    s.gap()

    tope_t = s.r
    s.subtotal('Tope de costos y deducciones · 60% de los ingresos de rentas de trabajo — no puede superarse',
               f'=ROUND(G{A["r32"]}*0.6,0)', accent=GOLD, tint=GOLD_T)
    ws[f'G{tope_t}'].comment = Comment(
        'NOTA 13 — 60% de los ingresos de esta subcédula.\n'
        'Los costos y deducciones imputables no pueden superar este porcentaje.', AUT, 300, 70)
    A['tope60_trab'] = tope_t
    s.gap(); s.gap()

    # ══════════════ RENTAS DE CAPITAL — R58 ══════════════
    s.section('RENTAS DE CAPITAL — R58 (ART. 338 E.T.)')
    s.head(HEAD)
    c0, c1 = partidas(C['rentas_capital'])
    if T.get('nota_capital'):
        s.note(T['nota_capital'], h=29.25)
    A['r58'] = s.subtotal('Subtotal rentas de capital (R58)', f'=SUM(G{c0}:G{c1})')
    s.gap()

    s.section('DEPURACIÓN DE LAS RENTAS DE CAPITAL')
    s.head([('B', 'C', 'Concepto', 'left'), ('D', 'F', 'Referencia normativa', 'left'),
            ('G', None, 'Valor', 'right')])
    r = s.datarow()
    s.txt(r, 'B', 'R59 · Ingresos no constitutivos de renta — componente inflacionario', 'C')
    s.txt(r, 'D', 'Art. 38 E.T. — porcentaje fijado por decreto reglamentario; se liquida en cero mientras no esté publicado', 'F', sz=8.0, i=True, color=MUTED)
    s.mark_input(r, 'G'); s.money(r, 'G', 0)
    A['incr58'] = r
    r = s.datarow(zebra=True)
    s.txt(r, 'B', 'R67 · Costos y deducciones procedentes', 'C')
    s.txt(r, 'D', 'Art. 339 E.T. — comisión de administración inmobiliaria, predial, seguros, reparaciones y depreciación de los inmuebles arrendados', 'F', sz=8.0, i=True, color=MUTED)
    s.mark_input(r, 'G'); s.money(r, 'G', 0)
    A['costos58'] = r
    ws[f'G{r}'].comment = Comment(
        'NOTA 13 — Casilla editable para los costos y deducciones procedentes\n'
        'de esta subcédula. No deben superar el tope del 60% que aparece abajo.', AUT, 300, 70)
    s.note('NOTA 13 — Las rentas de capital admiten ingresos no constitutivos de renta y costos y deducciones procedentes (art. 339 E.T.). Diligéncielos con los soportes: no se informan en la exógena y son plenamente procedentes con certificado.', h=22.0)
    tope_c = s.r
    s.subtotal('Tope de costos y deducciones · 60% de los ingresos de rentas de capital — no puede superarse',
               f'=ROUND(G{A["r58"]}*0.6,0)', accent=GOLD, tint=GOLD_T)
    A['tope60_cap'] = tope_c
    s.gap()

    if T.get('callout_reclasificacion'):
        titulo, cuerpo = T['callout_reclasificacion']
        s.callout(titulo, cuerpo, h=48.0)
        s.gap()

    # ══════════════ RENTAS NO LABORALES — R74 ══════════════
    s.section('RENTAS NO LABORALES — R74')
    s.head(HEAD)
    l0, l1 = partidas(C['rentas_no_laborales'])
    A['r74'] = s.subtotal('Subtotal rentas no laborales (R74)', f'=SUM(G{l0}:G{l1})')
    s.gap()

    s.section('DEPURACIÓN DE LAS RENTAS NO LABORALES')
    s.head([('B', 'C', 'Concepto', 'left'), ('D', 'F', 'Referencia normativa', 'left'),
            ('G', None, 'Valor', 'right')])
    r = s.datarow()
    s.txt(r, 'B', 'Ingresos no constitutivos de renta', 'C')
    s.txt(r, 'D', 'Arts. 36 a 57-2 E.T. — no se informan en la exógena para esta subcédula', 'F', sz=8.0, i=True, color=MUTED)
    s.mark_input(r, 'G'); s.money(r, 'G', 0)
    A['incr74'] = r
    r = s.datarow(zebra=True)
    s.txt(r, 'B', 'Costos y deducciones procedentes', 'C')
    s.txt(r, 'D', 'Art. 341 E.T. — costos y gastos con relación de causalidad, necesidad y proporcionalidad', 'F', sz=8.0, i=True, color=MUTED)
    s.mark_input(r, 'G'); s.money(r, 'G', 0)
    A['costos74'] = r
    tope_l = s.r
    s.subtotal('Tope de costos y deducciones · 60% de los ingresos de rentas no laborales — no puede superarse',
               f'=ROUND(G{A["r74"]}*0.6,0)', accent=GOLD, tint=GOLD_T)
    A['tope60_nol'] = tope_l
    s.gap(); s.gap()

    # ══════════════ CONSOLIDADO ══════════════
    s.section('CONSOLIDADO DE INGRESOS')
    s.head([('B', 'F', 'Subcédula', 'left'), ('G', None, 'Valor', 'right')])
    for lab, ref in [('R32 · Rentas de trabajo', A['r32']),
                     ('R58 · Rentas de capital', A['r58']),
                     ('R74 · Rentas no laborales', A['r74'])]:
        r = s.datarow(zebra=True)
        s.txt(r, 'B', lab, 'F', b=True)
        s.money(r, 'G', f'=G{ref}')
    A['ing_total'] = s.hero('TOTAL INGRESOS BRUTOS CÉDULA GENERAL',
                            f'=G{A["r32"]}+G{A["r58"]}+G{A["r74"]}')
    r = s.datarow(h=18.0)
    s.txt(r, 'B', 'Referencia · 60% del total de la cédula general', 'F', sz=8.6, i=True, color=MUTED)
    s.money(r, 'G', f'=ROUND(G{A["ing_total"]}*0.6,0)', sz=9.2, b=True, color=GOLD)
    s.note('NOTA 13 — El tope del 60% se calcula sobre los ingresos de cada subcédula por separado; esta línea es solo una referencia agregada.')

    ws.freeze_panes = 'A6'
    return ws
