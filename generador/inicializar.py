# -*- coding: utf-8 -*-
r"""Deja la nube lista para el sistema de cuentas. Se corre una sola vez.

    python inicializar.py                    dice qué falta, sin escribir nada
    python inicializar.py --aplicar          crea lo que falte
    python inicializar.py --aplicar --admin-clave "una frase larga"

Qué hace:

  · Crea los buckets privados si faltan.
  · Retira la cuenta técnica «contador» si quedó de antes, y pone a nombre del
    administrador los casos que subió el equipo de escritorio. Desde que nadie
    ve lo que no cargó, un dueño inhabilitado los dejaría invisibles para todo
    el mundo — y son del dueño del sistema.
  · Crea el administrador SOLO si se le da una contraseña. Sin ella no lo
    toca, a propósito: en el sitio publicado la cuenta «admin» se crea sola en
    el primer acceso a partir de RENTA_IA_CLAVE_ADMIN, que ya está puesta en
    Vercel. Crearlo aquí con otra clave dejaría de servir la de allá.
  · Migra «pruebapiloto2026» si su contraseña sigue en el entorno.

Es idempotente: correrlo dos veces no duplica ni pisa nada.
"""
import argparse
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import config
import cuentas
import db


def _env(nombre, defecto=''):
    a = config.ajustes()
    return (os.environ.get(nombre) or a.get(nombre) or defecto).strip().lstrip('﻿').strip()


def inicializar(aplicar=False, admin_clave='', log=print):
    s = db.Supabase.desde_env()
    c = cuentas.Cuentas(s)
    pendientes = []

    def hacer(titulo, fn):
        if not aplicar:
            pendientes.append(titulo)
            log(f'  · pendiente: {titulo}')
            return None
        try:
            salida = fn()
            log(f'  ✓ {titulo}')
            return salida
        except (cuentas.ErrorCuenta, db.ErrorSupabase) as ex:
            log(f'  ✗ {titulo} — {ex}')
            pendientes.append(titulo)
            return None

    log('\nAlmacenamiento')
    existentes = {b.get('name') for b in (s._pedir('GET', '/storage/v1/bucket') or [])}
    faltan = [b for b in (db.BUCKET_LIBROS, db.BUCKET_EXOGENAS) if b not in existentes]
    if faltan:
        hacer(f'crear los buckets privados: {", ".join(faltan)}', s.asegurar_buckets)
    else:
        log('  ya están los buckets «libros» y «exogenas».')

    log('\nCasos del equipo de escritorio')
    huerfanos = s.contar('declaraciones', creada_por='eq.contador')
    tecnica = c.buscar('contador')
    if not huerfanos and not tecnica:
        log('  nada que arreglar: no quedan casos ni cuenta técnica «contador».')
    else:
        if huerfanos:
            log(f'  {huerfanos} caso(s) figuran a nombre de «contador», una cuenta')
            log('  inhabilitada. Desde que nadie ve lo que no cargó, eso los deja')
            log('  invisibles para todo el mundo.')
        hacer('pasar esos casos a «admin» y retirar la cuenta técnica',
              c.migrar_rol_contador)
        if tecnica:
            hacer('eliminar la cuenta «contador», que ya no tiene función',
                  lambda: c.eliminar(tecnica['id'], por='(arranque)'))

    log('\nAdministrador')
    clave = admin_clave or _env('RENTA_IA_CLAVE_ADMIN')
    if c.buscar('admin'):
        log('  la cuenta «admin» ya existe; no se toca.')
    elif not clave:
        log('  sin contraseña a la mano: no se crea aquí.')
        log('  En el sitio publicado se creará sola en el primer acceso, con la')
        log('  RENTA_IA_CLAVE_ADMIN que ya está configurada en Vercel.')
    else:
        hacer('crear «admin» (administrador, sin límite de cupo)',
              lambda: c.crear('admin', 'Administrador', clave, rol='admin',
                              estado='activo', cupo=None, creado_por='(arranque)',
                              reservado_ok=True, exigir_clave_fuerte=False))

    log('\nUsuario de prueba')
    clave_piloto = _env('RENTA_IA_CLAVE_PILOTO')
    if c.buscar('pruebapiloto2026'):
        log('  la cuenta «pruebapiloto2026» ya existe; no se toca.')
    elif not clave_piloto:
        log('  sin RENTA_IA_CLAVE_PILOTO en el entorno: no se migra.')
        log('  Si la quiere conservar, créela desde el panel con el cupo que decida.')
    else:
        try:
            cupo = int(_env('RENTA_IA_CUPO_PILOTO') or 5)
        except ValueError:
            cupo = 5
        hacer(f'migrar «pruebapiloto2026» (cliente, cupo {cupo})',
              lambda: c.crear('pruebapiloto2026', 'Usuario de prueba', clave_piloto,
                              rol='cliente', estado='activo', cupo=cupo,
                              creado_por='(arranque)', exigir_clave_fuerte=False,
                              notas='Migrada desde RENTA_IA_CLAVE_PILOTO.'))

    log('\nDueños de las declaraciones')
    duenos = {}
    for fila in s.seleccionar('declaraciones', select='creada_por'):
        duenos[fila['creada_por']] = duenos.get(fila['creada_por'], 0) + 1
    for nombre, n in sorted(duenos.items(), key=lambda x: -x[1]):
        existe = '✓ con cuenta' if c.buscar(nombre) else '· sin cuenta registrada'
        log(f'  {nombre:22} {n:3} caso(s)   {existe}')
    log('  Las que no tengan cuenta se siguen viendo en el panel; el sistema no')
    log('  las esconde ni las borra. Cree la cuenta si quiere que su dueño entre.')

    return pendientes


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Prepara la nube para el sistema de cuentas.')
    p.add_argument('--aplicar', action='store_true',
                   help='escribe los cambios; sin esto solo informa')
    p.add_argument('--admin-clave', default='',
                   help='contraseña del administrador, si hay que crearlo aquí')
    args = p.parse_args()

    print('═' * 66)
    print('  RENTA IA — preparación del sistema de cuentas')
    print('═' * 66)
    if not args.aplicar:
        print('\n(modo consulta: no se escribe nada; agregue --aplicar)')
    try:
        pendientes = inicializar(args.aplicar, args.admin_clave)
    except db.ErrorSupabase as ex:
        print('\n✗ ' + str(ex))
        sys.exit(1)
    print('\n' + '═' * 66)
    if args.aplicar and not pendientes:
        print('  Todo listo.')
    elif pendientes:
        print(f'  Quedan {len(pendientes)} cosa(s) por hacer.')
    print('═' * 66)
    sys.exit(0)
