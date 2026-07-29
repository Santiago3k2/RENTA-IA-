# -*- coding: utf-8 -*-
"""Validador: replica en Python puro las cifras clave del libro y compara
contra los topes precalculados de la DIAN. Es el semáforo de la bandeja:

  VERDE    — topes reconstruidos exactos (± $10) y sin alertas ALTA
  AMARILLO — topes cuadran pero hay alertas ALTA por resolver
  ROJO     — los topes no cuadran: clasificación incompleta o errada
"""
import importlib.util
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clasificador


def _load(path):
    spec = importlib.util.spec_from_file_location('datos_calc', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.CLIENTE, mod.TEXTOS


def rnd(x):
    """ROUND de Excel: mitades lejos de cero."""
    s = 1 if x >= 0 else -1
    return s * math.floor(abs(x) + 0.5 + 1e-9)


def rnd1000(x):
    return rnd(x / 1000.0) * 1000


def impuesto_241(base_uvt, uvt):
    b = base_uvt
    if b <= 1090:
        imp = 0
    elif b <= 1700:
        imp = (b - 1090) * .19
    elif b <= 4100:
        imp = (b - 1700) * .28 + 116
    elif b <= 8670:
        imp = (b - 4100) * .33 + 788
    elif b <= 18970:
        imp = (b - 8670) * .35 + 2296
    elif b <= 31000:
        imp = (b - 18970) * .37 + 5901
    else:
        imp = (b - 31000) * .39 + 10352
    return rnd1000(imp * uvt)


def calcular(path):
    """Cifras clave de un caso guardado en disco (clientes\\…\\datos.py)."""
    C, T = _load(path)
    return calcular_dict(C, T)


def calcular_dict(C, T=None):
    """Igual, pero desde el diccionario del cliente ya cargado.

    Es la puerta que usa la nube: en Supabase el caso vive como JSON, no como
    archivo, y las cifras deben salir de este mismo motor y no de un cálculo
    paralelo que se pueda desincronizar.
    """
    uvt = C['uvt']

    # patrimonio
    cuentas = sum(v for _, _, v in C['cuentas'] if v)
    cdt = sum(rnd(v * p) for _, _, p, v, _ in C['cdt'])
    inv = sum(v for _, _, v in C['inversiones'])
    cxc = sum(v for _, _, v in C['cuentas_cobrar'])
    ces_f = sum(v for _, _, v in C['cesantias'])
    # el avalúo del 1476 es del predio completo: se aplica la participación
    inm = sum(int(v * p) for _, p, v in C['inmuebles'])
    veh = sum(v for _, _, v in C['vehiculos'])
    pat_bruto = cuentas + cdt + inv + cxc + ces_f + inm + veh
    deudas = sum(v for _, _, v in C['pasivos'])

    # ingresos y depuración
    r32 = sum(v for _, _, v in C['rentas_trabajo'])
    incr = sum(v for _, _, v in C['incrngo_trabajo'])
    r58 = sum(v for _, _, v in C['rentas_capital'])
    r74 = sum(v for _, _, v in C['rentas_no_laborales'])
    ing = r32 + r58 + r74
    ces_ex = sum(C['rentas_trabajo'][i][2] for i in C.get('indices_cesantias_exentas', []))
    base25 = r32 - incr - ces_ex - C.get('base_25_excluir', 0)
    ex25 = rnd(min(base25 * 0.25, 790 * uvt)) if base25 > 0 else 0
    solicitadas = ces_ex + ex25
    cupo = rnd(min(0.4 * (ing - incr), 1340 * uvt))
    aceptadas = min(solicitadas, cupo)
    ded1 = rnd(min(C['base_fe'] / 100, 240 * uvt))
    rlg = (ing - incr) - aceptadas - ded1
    base_uvt = rlg / uvt
    impuesto = impuesto_241(base_uvt, uvt)

    ret = sum(v for _, filas in C['retenciones'] for _, _, v in filas)
    pct = C.get('porcentaje_anticipo', 0.75)
    X = C.get('impuesto_neto_anterior', 0)
    anticipo = rnd1000(max(0, (impuesto + X) / 2 * pct - ret))          # método 2
    metodo1 = rnd1000(max(0, rnd(impuesto * pct) - ret))
    saldo = rnd1000(impuesto + anticipo - C.get('saldo_favor_anterior', 0)
                    - ret - C.get('anticipo_previo', 0))

    # topes
    mov = sum(v for _, _, _, v in C['movimientos'])
    consumos = sum(v for _, v in C['consumos_tarjeta'])
    compras = C['compras_fe']
    topes = C.get('topes_dian', {})
    mios = {'ingresos': ing, 'consumos': consumos,
            'movimientos': mov, 'compras': compras}
    # El tope 2 solo valida la composición del patrimonio cuando proviene de la
    # exógena, es decir cuando supera al patrimonio declarado el año anterior.
    if topes.get('patrimonio') and topes['patrimonio'] > C.get('patrimonio_bruto_anterior', 0):
        mios['patrimonio'] = pat_bruto
    difs = {k: mios[k] - topes[k] for k in mios if topes.get(k)}
    topes_ok = (all(abs(d) <= clasificador.tolerancia(topes[k]) for k, d in difs.items())
                if difs else None)

    n_altas = sum(1 for a in C['alertas'] if a[1] == 'ALTA')
    if topes_ok is False:
        semaforo = 'ROJO'
    elif n_altas:
        semaforo = 'AMARILLO'
    else:
        semaforo = 'VERDE'

    return {
        'cliente': C, 'textos': T or {},
        'pat_bruto': pat_bruto, 'deudas': deudas, 'pat_liquido': pat_bruto - deudas,
        'ingresos': ing, 'r32': r32, 'r58': r58, 'r74': r74, 'incrngo': incr,
        'exentas_aceptadas': aceptadas, 'ded_1pct': ded1, 'rlg': rlg,
        'base_uvt': base_uvt, 'impuesto': impuesto, 'retenciones': ret,
        'anticipo': anticipo, 'metodo1': metodo1, 'saldo': saldo,
        'movimientos': mov, 'consumos': consumos, 'compras': compras,
        'topes_dian': topes, 'difs_topes': difs, 'topes_ok': topes_ok,
        'n_altas': n_altas, 'semaforo': semaforo,
    }
