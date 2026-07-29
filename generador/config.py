# -*- coding: utf-8 -*-
r"""Configuración de RENTA IA: lee el .env de la raíz del proyecto.

Solo librería estándar. Las variables de entorno del sistema mandan sobre el
archivo, para que en Vercel (donde no hay .env) todo funcione igual.

    from config import ajustes
    a = ajustes()
    a['SUPABASE_URL']

El .env NUNCA se sube al repositorio: contiene la clave de servicio, que salta
la RLS y ve los datos tributarios de todos los contribuyentes.
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(BASE)
RUTA_ENV = os.path.join(RAIZ, '.env')

CLAVES = ('SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY', 'SUPABASE_PROJECT_REF',
          'DATABASE_URL')


def leer_env(ruta=RUTA_ENV):
    """Devuelve el .env como diccionario. Si no existe, diccionario vacío."""
    valores = {}
    if not os.path.isfile(ruta):
        return valores
    with open(ruta, encoding='utf-8-sig') as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith('#') or '=' not in linea:
                continue
            k, v = linea.split('=', 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'':
                v = v[1:-1]
            valores[k.strip()] = v
    return valores


def ajustes():
    """.env + variables de entorno (estas últimas tienen prioridad)."""
    a = leer_env()
    for k in CLAVES:
        if os.environ.get(k):
            a[k] = os.environ[k]
    return a


def revisar(a=None):
    """Lista de problemas de configuración, en español y accionables.

    No se conecta a nada: solo mira que las piezas estén y tengan pinta válida.
    """
    a = a or ajustes()
    problemas = []

    url = a.get('SUPABASE_URL', '')
    if not url:
        problemas.append('Falta SUPABASE_URL.')
    elif not url.startswith('https://') or '.supabase.co' not in url:
        problemas.append(f'SUPABASE_URL no parece la URL del proyecto: {url}')

    k = a.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not k:
        problemas.append('Falta SUPABASE_SERVICE_ROLE_KEY. Panel de Supabase → '
                         'Project Settings → API Keys → clave secreta.')
    elif k.startswith('sb_publishable_'):
        problemas.append('SUPABASE_SERVICE_ROLE_KEY tiene una clave PUBLICABLE. '
                         'El backend necesita la secreta (sb_secret_…): la '
                         'publicable no pasa la RLS y todo responderá vacío.')
    elif k.startswith('sb_secret_') and len(k) < 35:
        problemas.append(f'SUPABASE_SERVICE_ROLE_KEY parece cortada '
                         f'({len(k)} caracteres). Cópiela completa con el botón '
                         'de copiar del panel, no seleccionando el texto.')
    elif not (k.startswith('sb_secret_') or k.startswith('eyJ')):
        problemas.append('SUPABASE_SERVICE_ROLE_KEY no tiene forma de clave de '
                         'Supabase (debe empezar en «sb_secret_»).')

    d = a.get('DATABASE_URL', '')
    if d and '[PASSWORD]' in d:
        problemas.append('DATABASE_URL todavía tiene el marcador [PASSWORD]: '
                         'reemplácelo por la contraseña de la base.')
    return problemas


if __name__ == '__main__':
    a = ajustes()
    print(f'.env: {RUTA_ENV}')
    for k in CLAVES:
        v = a.get(k, '')
        if not v:
            estado = '(vacía)'
        elif 'KEY' in k or 'DATABASE' in k:
            estado = f'{v[:14]}… ({len(v)} caracteres)'
        else:
            estado = v
        print(f'  {k:28} {estado}')
    fallas = revisar(a)
    print()
    print('Configuración completa.' if not fallas else 'Pendientes:')
    for p in fallas:
        print(f'  · {p}')
