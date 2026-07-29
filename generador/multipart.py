# -*- coding: utf-8 -*-
r"""Lectura del archivo de un formulario multipart/form-data, sin dependencias.

El módulo `cgi` de la librería estándar desapareció en Python 3.13, y aquí solo
hace falta una cosa: sacar el .xlsx que subió el usuario. Lo usan por igual la
bandeja local y la función de Vercel.
"""
import re

# Los navegadores mandan filename entre comillas; otros clientes no. Se aceptan
# las dos formas para no rechazar un archivo válido por un detalle de formato.
_FILENAME = re.compile(r'filename\s*=\s*(?:"([^"]*)"|([^;\r\n]*))', re.I)
_BOUNDARY = re.compile(r'boundary=(?:"([^"]+)"|([^;]+))', re.I)


def extraer_archivo(cuerpo, content_type):
    """Devuelve (nombre, bytes) del primer archivo del envío."""
    m = _BOUNDARY.search(content_type or '')
    if not m:
        raise ValueError('El envío no trae la marca de separación (boundary).')
    frontera = ('--' + (m.group(1) or m.group(2)).strip()).encode()
    for parte in cuerpo.split(frontera):
        if b'\r\n\r\n' not in parte:
            continue
        cab, datos = parte.split(b'\r\n\r\n', 1)
        fn = _FILENAME.search(cab.decode('utf-8', 'replace'))
        if not fn:
            continue
        nombre = (fn.group(1) or fn.group(2) or '').strip()
        if nombre:
            return nombre, datos.rstrip(b'\r\n-')
    raise ValueError('No se recibió ningún archivo.')
