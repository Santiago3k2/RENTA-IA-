# -*- coding: utf-8 -*-
r"""Los casos, leídos desde Supabase, con la misma forma que los de disco.

La web local descubre los casos en `clientes\`; la web publicada los lee de
aquí. Ambas pintan el mismo HTML porque las dos entregan la misma estructura:

    {'persona', 'ano', 'ref', 'calc', 'C', 'libro', 'estado', 'creada_por'}

Las cifras NO se leen de las columnas de la tabla: se recalculan con
`calculos.calcular_dict` sobre el JSON del caso. Así la nube nunca se
desincroniza del motor — hay una sola fórmula, no dos.
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import calculos
import db

CAMPOS = ('id,ano_gravable,estado,semaforo,creada_por,libro_path,exogena_path,'
          'datos,creado_en,contribuyentes(nombre_titulo,identificacion)')


def _armar(fila):
    C = fila.get('datos') or {}
    persona = (fila.get('contribuyentes') or {}).get('nombre_titulo') \
        or C.get('nombre_titulo') or 'Sin nombre'
    caso = {
        'persona': persona,
        'ano': 'AG' + str(fila.get('ano_gravable') or ''),
        'ref': fila['id'],
        'id': fila['id'],
        'estado': fila.get('estado') or 'borrador',
        'creada_por': fila.get('creada_por') or 'contador',
        'libro_path': fila.get('libro_path'),
        'exogena_path': fila.get('exogena_path'),
        'libro': os.path.basename(fila['libro_path']) if fila.get('libro_path') else None,
    }
    try:
        caso['calc'] = calculos.calcular_dict(C)
        caso['C'] = C
    except Exception as ex:
        caso['error'] = f'El caso guardado no se pudo recalcular: {ex}'
    return caso


def listar(cliente=None, solo_de=None):
    """Casos de la nube, del año más reciente al más antiguo.

    `solo_de` restringe a los que cargó ese usuario: con datos tributarios de
    terceros, un usuario de prueba no tiene por qué ver la cartera completa.
    """
    s = cliente or db.Supabase.desde_env()
    filtros = {'select': CAMPOS, 'order': 'ano_gravable.desc'}
    if solo_de:
        filtros['creada_por'] = 'eq.' + solo_de
    return [_armar(f) for f in s.seleccionar('declaraciones', **filtros)]


def buscar(ref, cliente=None, solo_de=None):
    """Un caso por su id. Devuelve None si no existe o no es de ese usuario."""
    s = cliente or db.Supabase.desde_env()
    filtros = {'select': CAMPOS, 'id': 'eq.' + str(ref)}
    if solo_de:
        filtros['creada_por'] = 'eq.' + solo_de
    filas = s.seleccionar('declaraciones', **filtros)
    return _armar(filas[0]) if filas else None


def cuantas_lleva(usuario, cliente=None):
    """Declaraciones que ese usuario ha cargado — el cupo se mide con esto."""
    s = cliente or db.Supabase.desde_env()
    return len(s.seleccionar('declaraciones', select='id',
                             creada_por='eq.' + usuario))
