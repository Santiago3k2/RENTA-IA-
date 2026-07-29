# -*- coding: utf-8 -*-
r"""Descubrimiento de casos en disco: clientes\<Contribuyente>\AG<año>\datos.py

Es la fuente de verdad local (modo escritorio). La web y el sincronizador a
Supabase parten de aquí, para que ambos vean exactamente los mismos casos.
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(BASE)
sys.path.insert(0, BASE)

import calculos


def listar(raiz=RAIZ):
    """Lista plana de casos; cada uno es un año gravable de un contribuyente.

    Un caso que no se puede calcular no se descarta: vuelve con 'error' para
    que la bandeja lo muestre en vez de esconderlo.
    """
    out = []
    cdir = os.path.join(raiz, 'clientes')
    if not os.path.isdir(cdir):
        return out
    for persona in sorted(os.listdir(cdir)):
        pdir = os.path.join(cdir, persona)
        if not os.path.isdir(pdir):
            continue
        for ano in sorted(os.listdir(pdir), reverse=True):
            adir = os.path.join(pdir, ano)
            dpath = os.path.join(adir, 'datos.py')
            if not os.path.isfile(dpath):
                continue
            libro = exogena = None
            for f in sorted(os.listdir(adir)):
                if not f.lower().endswith('.xlsx'):
                    continue
                if f.startswith('Declaracion'):
                    libro = f
                elif 'exogena' in f.lower() or 'reporte' in f.lower():
                    exogena = f
            reg = {'persona': persona, 'ano': ano, 'dir': adir,
                   'libro': libro, 'exogena': exogena}
            try:
                reg['calc'] = calculos.calcular(dpath)
                reg['C'] = reg['calc']['cliente']
            except Exception as ex:
                reg['error'] = str(ex)
            out.append(reg)
    return out


def ruta_libro(caso):
    return os.path.join(caso['dir'], caso['libro']) if caso.get('libro') else None


def ruta_exogena(caso):
    return os.path.join(caso['dir'], caso['exogena']) if caso.get('exogena') else None
