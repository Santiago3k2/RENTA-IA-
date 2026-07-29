# -*- coding: utf-8 -*-
r"""
PLANTILLA DE DATOS — estructura que consume el generador.

Los datos de este archivo son FICTICIOS: sirven solo para documentar el formato.
Los casos reales los produce `autogen.py` a partir del reporte de exógena y se
guardan fuera del repositorio (ver .gitignore), porque son datos tributarios de
personas reales.

    python autogen.py "ruta\reporteExogena.xlsx"     # genera el datos.py real
    python generar.py --datos "ruta\datos.py"        # solo regenera el libro
"""

CLIENTE = {

    # ─────────── 1 · IDENTIFICACIÓN ───────────
    'nombre':          'PEREZ GOMEZ JUAN CARLOS',      # mayúsculas, franja de cada hoja
    'nombre_titulo':   'Pérez Gómez Juan Carlos',      # como se lee en la portada
    'nombre_archivo':  'Perez Gomez Juan Carlos',      # carpeta y nombre del .xlsx, sin tildes
    'identificacion':  'C.C. 00.000.000',
    'ultimos_digitos': '00',
    'ano_gravable':    '2025',
    'ano_siguiente':   '2026',
    'ano_anterior':    '2024',
    'uvt':             49799,                          # UVT del año — verificar cada año
    'fuente':          'Exógena DIAN · corte 00-xxx-0000',
    'registros':       0,

    # Topes precalculados por la DIAN, del encabezado del reporte. El validador
    # compara lo reconstruido contra estos valores: es la prueba de que la
    # clasificación quedó bien.
    'topes_dian': {'ingresos': 0, 'patrimonio': 0, 'consumos': 0,
                   'movimientos': 0, 'compras': 0},

    # Honorarios/servicios llevados a R43 (sujetos a costos): se excluyen de la
    # base de la renta exenta del 25%. Cero si no aplica.
    'base_25_excluir': 0,

    # ─────────── 2 · DECLARACIÓN ANTERIOR ───────────
    # Solo el patrimonio y el saldo a favor vienen por exógena. El impuesto neto
    # y el anticipo se toman de esa declaración; en 0 quedan como casillas editables.
    'patrimonio_bruto_anterior': 0,
    'saldo_favor_anterior':      0,
    'anticipo_previo':           0,
    'impuesto_neto_anterior':    0,
    'porcentaje_anticipo':       0.75,   # 0.25 primer año · 0.50 segundo · 0.75 tercero+

    # ─────────── 3 · PATRIMONIO ───────────
    'efectivo': ['Efectivo en caja'],

    # (entidad y cuenta, tipo, saldo exógena o None)
    'cuentas': [
        ('Banco Ejemplo S.A. — 00000000000', 'Cuenta de ahorros', 1000000),
        ('Banco Ejemplo S.A. — 11111111111', 'Depósito electrónico', None),
    ],

    # (entidad y cuenta, calidad del titular, % participación, saldo, resaltar_rojo)
    'cdt': [
        ('Banco Ejemplo S.A. — 0000000', 'Titular principal', 1.0, 5000000, False),
    ],

    # (entidad, % participación, valor declarado en MUISCA)
    'inversiones': [
        ('Cooperativa Ejemplo — aportes sociales', 1.0, 250000),
    ],

    # (deudor, concepto, valor)
    'cuentas_cobrar': [],
    'cuentas_cobrar_filas_libres': 1,

    # (entidad que declara, fondo que recibe, valor consignado)
    'cesantias': [],

    # (matrícula, % participación, avalúo catastral del PREDIO COMPLETO)
    # El valor patrimonial aplica el porcentaje: en copropiedades es lo que evita
    # declarar el inmueble entero.
    'inmuebles': [
        ('000000', 1.0, 80000000),
    ],
    'inmuebles_filas_libres': 2,

    # (placa, entidad donde está inscrito, avalúo)
    'vehiculos': [],

    # (acreedor, concepto, saldo exógena)
    'pasivos': [
        ('Banco Ejemplo S.A.', '1315 · Cuentas por pagar', 2000000),
    ],

    # ─────────── 4 · INGRESOS ───────────
    # Todas las listas: (pagador, concepto, valor reportado en el prevalidador)
    'rentas_trabajo': [
        ('Empresa Ejemplo S.A.S.', '2276 · Pagos por salarios', 30000000),
    ],
    # Índices (base 0) de las filas anteriores que son cesantías e intereses
    # exentos del art. 206 num. 4 — forman la base del R36.
    'indices_cesantias_exentas': [],

    'incrngo_trabajo': [
        ('Empresa Ejemplo S.A.S.', '2276 · Aportes obligatorios a salud a cargo del trabajador', 1200000),
    ],
    'rentas_capital': [],
    'rentas_no_laborales': [],

    # ─────────── 5 · RETENCIONES ───────────
    # Agrupadas por concepto: (concepto, [(agente, cuenta, retención), ...])
    'retenciones': [],
    # (origen, base informada o None, tarifa, retención estimada o None, estado)
    'retenciones_esperadas': [],

    # ─────────── 6 · CONSIGNACIONES Y TOPES ───────────
    'movimientos': [                      # (entidad, cuenta, tipo, valor)
        ('Banco Ejemplo S.A.', '00000000000', 'Cuenta de ahorro', 40000000),
    ],
    'movimientos_excluidos': [],          # titular secundario, suscripción de FIC…
    'consumos_tarjeta': [],               # (detalle, valor)
    'compras_fe': 0,                      # tope 5
    'base_fe':    0,                      # monto susceptible del beneficio del 1%

    # ─────────── 7 · ALERTAS ───────────
    # (código, severidad, hallazgo, detalle, acción requerida)
    # Severidades: ALTA · MEDIA · VERIFICADO · NORMATIVO · INFORMATIVO
    'alertas': [
        ('A1', 'MEDIA', 'Ejemplo de hallazgo',
         'Detalle de lo encontrado, con las cifras que lo sustentan.',
         'Qué debe hacer el contador antes de liberar el caso.'),
    ],

    # ─────────── 8 · DETALLE DE LA EXÓGENA ───────────
    # (NIT, nombre, detalle reportado, valor, clasificación asignada, depuración)
    'detalle_exogena': [
        ('000000000', 'EMPRESA EJEMPLO S.A.S.', 'Pagos por salarios (Concepto: 2276)',
         30000000, 'R32 · Rentas de trabajo', ''),
    ],
}


# ═══════════════════════════════════════════════════════════════════════
# TEXTOS DEL CASO — prosa que describe hallazgos de ESTE contribuyente.
# Se reescribe en cada declaración. Si una clave no aplica, dejar '' y el
# bloque correspondiente se omite.
# ═══════════════════════════════════════════════════════════════════════
TEXTOS = {
    'sub_resumen': 'Clasificación de los registros del reporte de exógena, con la depuración separada por cédula, la liquidación del impuesto y el anticipo. Las casillas de fondo crema son editables y el libro entero se recalcula con ellas.',
    'sub_patrimonio': 'Activos agrupados de mayor a menor liquidez. Cada grupo separa lo que informó la exógena de lo que debe diligenciarse con el certificado de la entidad, deja espacio para el ajuste fiscal y termina en el valor patrimonial que se lleva al formulario.',
    'sub_ingresos': 'Los ingresos del período distribuidos por subcédula. Cada partida enfrenta lo REPORTADO en el prevalidador contra lo CERTIFICADO por el tercero, y muestra la diferencia.',
    'sub_retenciones': 'Certificados de retención agrupados por concepto.',
    'sub_anticipo': 'El artículo 807 E.T. permite calcular el anticipo por dos métodos y optar por el que arroje el MENOR valor.',
    'sub_alertas': 'Ordenadas por impacto. Las de severidad ALTA deben resolverse antes de liberar el caso.',
    'sub_consignaciones': 'Movimientos informados. No se llevan a ningún renglón del formulario, pero determinan la obligación de declarar.',
    'sub_detalle': 'Los registros originales del reporte con la clasificación asignada a cada uno.',

    'nota_cuentas': 'NOTA 2 — «Valor real» es el saldo que certifica la entidad y «Valor patrimonial» el que se declara.',
    'nota_cdt': 'NOTA 3 — Valor patrimonial = Valor real × Porcentaje + Ajuste fiscal.',
    'nota_inversiones': 'NOTA 4 — El costo fiscal queda en blanco hasta tener el certificado de cada sociedad.',
    'nota_cxc': 'NOTA 5 — La última fila queda abierta para cuentas por cobrar que no viajan por exógena.',
    'nota_cesantias': 'NOTA 6 — El valor patrimonial es la suma del saldo anterior y lo consignado en el período.',
    'nota_pasivos': 'NOTA 9 — Art. 283 E.T.: los pasivos deben estar respaldados con documentos de fecha cierta.',
    'callout_brecha': ('DIFERENCIA PATRIMONIAL POR EXPLICAR',
        'Texto que explica la diferencia entre el patrimonio reconstruido y el declarado el año anterior.'),

    'nota_trabajo': 'NOTA 11 — Si el certificado difiere de lo reportado, declare el mayor valor.',
    'nota_capital': '',
    'callout_reclasificacion': ('', ''),
    'nota_r36': 'Cesantías e intereses exentos del art. 206 num. 4.',

    'nota_retencion': 'Al diligenciar el formulario, el total se redondea al múltiplo de mil más cercano (art. 577 E.T.).',
    'nota_esperadas': '',

    'nota_x_anticipo': 'El dato X se toma de la declaración del año anterior.',
    'nota_tabla_anticipo': 'El método 2 conviene cuando el impuesto neto del año anterior fue inferior al de este año.',
    'nota_saldo_anticipo': 'No disponible en la exógena: se obtiene de la declaración del año anterior.',
    'callout_rango': ('RANGO DE RESULTADOS',
        'El saldo a pagar depende del método de anticipo y del impuesto neto del año anterior.'),

    'sensibilidad': '',

    'nota_tope4': 'Movimientos informados por las entidades financieras.',
    'callout_cruce': ('LECTURA DEL CRUCE: MOVIMIENTOS FRENTE A INGRESOS',
        'Una diferencia grande entre movimientos e ingresos es normal, pero es el indicador que activa un requerimiento.'),
    'label_consumos_total': 'Total consumos con tarjeta',

    'callout_prioridad': ('PRIORIDAD DE GESTIÓN',
        'Resuelva las alertas de severidad ALTA antes de diligenciar el formulario.'),

    'como_leer': 'La columna «Valor» es el dato en BRUTO tal como lo reportó el tercero: sumarla NO da los totales de las hojas anteriores, porque todavía incluye las partidas depuradas.',

    'validacion_cruzada': 'Los totales reconstruidos se comparan contra los topes precalculados por la DIAN.',
    'kpi_ingresos_foot': 'Trabajo, capital y no laborales',
    'kpi_impuesto_foot': 'Tabla del art. 241 E.T.',
    'plazo_grande': 'CONSULTE EL DECRETO DE PLAZOS',
}
