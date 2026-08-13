# -*- coding: utf-8 -*-
r"""Componente inflacionario de los rendimientos financieros — art. 38 E.T.

La parte de un rendimiento financiero que solo repone la inflación no es
ingreso: no enriquece a nadie. El art. 38 E.T. la trata como ingreso NO
constitutivo de renta ni ganancia ocasional para las personas naturales, y el
Gobierno **fija por decreto, cada año, qué porcentaje del rendimiento
corresponde a esa inflación**.

Va en la cédula de RENTAS DE CAPITAL (R58 → R59) y solo sobre los rendimientos
financieros: los arrendamientos y los ingresos de mandato de esa misma cédula
no lo tienen.

**Cuáles llevan componente lo dice el propio prevalidador de la DIAN**, en su
columna de uso sugerido: para un CDT reza «… | R58 Ingresos brutos por rentas
de capital | R59 Ingresos no constitutivos por rentas de capital». Cuánto, no
—eso es el porcentaje del decreto—, pero el CUÁLES sale de ahí y no de adivinar
por el texto. `clasificador.py` recoge esos índices en
`indices_incrngo_capital`; el texto del concepto solo decide en reportes de
años anteriores, que no traen esa sugerencia.

Cuando el texto dice «rendimientos» y la DIAN no lo marcó, gana la DIAN y el
caso levanta un aviso MEDIA para que el contador lo mire: la casilla de la base
queda abierta en el libro por si él decide ampliarla.

**Un año sin porcentaje publicado se liquida en cero y con la casilla abierta**,
igual que hacía `plazos.py` con un calendario que aún no se conocía. Es la regla
que fijó el usuario para este libro: ante una cifra oficial que no se pueda
verificar, casilla editable con nota, nunca un dato inventado. Cuando el dato
llega, se codifica aquí y pasa a llenarse solo.

Para cargar un año nuevo: añada su porcentaje a `PORCENTAJE` con el número del
decreto al lado. Nada más — el libro y el validador lo toman de aquí los dos.
"""
import re
import unicodedata

# Año gravable → fracción del rendimiento que es componente inflacionario.
# El porcentaje del AG 2025 (55,43%) lo aportó el usuario el 13-ago-2026.
PORCENTAJE = {
    '2025': 0.5543,
}

# Qué partida de la cédula de capital es un rendimiento financiero. Se mira el
# concepto que trae la exógena: «1020 · CDT Rendimientos Pagados», «6 · Cartera
# Colectiva Rendimientos Pagados», intereses de cuentas de ahorro. Lo que no
# case —arrendamientos, mandato inmobiliario, regalías— se queda fuera.
_ES_RENDIMIENTO = re.compile(r'rendimiento|interes')


def _norm(texto):
    """Minúsculas y sin tildes, para comparar «Interés» con «interes»."""
    sin = unicodedata.normalize('NFKD', str(texto or ''))
    return ''.join(c for c in sin if not unicodedata.combining(c)).lower()


def porcentaje(ano_gravable):
    """La fracción del año, o None si su decreto todavía no está cargado."""
    return PORCENTAJE.get(str(ano_gravable or '').strip())


def es_rendimiento_financiero(concepto):
    return bool(_ES_RENDIMIENTO.search(_norm(concepto)))


def base(rentas_capital, sugeridos=None):
    """Suma de los rendimientos financieros dentro de la cédula de capital.

    `sugeridos` son los índices que **la propia DIAN** marcó con R59 en la
    columna de uso sugerido del prevalidador. Cuando vienen, mandan: la DIAN
    distingue por concepto —de un mismo pagador marca los CDT del concepto 1020
    y no los del 5063— y esa tabla es la que rige al declarar. El texto del
    concepto solo decide cuando el reporte no trae la sugerencia, que es lo que
    pasa con los formatos de años anteriores.

    Devuelve `(total, indices)`. Los índices sirven para que la hoja de
    ingresos arme la fórmula sumando exactamente esas filas, en vez de pegar
    un total: el contador tiene que poder ver de dónde sale.
    """
    partidas = rentas_capital or []
    if sugeridos:
        indices = [i for i in sugeridos if 0 <= i < len(partidas)]
    else:
        indices = [i for i, (_, concepto, _) in enumerate(partidas)
                   if es_rendimiento_financiero(concepto)]
    return sum(partidas[i][2] for i in indices), indices


def calcular(C):
    """El componente inflacionario del caso: porcentaje, base y valor.

    `valor` es 0 cuando el año no tiene porcentaje cargado o cuando el
    contribuyente no tuvo rendimientos financieros; en los dos casos la
    depuración de capital queda como estaba antes de existir este módulo.
    """
    pct = porcentaje(C.get('ano_gravable'))
    total, indices = base(C.get('rentas_capital') or [],
                          C.get('indices_incrngo_capital'))
    # Mismo redondeo que el ROUND de Excel, para que el libro y el validador no
    # se separen en un peso.
    valor = int(total * (pct or 0) + 0.5 + 1e-9) if pct and total > 0 else 0
    return {'porcentaje': pct, 'base': total, 'indices': indices, 'valor': valor}
