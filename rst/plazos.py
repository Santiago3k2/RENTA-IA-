# -*- coding: utf-8 -*-
"""Calendario de plazos del anticipo bimestral del SIMPLE (Formulario 2593).

Ojo con la diferencia frente a renta de personas naturales: aquí el plazo
depende del **último dígito** del NIT —uno solo—, no de los dos últimos.
Copiar la lógica del otro calendario daría fechas equivocadas.

Transcrito de la tabla oficial que aportó el usuario (31-jul-2026), guardada en
`referencia\\calendario plazos RST.png`. Cada anticipo vence en el mes siguiente
al cierre del bimestre; el del sexto bimestre se corre a enero del año próximo.

`_verificar` exige las 60 combinaciones (6 bimestres × 10 dígitos) al importar:
un dígito perdido en la transcripción revienta de una vez, en vez de dejar una
declaración con la fecha en blanco o, peor, con una fecha inventada.
"""
import datetime

# año gravable → bimestre → último dígito del NIT → (mes, día, desplazamiento de año)
PLAZOS = {
    2026: {
        1: (5, {1: 12, 2: 13, 3: 14, 4: 15, 5: 19,
                6: 20, 7: 21, 8: 22, 9: 25, 0: 26}, 0),
        2: (6, {1: 10, 2: 11, 3: 12, 4: 16, 5: 17,
                6: 18, 7: 19, 8: 22, 9: 23, 0: 24}, 0),
        3: (7, {1: 9, 2: 10, 3: 14, 4: 15, 5: 16,
                6: 17, 7: 21, 8: 22, 9: 23, 0: 24}, 0),
        4: (9, {1: 9, 2: 10, 3: 11, 4: 14, 5: 15,
                6: 16, 7: 17, 8: 18, 9: 21, 0: 22}, 0),
        5: (11, {1: 11, 2: 12, 3: 13, 4: 17, 5: 18,
                 6: 19, 7: 20, 8: 23, 9: 24, 0: 25}, 0),
        # El sexto bimestre se declara y paga en enero del año siguiente.
        6: (1, {1: 13, 2: 14, 3: 15, 4: 18, 5: 19,
                6: 20, 7: 21, 8: 22, 9: 25, 0: 26}, 1),
    },
}


def _verificar():
    for ano, bimestres in PLAZOS.items():
        if sorted(bimestres) != [1, 2, 3, 4, 5, 6]:
            raise ValueError('El calendario del SIMPLE de %s no tiene los 6 bimestres: %s'
                             % (ano, sorted(bimestres)))
        for bim, (mes, dias, _) in bimestres.items():
            if sorted(dias) != list(range(10)):
                faltan = sorted(set(range(10)) - set(dias))
                raise ValueError(
                    'Al calendario del SIMPLE %s, bimestre %d, le faltan los dígitos %s. '
                    'Revise la transcripción antes de usarlo.' % (ano, bim, faltan))
            for d, dia in dias.items():
                if not 1 <= dia <= 31 or not 1 <= mes <= 12:
                    raise ValueError('Fecha imposible en %s bimestre %d dígito %d: %d/%d'
                                     % (ano, bim, d, dia, mes))


_verificar()


def ultimo_digito(nit):
    """Último dígito del NIT, sin puntos ni dígito de verificación.

    El NIT puede venir como '901.555.552', '901555552' o '901555552-7'. El DV va
    después del guion y NO cuenta para el plazo: tomarlo por error correría la
    fecha de vencimiento.
    """
    limpio = str(nit).split('-')[0]
    digitos = [c for c in limpio if c.isdigit()]
    if not digitos:
        raise ValueError('No se pudo leer el NIT «%s» para calcular el plazo.' % nit)
    return int(digitos[-1])


def vencimiento(ano, bimestre, nit):
    """Fecha límite de declaración y pago. None si no hay calendario cargado."""
    bimestres = PLAZOS.get(ano)
    if not bimestres or bimestre not in bimestres:
        return None
    mes, dias, salto = bimestres[bimestre]
    return datetime.date(ano + salto, mes, dias[ultimo_digito(nit)])


def texto(ano, bimestre, nit):
    """Frase lista para el libro y para la web."""
    f = vencimiento(ano, bimestre, nit)
    if f is None:
        return ('No hay calendario de plazos cargado para el año gravable %s. '
                'Consulte el decreto del año y añádalo a rst/plazos.py.' % ano)
    meses = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
             'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
    return ('Vence el %d de %s de %d — según el último dígito del NIT (%d).'
            % (f.day, meses[f.month - 1], f.year, ultimo_digito(nit)))
