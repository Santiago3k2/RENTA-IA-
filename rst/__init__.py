# -*- coding: utf-8 -*-
r"""Módulo RST — Régimen Simple de Tributación (Formulario 2593).

Es un paquete a propósito: sus módulos se llaman igual que los del motor de
renta (`calculos`, `lector`, `libro`, `db`) y ambos se cargan en el mismo
proceso cuando la web sirve los dos apartados. Importar siempre `rst.x`.

De `generador\` sí se toma prestado lo que no tiene por qué existir dos veces:
`db.py`, que habla con Supabase, y `legal.py`, que es la única definición del
descargo de responsabilidad. Por eso esa carpeta entra al camino de módulos
aquí, y no en cada archivo del paquete.
"""
import os
import sys

_GENERADOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'generador')
if _GENERADOR not in sys.path:
    sys.path.insert(0, _GENERADOR)
