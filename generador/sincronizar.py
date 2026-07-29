# -*- coding: utf-8 -*-
r"""Sube a Supabase los casos que hoy viven en clientes\ — el puente entre el
modo escritorio y la nube.

    python sincronizar.py              sube todos los casos
    python sincronizar.py --ver        no escribe: solo dice qué haría
    python sincronizar.py --caso "Munera De Marin Beatriz"

Es idempotente: cada caso se identifica por (contribuyente, año gravable), así
que correrlo dos veces actualiza en vez de duplicar. El estado de revisión que
ya tenga el caso en la nube no se pisa.
"""
import argparse
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import casos as casos_mod
import db


def sincronizar(filtro=None, ver=False, log=print):
    lista = casos_mod.listar()
    if filtro:
        f = filtro.lower()
        lista = [c for c in lista if f in c['persona'].lower() or f in c['ano'].lower()]
    if not lista:
        log('No hay casos en clientes\\ que sincronizar.')
        return 0, 0

    if ver:
        for c in lista:
            estado = c.get('error') and 'ERROR' or c['calc']['semaforo']
            log(f"  {c['persona']} · {c['ano']} · {estado} · "
                f"libro: {c['libro'] or '—'}")
        log(f'\n{len(lista)} caso(s) se subirían. Nada se escribió (--ver).')
        return 0, 0

    s = db.Supabase.desde_env()
    creados = s.asegurar_buckets()
    if creados:
        log('Buckets creados: ' + ', '.join(creados))

    ok = fallos = 0
    for c in lista:
        etiqueta = f"{c['persona']} · {c['ano']}"
        if 'error' in c:
            log(f'  ✗ {etiqueta} — no se pudo calcular: {c["error"][:120]}')
            fallos += 1
            continue
        try:
            decl = s.guardar_caso(c['calc'],
                                  libro=casos_mod.ruta_libro(c),
                                  exogena=casos_mod.ruta_exogena(c))
            log(f'  ✓ {etiqueta} — {c["calc"]["semaforo"]} '
                f'· {len(c["C"].get("alertas", []))} alertas · id {decl["id"][:8]}')
            ok += 1
        except db.ErrorSupabase as ex:
            log(f'  ✗ {etiqueta} — {ex}')
            fallos += 1
    log(f'\n{ok} caso(s) sincronizado(s), {fallos} con problemas.')
    return ok, fallos


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Sube los casos locales a Supabase.')
    p.add_argument('--caso', help='filtra por nombre de contribuyente o año')
    p.add_argument('--ver', action='store_true', help='no escribe nada; solo lista')
    args = p.parse_args()
    try:
        _, fallos = sincronizar(args.caso, args.ver)
    except db.ErrorSupabase as ex:
        print('✗ ' + str(ex))
        sys.exit(1)
    sys.exit(1 if fallos else 0)
