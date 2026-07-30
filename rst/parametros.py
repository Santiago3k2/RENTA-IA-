# -*- coding: utf-8 -*-
"""Parámetros tributarios del Régimen Simple de Tributación (SIMPLE).

Todo lo que cambia por año o por norma vive aquí y en ningún otro sitio.
Al llegar la resolución de UVT de un año nuevo se añade una línea a UVT y el
motor queda al día.
"""

# UVT por año gravable. Res. DIAN 000238 del 15-dic-2025 fijó la de 2026.
UVT = {
    2023: 42412,
    2024: 47065,
    2025: 49799,
    2026: 52374,
}

# Tabla del art. 908 ET sobre base BIMESTRAL en UVT, vigente tras la Sentencia
# C-540 del 12-dic-2023, que declaró inexequibles los numerales 4 y 5 añadidos
# por la Ley 2277 de 2022 y revivió la tabla de cuatro grupos.
# Cada tramo: (desde UVT, hasta UVT, tarifa).
TARIFAS = {
    1: [(0, 1000, 0.012), (1000, 2500, 0.028), (2500, 5000, 0.044), (5000, 16666, 0.056)],
    2: [(0, 1000, 0.016), (1000, 2500, 0.020), (2500, 5000, 0.035), (5000, 16666, 0.045)],
    3: [(0, 1000, 0.059), (1000, 2500, 0.073), (2500, 5000, 0.120), (5000, 16666, 0.145)],
    4: [(0, 1000, 0.034), (1000, 2500, 0.038), (2500, 5000, 0.055), (5000, 16666, 0.070)],
}

GRUPOS = {
    1: 'Tiendas, mini/micro-mercados y peluquería',
    2: 'Comercio, industria, servicios técnicos y demás',
    3: 'Servicios profesionales, consultoría y científicos',
    4: 'Expendio de comidas y bebidas, y transporte',
}

TARIFA_IVA = 0.19            # Art. 468 ET
TARIFA_RETEIVA = 0.15        # Art. 437-1 ET
PENSION_EMPLEADOR = 0.12     # Art. 33 Ley 100/93
PENSION_TOTAL = 0.16         # 12% patronal + 4% trabajador

TOPE_SIMPLE_UVT = 100000     # tope anual de ingresos para permanecer en el SIMPLE
TOPE_GRUPO3_UVT = 6000       # umbral del art. 908: por encima, tarifa anual mayor

BIMESTRES = {
    1: ('Enero y Febrero', (1, 2)),
    2: ('Marzo y Abril', (3, 4)),
    3: ('Mayo y Junio', (5, 6)),
    4: ('Julio y Agosto', (7, 8)),
    5: ('Septiembre y Octubre', (9, 10)),
    6: ('Noviembre y Diciembre', (11, 12)),
}

MESES = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
         7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre',
         12: 'Diciembre'}

# Fundamento normativo que se imprime en la hoja 8.
NORMAS = [
    ('Arts. 903 a 916 ET',
     'Libro Octavo — Impuesto unificado bajo el Régimen Simple de Tributación (SIMPLE).'),
    ('Art. 908 ET',
     'Tarifas. Los numerales 4 y 5 añadidos por la Ley 2277 de 2022 fueron declarados '
     'INEXEQUIBLES por la Sentencia C-540 del 12-dic-2023, reviviendo el num. 3 del art. 42 '
     'de la Ley 2155 de 2021 (4 grupos, tope 100.000 UVT).'),
    ('Concepto DIAN 172 del 12-mar-2024',
     'Los agentes, agencias y corredores de seguros (CIIU 6621/6629) tributan en el GRUPO 3 '
     '— servicios profesionales, de consultoría y científicos en los que predomina el factor '
     'intelectual. Tarifas 5,9% / 7,3% / 12% / 14,5%.'),
    ('Art. 910 ET',
     'Anticipo bimestral mediante recibo electrónico (Formulario 2593), con la información '
     'de ingresos por municipio.'),
    ('Art. 903 Par. 4 ET',
     'Los aportes a pensión a cargo del EMPLEADOR pagados en el bimestre se descuentan del '
     'anticipo. El descuento NO puede exceder el anticipo y NO puede cubrir el componente de '
     'ICA consolidado.'),
    ('Art. 911 ET',
     'Los contribuyentes del SIMPLE no están sujetos a retención en la fuente a título de '
     'renta ni de ICA, ni son agentes de retención (salvo pagos laborales).'),
    ('Art. 437-2 num. 9 ET',
     'Quien adquiere bienes o servicios gravados de un contribuyente del SIMPLE debe '
     'practicarle retención de IVA (15% del IVA, Art. 437-1).'),
    ('Art. 915 ET',
     'El responsable de IVA en el SIMPLE presenta declaración ANUAL de IVA (Form. 300) y '
     'transfiere el IVA bimestralmente en el recibo 2593.'),
    ('Art. 488 ET',
     'Solo da derecho a IVA descontable el impuesto de bienes/servicios que constituyan '
     'costo o gasto de la actividad productora de renta.'),
]


def uvt(ano):
    """UVT del año gravable. Falla fuerte si no está cargada: preferimos que
    reviente aquí a emitir una declaración con una base mal expresada."""
    if ano not in UVT:
        raise KeyError(
            'No está cargada la UVT del año %s. Añádela a rst/parametros.py '
            'con la resolución de la DIAN correspondiente.' % ano)
    return UVT[ano]


def tarifa(grupo, base_uvt):
    """Tarifa SIMPLE consolidada del bimestre para un grupo y una base en UVT."""
    if grupo not in TARIFAS:
        raise KeyError('Grupo de actividad SIMPLE inválido: %r (debe ser 1 a 4)' % grupo)
    tramos = TARIFAS[grupo]
    for desde, hasta, tar in tramos:
        if base_uvt <= hasta:
            return tar
    return tramos[-1][2]        # por encima del último tramo se mantiene la mayor


def nombre_bimestre(n):
    if n not in BIMESTRES:
        raise KeyError('Bimestre inválido: %r (debe ser 1 a 6)' % n)
    return BIMESTRES[n][0]


def meses_bimestre(n):
    return BIMESTRES[n][1]
