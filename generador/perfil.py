# -*- coding: utf-8 -*-
r"""Lo que la exógena no responde y solo sabe el contribuyente.

Cinco preguntas. Ninguna llega en el reporte de la DIAN y ninguna se puede
deducir: si es casado, cuántos hijos tiene, si paga intereses de vivienda, si
paga ICETEX y si es residente fiscal. Todas mueven la liquidación —deducciones
del art. 119 y del art. 387— y por eso el libro deja sus casillas abiertas.

Hasta agosto de 2026 se preguntaban **después**: el libro salía con las cinco
en blanco y alguien las llenaba a mano en Excel. Ahora se preguntan en la web,
en el paso de confirmación, y el libro sale ya diligenciado.

Son **opcionales** a propósito. Quien sube el archivo no siempre tiene los
datos a la mano, y trabar la generación por eso convertiría una ayuda en un
obstáculo. Lo que quede sin responder sale en blanco —igual que antes— y el
libro lo señala.

Este módulo es la única definición: de aquí salen el formulario de la web y las
filas de la hoja «1. Resumen». Si estuvieran escritas dos veces, se irían
separando.
"""

# clave, pregunta, qué se escribe al lado, dónde impacta.
# `efecto=None` es la fila de los hijos: su texto es una fórmula de Excel que
# se arma en `sheet_resumen`, porque depende de la UVT del año.
PREGUNTAS = [
    ('casado', '¿Es casado o vive en unión permanente?',
     'Nombre e identificación del cónyuge',
     'El cónyuge en situación de dependencia cuenta como dependiente — art. 387 par. 2 E.T.'),
    ('hijos', '¿Tiene hijos? ¿Cuántos?',
     'Número de hijos', None),
    ('hipoteca', '¿Tiene crédito hipotecario de vivienda?',
     'Entidad e intereses pagados en el año',
     'Los intereses son deducibles hasta 1.200 UVT al año — art. 119 E.T.'),
    ('icetex', '¿Tiene crédito educativo (ICETEX u otro)?',
     'Entidad e intereses pagados en el año',
     'Los intereses de préstamos del ICETEX son deducibles hasta 100 UVT — art. 119 E.T.'),
    ('residente', '¿Tiene residencia fiscal en Colombia?',
     'Días de permanencia en el país durante el año',
     'Define si tributa sobre renta de fuente mundial y presenta el formulario 210 — art. 10 E.T.'),
]

# La fila de los hijos pide un número, no un texto libre: de ahí sale la
# fórmula de la deducción por dependientes.
NUMERICAS = {'hijos'}

RESPUESTAS = ('', 'Sí', 'No')      # vacío = «todavía no lo he confirmado»


def desde_formulario(campos):
    """Los campos del formulario → el perfil que viaja en el CLIENTE.

    Solo se guarda lo que se respondió. Un «No» es una respuesta y se guarda;
    dejar la casilla en blanco no lo es, y se omite para que el libro la deje
    abierta, que es exactamente lo que hacía antes.
    """
    perfil = {}
    for clave, _, _, _ in PREGUNTAS:
        respuesta = (campos.get('perfil_' + clave) or '').strip()
        detalle = (campos.get('detalle_' + clave) or '').strip()[:120]
        if respuesta not in RESPUESTAS:
            respuesta = ''
        if respuesta or detalle:
            perfil[clave] = {'respuesta': respuesta, 'detalle': detalle}
    return perfil


def sin_responder(perfil):
    """Cuáles quedaron en blanco. Alimenta la alerta informativa del caso."""
    perfil = perfil or {}
    return [pregunta for clave, pregunta, _, _ in PREGUNTAS
            if not (perfil.get(clave) or {}).get('respuesta')]


def alerta(perfil, codigo='P1'):
    """Deja constancia de lo que quedó sin responder, o None si está completo.

    Es INFORMATIVA y no ALTA a propósito: que falte un dato del contribuyente
    no significa que la clasificación esté mal, que es lo que mide el semáforo.
    Pero tiene que quedar escrito, porque es lo que separa un libro terminado
    de uno al que le falta la mitad de las deducciones.
    """
    faltan = sin_responder(perfil)
    if not faltan:
        return None
    return (codigo, 'INFORMATIVO',
            f'{len(faltan)} dato(s) que solo tiene el contribuyente, sin responder',
            'Sin responder: ' + ' · '.join(faltan)
            + '. No llegan por exógena y ninguno se puede deducir del reporte.',
            'Confírmelos con el contribuyente y complételos en las casillas de '
            'fondo crema de la hoja «1. Resumen»; después cargue el valor en la '
            'hoja que indica cada fila.')
