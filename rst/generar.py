# -*- coding: utf-8 -*-
r"""Motor del Régimen Simple: consolidado de la DIAN + ficha → libro de 9 hojas.

Uso:
    python -m rst.generar --consolidado "CONSOLIDADO ...xlsx" --ficha rst\fichas\mi-cliente.py
    python -m rst.generar --consolidado ... --ficha ... --bimestre 4 --salida libro.xlsx

Se ejecuta como módulo (`-m`) desde la raíz del proyecto, no como archivo
suelto: `rst` es un paquete para que sus módulos (`calculos`, `lector`, `db`)
no choquen con los del motor de renta, que se llaman igual y se cargan en el
mismo proceso cuando la web sirve los dos apartados.
"""
import argparse
import importlib.util
import os
import sys

from . import calculos
from . import lector
from . import libro


def cargar_ficha(ruta):
    spec = importlib.util.spec_from_file_location('ficha_cliente', ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(mod.FICHA)


def procesar(ruta_consolidado, ficha):
    """Consolidado + ficha → (liquidación, workbook). Sin tocar disco."""
    fuente = lector.leer(ruta_consolidado)
    liq = calculos.liquidar(ficha, fuente)
    return liq, libro.construir(liq, ficha)


def nombre_salida(ficha, liq):
    return 'DECLARACION BIMESTRAL SIMPLE - %s - Bim%d %d.xlsx' % (
        ficha['nombre'].split()[0].upper(), liq['bimestre'], liq['ano'])


def main(argv=None):
    ap = argparse.ArgumentParser(description='Genera el libro del anticipo bimestral '
                                             'del Régimen Simple (Formulario 2593).')
    ap.add_argument('--consolidado', required=True,
                    help='Exportación de documentos electrónicos de la DIAN (.xlsx)')
    ap.add_argument('--ficha', required=True, help='Ficha del contribuyente (.py)')
    ap.add_argument('--bimestre', type=int, help='Sobrescribe el bimestre de la ficha')
    ap.add_argument('--ano', type=int, help='Sobrescribe el año gravable de la ficha')
    ap.add_argument('--salida', help='Ruta del libro a escribir')
    a = ap.parse_args(argv)

    ficha = cargar_ficha(a.ficha)
    if a.bimestre:
        ficha['bimestre'] = a.bimestre
    if a.ano:
        ficha['ano'] = a.ano

    liq, wb = procesar(a.consolidado, ficha)
    salida = a.salida or os.path.join(os.path.dirname(os.path.abspath(a.ficha)),
                                      nombre_salida(ficha, liq))
    wb.save(salida)

    pesos = libro._pesos
    print('%s — NIT %s' % (ficha['nombre'], ficha['nit']))
    print('Bimestre %d (%s) de %d · grupo %d · UVT $%s'
          % (liq['bimestre'], liq['nombre_bimestre'], liq['ano'], liq['grupo'],
             pesos(liq['uvt'])))
    print('-' * 64)
    print('  Base del anticipo        $%14s  (%.2f UVT)' % (pesos(liq['base']), liq['base_uvt']))
    print('  Tarifa                    %14s' % ('%.1f %%' % (liq['tarifa'] * 100)))
    print('  Anticipo consolidado     $%14s' % pesos(liq['anticipo_consolidado']))
    print('  (−) ICA %-16s $%14s' % (liq['filas_ica'][0]['nombre'], pesos(liq['ica'])))
    print('  (−) Pensión patronal     $%14s' % pesos(liq['descuento_pension']))
    print('  ANTICIPO NETO            $%14s' % pesos(liq['anticipo_neto']))
    print('  IVA a pagar              $%14s' % pesos(liq['iva_pagar']))
    print('  TOTAL (aprox. a mil)     $%14s' % pesos(liq['total_mil']))
    print('-' * 64)
    malas = [v for v in liq['validaciones'] if not v['ok']]
    print('Semáforo: %s · %d validaciones (%d por revisar) · %d alertas (%d ALTA)'
          % (liq['semaforo'], len(liq['validaciones']), len(malas), len(liq['alertas']),
             sum(1 for x in liq['alertas'] if x['prioridad'] == 'ALTA')))
    for v in malas:
        print('  REVISAR: %s → %s' % (v['nombre'], v['nota']))
    print('Libro: %s' % salida)
    return 0


if __name__ == '__main__':
    sys.exit(main())
