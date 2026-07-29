# -*- coding: utf-8 -*-
"""Hoja 8 · Consignaciones — topes 3, 4 y 5, alimentada por datos.py."""
from build_lib import *


def build(wb, A, C, T):
    ws = wb.create_sheet('8. Consignaciones')
    ws.sheet_properties.tabColor = GOLD[2:]
    s = Sheet(ws, 'B', 'G', GOLD, GOLD_T)
    s.widths({'A': 2.3, 'B': 24.0, 'C': 17.0, 'D': 30.0,
              'E': 19.0, 'F': 14.0, 'G': 19.0})

    s.band('08  ·  TOPE 4 — MOVIMIENTOS DEL AÑO',
           'Consignaciones bancarias e inversiones',
           T['sub_consignaciones'], h_desc=48.0)
    s.gap()

    # ══════════════ MOVIMIENTOS ══════════════
    s.section('MOVIMIENTOS INFORMADOS')
    s.head([('B', None, 'Entidad', 'left'), ('C', None, 'Cuenta', 'left'),
            ('D', None, 'Tipo de movimiento', 'left'), ('E', None, 'Valor', 'right'),
            ('F', 'G', 'Computa al tope', 'center')])
    m0 = s.r
    for i, (ent, cta, tipo, val) in enumerate(C['movimientos']):
        r = s.datarow(zebra=bool(i % 2))
        s.txt(r, 'B', ent, v='center')
        s.put(r, 'C', cta, F(9.0, color=TEXT2), AL('left', 'center'), '@')
        s.txt(r, 'D', tipo, sz=9.0, color=TEXT2, v='center')
        s.money(r, 'E', val)
        s.put(r, 'F', 'SÍ', F(8.3, True, color=GREEN), AL('center', 'center'), None, 'G')
    m1 = s.r - 1
    A['mov_tope4'] = s.subtotal('Subtotal que computa al tope 4', f'=SUM(E{m0}:E{m1})')
    x0 = s.r
    for i, (ent, cta, tipo, val) in enumerate(C.get('movimientos_excluidos', [])):
        h = 30.0 if len(tipo) > 28 else 19.35
        r = s.datarow(zebra=bool(i % 2), h=h)
        s.txt(r, 'B', ent, v='center')
        s.put(r, 'C', cta, F(9.0, color=TEXT2), AL('left', 'center'), '@')
        s.txt(r, 'D', tipo, sz=9.0, color=TEXT2, v='center')
        s.money(r, 'E', val)
        s.put(r, 'F', 'EXCLUIDA', F(8.3, True, color=MUTED), AL('center', 'center'), None, 'G')
    x1 = s.r - 1
    if T.get('nota_tope4'):
        s.note(T['nota_tope4'], h=29.25)
    rango_total = f'=SUM(E{m0}:E{m1})' if x1 < x0 else f'=SUM(E{m0}:E{m1})+SUM(E{x0}:E{x1})'
    s.subtotal('Total movimientos informados', rango_total)
    s.gap()
    if T.get('callout_cruce'):
        titulo, cuerpo = T['callout_cruce']
        s.callout(titulo, cuerpo, h=47.85)
    s.gap()

    # ══════════════ TOPES COMPLEMENTARIOS ══════════════
    s.section('TOPES COMPLEMENTARIOS INFORMADOS')
    s.head([('B', 'C', 'Concepto', 'left'), ('D', None, 'Detalle', 'left'),
            ('E', None, 'Valor', 'right'), ('F', 'G', '', 'center')])
    c0 = s.r
    for i, (det, val) in enumerate(C['consumos_tarjeta']):
        r = s.datarow(zebra=bool(i % 2))
        if i == 0:
            s.txt(r, 'B', 'Consumos con tarjeta — tope 3', 'C', b=True, v='center')
        else:
            s.txt(r, 'B', None, 'C')
        s.txt(r, 'D', det, sz=9.0, color=TEXT2, v='center')
        s.money(r, 'E', val)
    c1 = s.r - 1
    A['consumos'] = s.subtotal(T.get('label_consumos_total', 'Total consumos con tarjeta'),
                               f'=SUM(E{c0}:E{c1})', lab_col='B', val_col='E')
    r = s.datarow(h=32.7)
    s.txt(r, 'B', 'Compras con factura electrónica — tope 5', 'C', b=True, v='center')
    s.txt(r, 'D', 'Suma de facturas tras ajustes por notas', sz=9.0, color=TEXT2, v='center')
    s.money(r, 'E', C['compras_fe'])
    A['compras'] = r
    r = s.datarow(zebra=True, h=32.7)
    s.txt(r, 'B', None, 'C')
    s.txt(r, 'D', 'Monto susceptible del beneficio del 1%', sz=9.0, color=TEXT2, v='center')
    s.money(r, 'E', C['base_fe'])
    A['base_fe'] = r
    s.note('Base de la deducción del art. 336 par. 5 E.T. — ver hoja «6. Liquidación».')

    ws.freeze_panes = 'A6'
    return ws
