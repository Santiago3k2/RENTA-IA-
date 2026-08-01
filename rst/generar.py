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
from . import parametros as P


def cargar_ficha(ruta):
    spec = importlib.util.spec_from_file_location('ficha_cliente', ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(mod.FICHA)


def resolver_periodo(ficha, fuente):
    """Deja en la ficha el año y el bimestre que se van a liquidar.

    El período no hay que adivinarlo: las fechas del archivo ya dicen de qué
    bimestre es. Si la ficha no lo trae —que es lo normal—, se toma el período
    con más documentos y se anota en `_periodo_auto` para que el libro y la web
    puedan decir de dónde salió.

    Si la ficha SÍ lo trae y el archivo no tiene un solo documento de ese
    período teniendo documentos de otros, se aborta con un mensaje que nombra el
    correcto. Antes eso salía adelante y producía un libro entero en ceros: una
    declaración vacía que parecía válida es peor que un error.
    """
    disponibles = fuente.get('periodos') or []
    pedido = ficha.get('bimestre')
    if pedido:
        ficha['_periodo_auto'] = ''
        if disponibles and not any(p['bimestre'] == int(pedido)
                                   and p['ano'] == int(ficha['ano']) for p in disponibles):
            raise ValueError(
                'El archivo no trae ningún documento de %s de %s, que es el período que '
                'se pidió liquidar. Lo que trae es: %s. Procéselo con ese período —o deje '
                'el bimestre en «detectar del archivo»— porque así como está la '
                'declaración saldría en ceros.'
                % (P.nombre_bimestre(int(pedido)).lower(), ficha['ano'],
                   P.describir_periodos(disponibles)))
        return ficha

    if not disponibles:
        raise ValueError(
            'El archivo no trae documentos con fecha, así que no se puede deducir de qué '
            'bimestre es. Indique el bimestre a mano.')

    elegido = disponibles[0]
    ficha['ano'] = elegido['ano']
    ficha['bimestre'] = elegido['bimestre']
    ficha['_periodo_auto'] = P.describir_periodos([elegido])
    P.uvt(elegido['ano'])        # falla claro si no está cargada la UVT de ese año
    return ficha


def procesar(ruta_consolidado, ficha):
    """Consolidado + ficha → (liquidación, workbook). Sin tocar disco.

    El NIT va al lector porque es lo que separa las ventas de las compras: en
    el archivo crudo de la DIAN ambas viven en la misma hoja y lo único que las
    distingue es si el contribuyente es el emisor o el receptor.
    """
    fuente = lector.leer(ruta_consolidado, ficha.get('nit', ''))
    resolver_periodo(ficha, fuente)
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
    ap.add_argument('--bimestre', type=int,
                    help='Fuerza el bimestre. Si se omite y la ficha no lo trae, se '
                         'deduce de las fechas del archivo.')
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
    print('Bimestre %d (%s) de %d · grupo %d · UVT $%s%s'
          % (liq['bimestre'], liq['nombre_bimestre'], liq['ano'], liq['grupo'],
             pesos(liq['uvt']),
             '  [detectado del archivo]' if ficha.get('_periodo_auto') else ''))
    otros = [p for p in liq['periodos_del_archivo']
             if (p['ano'], p['bimestre']) != (liq['ano'], liq['bimestre'])]
    if otros:
        print('AVISO: el archivo trae además %s — se procesan aparte.'
              % P.describir_periodos(otros))
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
