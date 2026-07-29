# -*- coding: utf-8 -*-
"""Hoja 9 · Detalle exógena — trazabilidad de los registros fuente."""
import math
from build_lib import *


def _lineas(texto, ancho):
    return max(1, math.ceil(len(texto or '') / ancho))


def build(wb, A, C, T):
    ws = wb.create_sheet('9. Detalle exógena')
    ws.sheet_properties.tabColor = GREY[2:]
    s = Sheet(ws, 'B', 'G', GREY, ZEBRA)
    s.widths({'A': 2.3, 'B': 11.0, 'C': 28.0, 'D': 44.0,
              'E': 14.0, 'F': 26.0, 'G': 12.0})

    s.band('09  ·  TRAZABILIDAD',
           'Detalle de la información reportada por terceros',
           T['sub_detalle'], h_desc=35.55)
    s.gap()

    s.callout('CÓMO LEER ESTA HOJA', T['como_leer'], accent=GOLD, tint=GOLD_T, h=60.45)
    s.gap()

    hdr = s.r
    s.head([('B', None, 'NIT', 'left'), ('C', None, 'Nombre / razón social', 'left'),
            ('D', None, 'Detalle reportado', 'left'), ('E', None, 'Valor', 'right'),
            ('F', None, 'Clasificación asignada', 'left'), ('G', None, 'Depuración', 'center')])
    for i, (nit, nombre, det, val, clas, dep) in enumerate(C['detalle_exogena']):
        lineas = max(_lineas(nombre, 32), _lineas(det, 52), _lineas(clas, 30))
        h = min(44.0, max(17.85, lineas * 12.6 + 4))
        r = s.datarow(zebra=bool(i % 2), h=h)
        s.put(r, 'B', int(nit), F(8.2, color=TEXT2), AL('left', 'top', False, 1), '0')
        s.put(r, 'C', nombre, F(8.2, color=TEXT2), AL('left', 'top', True, 1))
        s.put(r, 'D', det, F(8.2, color=TEXT2), AL('left', 'top', True, 1))
        s.put(r, 'E', val, F(8.6, True, color=TEXT), AL('right', 'top', False, 1), NUM)
        s.put(r, 'F', clas, F(8.2, color=TEXT2), AL('left', 'top', True, 1))
        if dep:
            s.put(r, 'G', dep, F(7.3, True, color=MUTED), AL('center', 'top'))
    last = s.r - 1
    ws.auto_filter.ref = f'B{hdr}:G{last}'

    ws.freeze_panes = f'A{hdr + 1}'
    return ws
