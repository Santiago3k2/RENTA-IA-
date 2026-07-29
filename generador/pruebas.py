# -*- coding: utf-8 -*-
"""Suite de pruebas del motor.  Uso:  python pruebas.py

Corre todos los reportes de exógena conocidos, verifica que la clasificación
reconstruya los topes de la DIAN y compara contra los patrones congelados en
..\\referencia\\. Cualquier cambio al clasificador debe pasar esta suite.
"""
import importlib.util
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(BASE)
sys.path.insert(0, BASE)

import clasificador
import parser_exogena

EJ = r'C:\Users\PERSONAL\Documents\EJERCICIO 3'
CASOS = [
    ('Sepúlveda AG2025', os.path.join(EJ, 'reporteExogena2025 (1).xlsx'),
     'Sepulveda Orejarena AG2025 - manual.py'),
    ('Paula AG2024', os.path.join(EJ, r'PAULAANDREASUAREZMOYA\2024\reporteExogena2024-27082025.xlsx'),
     'Suarez Moya Paula Andrea AG2024 - auto.py'),
    ('Paula AG2023', os.path.join(EJ, r'PAULAANDREASUAREZMOYA\2023\reporteExogena2023.xlsx'),
     'Suarez Moya Paula Andrea AG2023 - auto.py'),
    ('Munera AG2025', os.path.join(RAIZ, r'subidas\reporteExogena2025.xlsx'),
     'Munera De Marin Beatriz AG2025 - auto.py'),
]

CAMPOS = ['cuentas', 'inversiones', 'cuentas_cobrar', 'cesantias', 'vehiculos',
          'pasivos', 'rentas_trabajo', 'incrngo_trabajo', 'rentas_capital',
          'rentas_no_laborales', 'consumos_tarjeta']


def _cargar(ruta):
    spec = importlib.util.spec_from_file_location('patron', ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.CLIENTE


def main():
    fallos = 0
    for nombre, xlsx, patron in CASOS:
        print(f'\n{"=" * 68}\n{nombre}')
        if not os.path.isfile(xlsx):
            print('  OMITIDO — no se encuentra el reporte'); continue
        c = clasificador.procesar(parser_exogena.leer(xlsx))

        for k, v in c['difs'].items():
            tol = clasificador.tolerancia(c['topes'][k])
            ok = abs(v) <= tol
            fallos += 0 if ok else 1
            print(f'  tope {k:12} dif {v:>+14,.0f}   {"OK" if ok else "FALLA"}'.replace(',', '.'))

        p = os.path.join(RAIZ, 'referencia', patron)
        if os.path.isfile(p):
            M = _cargar(p)
            difs = []
            for campo in CAMPOS:
                a = sum((x[-1] or 0) for x in c[campo])
                b = sum((x[-1] or 0) for x in M[campo])
                if a != b:
                    difs.append(f'{campo} {a:,} vs {b:,}'.replace(',', '.'))
            a_inm = sum(int(v * pc) for _, pc, v in c['inmuebles'])
            b_inm = sum(int(v * pc) for _, pc, v in M['inmuebles'])
            if a_inm != b_inm:
                difs.append(f'inmuebles {a_inm:,} vs {b_inm:,}'.replace(',', '.'))
            a_cdt = sum(int(round(v * pc)) for _, _, pc, v, _ in c['cdt'])
            b_cdt = sum(int(round(v * pc)) for _, _, pc, v, _ in M['cdt'])
            if a_cdt != b_cdt:
                difs.append(f'cdt {a_cdt:,} vs {b_cdt:,}'.replace(',', '.'))
            a_ret = sum(v for _, f in c['retenciones'] for _, _, v in f)
            b_ret = sum(v for _, f in M['retenciones'] for _, _, v in f)
            if a_ret != b_ret:
                difs.append(f'retenciones {a_ret:,} vs {b_ret:,}'.replace(',', '.'))
            fallos += len(difs)
            print(f'  patrón {patron[:44]:44} {"OK" if not difs else "FALLA"}')
            for d in difs:
                print(f'      ← {d}')
        sin = [x for x in c['detalle_exogena'] if x[4] == 'SIN CLASIFICAR']
        if sin:
            fallos += 1
            print(f'  {len(sin)} registro(s) SIN CLASIFICAR   FALLA')
            for x in sin[:5]:
                print(f'      ← {x[1]}: {x[2][:60]}')

    print(f'\n{"=" * 68}')
    print('RESULTADO:', 'TODAS LAS PRUEBAS PASAN' if not fallos else f'{fallos} FALLA(S)')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(main())
