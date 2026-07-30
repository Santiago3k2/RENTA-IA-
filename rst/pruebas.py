# -*- coding: utf-8 -*-
"""Regresión del motor del SIMPLE contra el caso modelo hecho a mano.

Debe decir «TODAS LAS PRUEBAS PASAN» después de cualquier cambio al lector, a
los parámetros o a la liquidación.

    python -m rst.pruebas
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))

from rst import calculos
from rst import generar
from rst import lector
from rst import libro
from rst import parametros as P

# El caso de referencia —archivo fuente y cifras verificadas a mano— vive en
# `rst\caso_referencia.py`, que NO se versiona: son datos de un contribuyente
# real, sujetos a la reserva del art. 583 E.T. Sin ese archivo la suite corre
# igual y solo omite el bloque del caso real.
try:
    from rst import caso_referencia as CASO
except ImportError:
    CASO = None

fallos = []


def check(nombre, obtenido, esperado, tol=0.02):
    if abs(obtenido - esperado) > tol:
        fallos.append('%s: esperado %s, obtenido %s' % (nombre, esperado, obtenido))


def probar_parametros():
    check('UVT 2026', P.uvt(2026), 52374, 0)
    check('tarifa grupo 3 tramo 1', P.tarifa(3, 884.6), 0.059, 0)
    check('tarifa grupo 3 tramo 2', P.tarifa(3, 1500), 0.073, 0)
    check('tarifa grupo 3 tramo 4', P.tarifa(3, 20000), 0.145, 0)
    check('tarifa grupo 2 tramo 1', P.tarifa(2, 884.6), 0.016, 0)
    if P.nombre_bimestre(3) != 'Mayo y Junio':
        fallos.append('nombre del bimestre 3 incorrecto')
    if P.meses_bimestre(6) != (11, 12):
        fallos.append('meses del bimestre 6 incorrectos')
    try:
        P.uvt(2099)
        fallos.append('uvt() debería fallar con un año sin resolución cargada')
    except KeyError:
        pass
    try:
        P.tarifa(9, 100)
        fallos.append('tarifa() debería fallar con un grupo inexistente')
    except KeyError:
        pass


def probar_caso_real():
    """El caso de referencia, si está disponible en este equipo."""
    if CASO is None:
        print('  (sin rst/caso_referencia.py: se omite el caso real)')
        return None
    if not os.path.exists(CASO.CONSOLIDADO):
        fallos.append('No se encuentra el consolidado de referencia: %s' % CASO.CONSOLIDADO)
        return None
    ficha = generar.cargar_ficha(CASO.FICHA)
    fuente = lector.leer(CASO.CONSOLIDADO)

    for clave, valor in CASO.CONTEOS.items():
        check(clave, len(fuente[clave]), valor, 0)

    liq = calculos.liquidar(ficha, fuente)
    for clave, valor in CASO.ESPERADO.items():
        check(clave, liq[clave], valor, 0.02 if clave != 'base_uvt' else 0.01)

    for v in liq['validaciones']:
        if not v['ok']:
            fallos.append('validación en rojo que debería cuadrar: %s' % v['nombre'])
    if len(liq['validaciones']) < 10:
        fallos.append('se esperaban al menos 10 validaciones, hay %d' % len(liq['validaciones']))
    if liq['semaforo'] != 'AMARILLO':
        fallos.append('semáforo esperado AMARILLO (hay alertas ALTA), obtenido %s'
                      % liq['semaforo'])
    temas = {a['tema'] for a in liq['alertas']}
    for esperado in ('Grupo de actividad', 'Diferencias en certificados de ReteIVA',
                     'Completitud de las planillas de pensión', 'DV y Dirección Seccional'):
        if esperado not in temas:
            fallos.append('falta la alerta «%s»' % esperado)
    return liq, ficha


def probar_libro(liq, ficha):
    wb = libro.construir(liq, ficha)
    if wb.sheetnames != libro.ORDEN:
        fallos.append('el orden de las hojas cambió: %s' % wb.sheetnames)
    datos = libro.a_bytes(wb)
    if len(datos) < 10000:
        fallos.append('el libro generado pesa %d bytes: parece vacío' % len(datos))
    ws = wb['2.INGRESOS']
    # el detalle debe traer una fila por factura más encabezado y totales
    if sum(1 for f in ws.iter_rows() if f[0].value == 'TOTALES') != 1:
        fallos.append('la hoja 2 no tiene exactamente una fila de TOTALES')


def probar_semaforo_rojo():
    """Si las razones no cuadran, el semáforo tiene que ponerse en ROJO."""
    liq = {'ingresos_gravados': 100, 'iva_generado': 5, 'reteiva': 0.75,
           'reteiva_certificados': 0.75, 'facturas': [], 'ingresos_no_gravados': 0,
           'iva_descontable': 0, 'validaciones': [], 'alertas': []}
    liq['validaciones'] = calculos.validar(liq, {}, {'reteiva': [], 'totales_declarados': {}})
    if calculos.semaforo(liq) != 'ROJO':
        fallos.append('una razón IVA del 5%% debería dar ROJO, dio %s'
                      % calculos.semaforo(liq))


def main():
    probar_parametros()
    resultado = probar_caso_real()
    if resultado:
        probar_libro(*resultado)
    probar_semaforo_rojo()

    if fallos:
        print('FALLARON %d COMPROBACIONES:' % len(fallos))
        for f in fallos:
            print('  · %s' % f)
        return 1
    print('TODAS LAS PRUEBAS PASAN')
    return 0


if __name__ == '__main__':
    sys.exit(main())
