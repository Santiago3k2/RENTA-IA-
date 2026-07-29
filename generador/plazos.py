# -*- coding: utf-8 -*-
"""Calendario oficial de vencimientos — renta de personas naturales residentes.

El día exacto lo fijan los DOS ÚLTIMOS dígitos del documento. Cada año gravable
tiene su propio calendario porque los festivos corren las fechas, así que aquí
solo se responden los años efectivamente cargados: para cualquier otro,
`vencimiento` devuelve None y el libro vuelve a dejar la casilla en blanco para
diligenciar. Antes que inventar una fecha, que la escriba el contador.

Fuente: calendario tributario publicado por la DIAN (decreto de plazos).
"""
import datetime

DIAS = ['LUNES', 'MARTES', 'MIÉRCOLES', 'JUEVES', 'VIERNES', 'SÁBADO', 'DOMINGO']
MESES = ['', 'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO',
         'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']

# Año gravable 2025 — declaración y pago durante 2026.
# Los saltos del calendario son los festivos: 17 de agosto (Asunción) y
# 12 de octubre (Día de la Raza), ambos lunes en 2026.
_AG2025 = (
    (8, 12, '01-02'), (8, 13, '03-04'), (8, 14, '05-06'), (8, 18, '07-08'),
    (8, 19, '09-10'), (8, 20, '11-12'), (8, 21, '13-14'), (8, 24, '15-16'),
    (8, 25, '17-18'), (8, 26, '19-20'), (8, 27, '21-22'), (8, 28, '23-24'),
    (8, 31, '25-26'),

    (9,  1, '27-28'), (9,  2, '29-30'), (9,  3, '31-32'), (9,  4, '33-34'),
    (9,  7, '35-36'), (9,  8, '37-38'), (9,  9, '39-40'), (9, 10, '41-42'),
    (9, 11, '43-44'), (9, 14, '45-46'), (9, 15, '47-48'), (9, 16, '49-50'),
    (9, 17, '51-52'), (9, 18, '53-54'), (9, 21, '55-56'), (9, 22, '57-58'),
    (9, 23, '59-60'), (9, 24, '61-62'), (9, 25, '63-64'), (9, 28, '65-66'),

    (10,  1, '67-68'), (10,  2, '69-70'), (10,  5, '71-72'), (10,  6, '73-74'),
    (10,  7, '75-76'), (10,  8, '77-78'), (10,  9, '79-80'), (10, 13, '81-82'),
    (10, 14, '83-84'), (10, 15, '85-86'), (10, 16, '87-88'), (10, 19, '89-90'),
    (10, 20, '91-92'), (10, 21, '93-94'), (10, 22, '95-96'), (10, 23, '97-98'),
    (10, 26, '99-00'),
)


def _expandir(tabla, ano_presenta):
    """Pasa la tabla de parejas a {dos dígitos: date}, exigiendo las 100 combinaciones.

    La verificación no es decorativa: un dígito que se pierda en la transcripción
    no rompe nada visible, simplemente deja una declaración con la fecha en blanco
    o —peor— hace pensar que el año no tiene calendario.
    """
    m = {}
    for mes, dia, pares in tabla:
        for d in pares.split('-'):
            if d in m:
                raise ValueError(f'dígitos {d} repetidos en el calendario de {ano_presenta}')
            m[d] = datetime.date(ano_presenta, mes, dia)
    faltan = {f'{i:02d}' for i in range(100)} - set(m)
    if faltan:
        raise ValueError(f'el calendario de {ano_presenta} no cubre: {sorted(faltan)}')
    return m


CALENDARIO = {
    2025: _expandir(_AG2025, 2026),
}


def _dos_digitos(valor):
    d = ''.join(c for c in str(valor or '') if c.isdigit())
    return d[-2:].rjust(2, '0') if d else None


def vencimiento(ano_gravable, documento):
    """Fecha límite de declaración y pago, o None si no hay calendario para ese año.

    `documento` puede ser la cédula completa o solo sus dos últimos dígitos.
    """
    try:
        ano = int(str(ano_gravable).strip())
    except (TypeError, ValueError):
        return None
    dig = _dos_digitos(documento)
    if dig is None:
        return None
    return CALENDARIO.get(ano, {}).get(dig)


def texto_grande(fecha):
    """'JUEVES 27 DE AGOSTO DE 2026' — la línea destacada del bloque de plazo."""
    return f'{DIAS[fecha.weekday()]} {fecha.day} DE {MESES[fecha.month]} DE {fecha.year}'


def frase(ano_gravable, documento):
    """Línea destacada ya resuelta, o None para que el llamador use su respaldo."""
    f = vencimiento(ano_gravable, documento)
    return texto_grande(f) if f else None
