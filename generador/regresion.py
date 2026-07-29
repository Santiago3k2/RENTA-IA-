# -*- coding: utf-8 -*-
"""Regresión: compara la clasificación AUTOMÁTICA contra una hecha a mano.

    python regresion.py <reporteExogena.xlsx> <datos_manual.py>

Cifra por cifra. Es la prueba que debe pasar el clasificador cada vez que se
le añade una regla, para asegurar que no rompió los casos ya validados.
"""
import importlib.util
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import calculos
import clasificador
import parser_exogena


def _pesos(v):
    s = '-' if v < 0 else ''
    return f'{s}{abs(int(round(v))):,}'.replace(',', '.')


def main():
    xlsx, manual = sys.argv[1], sys.argv[2]
    auto = clasificador.procesar(parser_exogena.leer(xlsx))

    spec = importlib.util.spec_from_file_location('man', manual)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    M = m.CLIENTE

    def suma(lista, i=-1):
        return sum(x[i] or 0 for x in lista)

    pruebas = [
        ('Cuentas bancarias', suma(auto['cuentas']), suma(M['cuentas'])),
        ('CDT', sum(int(round(v * p)) for _, _, p, v, _ in auto['cdt']),
         sum(int(round(v * p)) for _, _, p, v, _ in M['cdt'])),
        ('Inversiones', suma(auto['inversiones']), suma(M['inversiones'])),
        ('Cuentas por cobrar', suma(auto['cuentas_cobrar']), suma(M['cuentas_cobrar'])),
        ('Cesantías', suma(auto['cesantias']), suma(M['cesantias'])),
        ('Inmuebles', sum(int(v * p) for _, p, v in auto['inmuebles']),
         sum(int(v * p) for _, p, v in M['inmuebles'])),
        ('Vehículos', suma(auto['vehiculos']), suma(M['vehiculos'])),
        ('Pasivos', suma(auto['pasivos']), suma(M['pasivos'])),
        ('R32 rentas de trabajo', suma(auto['rentas_trabajo']), suma(M['rentas_trabajo'])),
        ('R33 INCRNGO', suma(auto['incrngo_trabajo']), suma(M['incrngo_trabajo'])),
        ('R58 rentas de capital', suma(auto['rentas_capital']), suma(M['rentas_capital'])),
        ('R74 rentas no laborales', suma(auto['rentas_no_laborales']), suma(M['rentas_no_laborales'])),
        ('R132 retenciones',
         sum(v for _, f in auto['retenciones'] for _, _, v in f),
         sum(v for _, f in M['retenciones'] for _, _, v in f)),
        ('Tope 4 movimientos', sum(x[3] for x in auto['movimientos']),
         sum(x[3] for x in M['movimientos'])),
        ('Tope 3 consumos', suma(auto['consumos_tarjeta']), suma(M['consumos_tarjeta'])),
        ('Tope 5 compras', auto['compras_fe'], M['compras_fe']),
        ('Base factura electrónica', auto['base_fe'], M['base_fe']),
        ('Base excluida del 25%', auto['base_25_excluir'], M.get('base_25_excluir', 0)),
        ('Patrimonio año anterior', auto['pat_anterior'], M['patrimonio_bruto_anterior']),
        ('Saldo a favor anterior', auto['saldo_favor'], M['saldo_favor_anterior']),
        ('UVT', auto['uvt'], M['uvt']),
        ('Registros', auto['n_registros'], M['registros']),
    ]

    print(f'REGRESIÓN  ·  {os.path.basename(xlsx)}')
    print(f'{"Concepto":<28}{"AUTOMÁTICO":>18}{"MANUAL":>18}   ')
    print('-' * 72)
    fallos = 0
    for nombre, a, b in pruebas:
        ok = (a == b)
        if not ok:
            fallos += 1
        print(f'{nombre:<28}{_pesos(a):>18}{_pesos(b):>18}   {"OK" if ok else "← DIFIERE"}')
    print('-' * 72)
    print(f'{"":<28}{"":>18}{"":>18}   {fallos} diferencia(s)')

    print('\nTopes DIAN:')
    for k, v in auto['difs'].items():
        print(f'  {k:12} dif {v:+,.0f}'.replace(',', '.'))
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(main())
