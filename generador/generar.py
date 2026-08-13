# -*- coding: utf-8 -*-
"""Genera el libro completo de declaración de renta desde un archivo de datos.

Uso:
    python generar.py                                   # caso modelo (datos.py)
    python generar.py --datos ..\\clientes\\X\\datos.py
    python generar.py --datos ... --salida ruta\\libro.xlsx
"""
import argparse
import importlib.util
import io
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import openpyxl
from openpyxl.workbook.defined_name import DefinedName

import build_lib
import sheet_patrimonio, sheet_ingresos, sheet_retenciones, sheet_consignaciones
import sheet_liquidacion, sheet_anticipo, sheet_alertas, sheet_detalle, sheet_resumen

ORDER = ['1. Resumen', '2. Patrimonio', '3. Ingresos', '4. Retenciones',
         '5. Anticipo', '6. Liquidación', '7. Alertas', '8. Consignaciones',
         '9. Detalle exógena']


def cargar_datos(ruta):
    spec = importlib.util.spec_from_file_location('datos_cliente', ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.CLIENTE, mod.TEXTOS


def construir(C, T):
    """Arma el libro de 9 hojas en memoria y devuelve (workbook, anclas).

    No toca el disco: así el mismo motor sirve para el escritorio y para las
    funciones sin estado de Vercel.
    """
    build_lib.set_identidad(C['nombre'], C['identificacion'], C['ano_gravable'])

    wb = openpyxl.Workbook()
    wb.active.title = '1. Resumen'      # G9 (UVT) vive aquí; se puebla al final

    A = {}
    sheet_patrimonio.build(wb, A, C, T)
    sheet_ingresos.build(wb, A, C, T)
    sheet_retenciones.build(wb, A, C, T)
    sheet_consignaciones.build(wb, A, C, T)
    sheet_liquidacion.build(wb, A, C, T)      # necesita base_fe de consignaciones
    sheet_anticipo.build(wb, A, C, T)         # necesita liquidación y retenciones
    sheet_alertas.build(wb, A, C, T)
    sheet_detalle.build(wb, A, C, T)
    sheet_resumen.populate(wb, A, C, T)       # necesita todas las anclas

    wb._sheets = [wb[t] for t in ORDER]
    for ws in wb.worksheets:
        ws.sheet_view.tabSelected = False
    wb['1. Resumen'].sheet_view.tabSelected = True
    wb.active = 0
    wb.calculation.fullCalcOnLoad = True

    # nombres definidos: verificación independiente de las posiciones de fila
    nombres = {
        'PATRIMONIO_BRUTO':   ('2. Patrimonio', 'H', A['pat_bruto']),
        'DEUDAS':             ('2. Patrimonio', 'H', A['pas_tot']),
        'PATRIMONIO_LIQUIDO': ('2. Patrimonio', 'H', A['pat_liq']),
        'DIFERENCIA_PATRIM':  ('2. Patrimonio', 'H', A['pat_dif']),
        'INGRESOS_BRUTOS':    ('3. Ingresos', 'G', A['ing_total']),
        # Los tres INCRNGO por separado: la conciliación patrimonial de la hoja 2
        # los suma, y esa hoja se arma ANTES que la 3, así que no puede citar sus
        # filas — solo el nombre, que Excel resuelve al abrir.
        'INCRNGO_TRABAJO':    ('3. Ingresos', 'G', A['r33']),
        'INCRNGO_CAPITAL':    ('3. Ingresos', 'G', A['incr58']),
        'INCRNGO_NO_LABORAL': ('3. Ingresos', 'G', A['incr74']),
        'RETENCIONES':        ('4. Retenciones', 'D', A['ret_total']),
        'RENTA_LIQ_GRAVABLE': ('6. Liquidación', 'D', A['rlg']),
        'IMPUESTO_A_CARGO':   ('6. Liquidación', 'D', A['imp_cargo']),
        # Los cuatro escalones que van entre la renta líquida y el impuesto
        # neto. El consolidado de la hoja 3 los cita por nombre porque esa hoja
        # se arma antes que la 6 — y así las dos no pueden decir cifras
        # distintas: son literalmente la misma celda.
        'EXENTAS_ACEPTADAS':  ('6. Liquidación', 'D', A['exentas_aceptadas']),
        'DEDUC_SIN_LIMITE':   ('6. Liquidación', 'D', A['ded_sin_limite']),
        'IMPUESTO_RENTA':     ('6. Liquidación', 'D', A['imp_241']),
        'DESCUENTOS_TRIB':    ('6. Liquidación', 'D', A['descuentos']),
        'IMPUESTO_NETO':      ('6. Liquidación', 'D', A['imp_neto']),
        'ANTICIPO':           ('5. Anticipo', 'I', A['ant_row']),
        'SALDO_A_PAGAR':      ('5. Anticipo', 'I', A['saldo_row']),
        'TOPE4_MOVIMIENTOS':  ('8. Consignaciones', 'G', A['mov_tope4']),
        'CONSUMOS_TARJETA':   ('8. Consignaciones', 'E', A['consumos']),
        'COMPRAS_FE':         ('8. Consignaciones', 'E', A['compras']),
    }
    for nom, (hoja, col, fila) in nombres.items():
        wb.defined_names[nom] = DefinedName(nom, attr_text=f"'{hoja}'!${col}${fila}")

    return wb, A


def nombre_libro(C):
    return f"Declaracion Renta AG{C['ano_gravable']} - {C['nombre_archivo']}.xlsx"


def a_bytes(C, T):
    """El libro como bytes, sin archivo intermedio (para servir o subir)."""
    wb, _ = construir(C, T)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def main():
    ap = argparse.ArgumentParser(description='Generador del libro de declaración de renta')
    ap.add_argument('--datos', default=os.path.join(BASE, 'datos.py'))
    ap.add_argument('--salida', default=None)
    args = ap.parse_args()

    C, T = cargar_datos(args.datos)
    wb, A = construir(C, T)

    if args.salida:
        out = args.salida
    else:
        carpeta = os.path.join(os.path.dirname(BASE), 'clientes',
                               C['nombre_archivo'], f"AG{C['ano_gravable']}")
        os.makedirs(carpeta, exist_ok=True)
        out = os.path.join(carpeta, nombre_libro(C))
    wb.save(out)
    print('OK ->', out)
    print('anclas:', dict(sorted(A.items())))


if __name__ == '__main__':
    main()
