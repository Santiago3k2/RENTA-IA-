# -*- coding: utf-8 -*-
"""Hoja 7 · Alertas — partidas por resolver, alimentada por datos.py."""
import math
from build_lib import *

SEV_COLOR = {'ALTA': RED, 'MEDIA': GOLD, 'VERIFICADO': GREEN,
             'NORMATIVO': BLUE, 'INFORMATIVO': GREY}


def _lineas(texto, ancho):
    return max(1, math.ceil(len(texto or '') / ancho))


def build(wb, A, C, T):
    ws = wb.create_sheet('7. Alertas')
    ws.sheet_properties.tabColor = RED[2:]
    s = Sheet(ws, 'B', 'F', RED, RED_T)
    s.widths({'A': 2.3, 'B': 6.0, 'C': 9.0, 'D': 36.0, 'E': 46.0, 'F': 44.0})
    n = len(C['alertas'])

    s.band('07  ·  CONTROL DE CALIDAD',
           'Partidas por resolver antes de presentar',
           T['sub_alertas'], h_desc=22.8)
    s.gap()

    s.head([('B', None, 'Cód.', 'center'), ('C', None, 'Severidad', 'center'),
            ('D', None, 'Hallazgo', 'left'), ('E', None, 'Detalle', 'left'),
            ('F', None, 'Acción requerida', 'left')])
    for cl in ('B', 'C'):   # columnas angostas: sin ajuste de línea
        ws[f'{cl}{s.r - 1}'].alignment = AL('center', 'center', False)
        ws[f'{cl}{s.r - 1}'].font = F(7.2, True, color=WHITE)
    for i, (cod, sev, hallazgo, detalle, accion) in enumerate(C['alertas']):
        lineas = max(_lineas(hallazgo, 42), _lineas(detalle, 60), _lineas(accion, 57))
        h = min(72.0, max(29.0, lineas * 11.7 + 6))
        r = s.datarow(h=h)
        color = SEV_COLOR.get(sev, GREY)
        s.put(r, 'B', cod, F(9.0, True, color=RED), AL('center', 'center'))
        chip = ws.cell(row=r, column=3)
        chip.value = sev
        chip.fill = FILL(color)
        chip.font = F(7.2, True, color=WHITE)
        chip.alignment = AL('center', 'center', True)
        s.put(r, 'D', hallazgo, F(9.2, True, color=TEXT), AL('left', 'top', True, 1))
        s.put(r, 'E', detalle, F(8.4, color=TEXT2), AL('left', 'top', True, 1))
        s.put(r, 'F', accion, F(8.4, color=TEXT2), AL('left', 'top', True, 1))
    s.gap()

    if T.get('callout_prioridad'):
        titulo, cuerpo = T['callout_prioridad']
        s.callout(titulo, cuerpo, h=35.25)

    ws.freeze_panes = 'A6'
    return ws
