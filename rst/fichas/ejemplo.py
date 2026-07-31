# -*- coding: utf-8 -*-
"""Plantilla de la ficha del contribuyente del SIMPLE.

Cópiala como `rst\\fichas\\<cliente>.py` y llénala. Es lo que el consolidado de
la DIAN NO trae y el motor no puede adivinar; se llena una vez por cliente y
sirve para todos sus bimestres: entre uno y otro solo cambian `bimestre`, `ano`
y las casillas del período.

Las fichas con datos reales no se versionan (ver .gitignore): son datos
tributarios de contribuyentes de verdad.
"""

FICHA = {
    # --- identificación (Sección A del Formulario 2593)
    'nombre': 'RAZÓN SOCIAL DEL CONTRIBUYENTE',
    'nit': '900000000',
    'dv': '',                       # dígito de verificación, del RUT
    'direccion_seccional': '',      # código de dirección seccional, del RUT
    'ciiu': '',                     # p. ej. '6621 / 6629 — Agentes de seguros'

    # --- período que se liquida
    'ano': 2026,
    'bimestre': 1,                  # 1 a 6

    # --- criterio tributario
    # El grupo es la decisión más delicada del caso: define la tarifa. No es un
    # dato que salga del archivo, es una calificación de la actividad.
    #   1 Tiendas, mini/micro-mercados y peluquería
    #   2 Comercio, industria, servicios técnicos y demás
    #   3 Servicios profesionales, consultoría y científicos
    #   4 Expendio de comidas y bebidas, y transporte
    'grupo': 2,
    'responsable_iva': True,

    # --- componente territorial (el SIMPLE integra el ICA y lo gira al municipio)
    'municipio': '',
    'cod_dane': '',
    'depto': '',
    'tarifa_ica': 0.0,              # consolidada, en decimal: 12,5 por mil = 0.0125

    # --- casillas del período (todas editables también en el libro)
    'incrngo': 0,                   # cas. 27 — ingresos no constitutivos de renta
    'ganancias_ocasionales': 0,     # cas. 28
    'devoluciones': 0,              # notas crédito que el archivo no traiga
    'ingresos_no_gravados_ica': 0,  # exportaciones, venta de activos fijos, etc.
    'retenciones_previas': 0,       # cas. 45 — solo en el 1.er bimestre en el SIMPLE
    'saldo_favor_iva_anterior': 0,
    'inc': 0,                       # impuesto al consumo, solo grupo 4
    'sanciones': 0,                 # extemporaneidad, si aplica

    # Aporte TOTAL a pensión (16% del IBC) pagado dentro del bimestre, según la
    # planilla PILA. El motor toma de ahí el 12% del empleador, que es lo único
    # descontable (Art. 903 Par. 4 ET). Solo se usa si el archivo de la DIAN no
    # trae el reporte de seguridad social, que es lo normal.
    'aporte_pension_total': 0,

    # --- varios municipios: si se declara en más de uno, en vez de los campos
    # sueltos de arriba se puede dar la lista completa
    # 'municipios': [
    #     {'codigo': '68001', 'nombre': 'Bucaramanga', 'depto': 'Santander',
    #      'ingresos': 0, 'no_gravados_ica': 0, 'tarifa': 0.0125},
    # ],
}
