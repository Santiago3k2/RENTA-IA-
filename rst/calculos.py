# -*- coding: utf-8 -*-
"""Liquidación del anticipo bimestral del SIMPLE (Formulario 2593).

Replica en Python puro toda la aritmética del libro y produce, además, las
validaciones que dan el semáforo. El principio es el mismo del módulo de
renta: en renta la señal son los topes precalculados de la DIAN; aquí son
razones que deben dar exactas —IVA sobre ingresos gravados = 19%, ReteIVA
sobre IVA = 15%—. Si no dan, hay una partida mal leída o mal clasificada.

  VERDE    — las razones cuadran y no hay alertas de prioridad ALTA
  AMARILLO — cuadran pero quedan alertas ALTA por resolver
  ROJO     — las razones no cuadran: no se debe presentar así
"""
import math

from . import parametros as P

TOL_RAZON = 0.0005      # 0,05 puntos porcentuales
TOL_PESOS = 10.0


def rnd(x):
    """ROUND de Excel: mitades lejos de cero."""
    s = 1 if x >= 0 else -1
    return s * math.floor(abs(x) + 0.5 + 1e-9)


def rnd1000(x):
    return rnd(x / 1000.0) * 1000


# ----------------------------------------------------------------- agregados

def _resumen_meses(ventas, meses):
    """Ventas agrupadas por mes del bimestre, en el orden del bimestre."""
    filas = []
    for m in meses:
        del_mes = [v for v in ventas if v['fecha'] and v['fecha'].month == m]
        filas.append({
            'mes': m,
            'nombre': P.MESES[m],
            'facturas': len(del_mes),
            'gravado': sum(v['gravado'] for v in del_mes),
            'no_gravado': sum(v['no_gravado'] for v in del_mes),
            'iva': sum(v['iva'] for v in del_mes),
            'reteiva': sum(v['reteiva'] for v in del_mes),
        })
    return filas


def _clasificar_compras(compras, tarifa_iva):
    """Separa las compras que generan IVA descontable de las que no.

    Cuando el archivo no trae la base gravable se deduce dividiendo el IVA
    entre la tarifa general; es lo único que puede hacerse con ese dato.
    """
    gravadas, excluidas = [], []
    for c in compras:
        d = dict(c)
        if d['iva']:
            if not d['base']:
                d['base'] = d['iva'] / tarifa_iva
            d['clasificacion'] = 'Gravada — IVA descontable'
            gravadas.append(d)
        else:
            d['base'] = 0.0
            d['clasificacion'] = 'Excluida / no gravada'
            excluidas.append(d)
    return gravadas, excluidas


def _pension_empleador(planillas):
    """Parte patronal (12%) de cada planilla pagada dentro del bimestre.

    El reporte de PILA trae el aporte total (16% del IBC): el 12% del empleador
    es descontable y el 4% del trabajador no. Los intereses de mora tampoco.
    """
    total = 0
    detalle = []
    for pl in planillas:
        patronal = rnd(pl['aporte'] / P.PENSION_TOTAL * P.PENSION_EMPLEADOR)
        d = dict(pl)
        d['patronal'] = patronal
        detalle.append(d)
        total += patronal
    return total, detalle


# --------------------------------------------------------------- liquidación

def liquidar(ficha, fuente):
    """ficha (datos del contribuyente) + fuente (salida de lector.leer) →
    dict con toda la liquidación, las validaciones y las alertas."""
    ano = ficha['ano']
    bim = ficha['bimestre']
    uvt = P.uvt(ano)
    meses = P.meses_bimestre(bim)

    ventas = fuente['ventas']
    del_periodo = [v for v in ventas if v['fecha'] and v['fecha'].month in meses
                   and v['fecha'].year == ano]
    fuera = [v for v in ventas if v not in del_periodo]

    por_mes = _resumen_meses(del_periodo, meses)
    gravados = sum(f['gravado'] for f in por_mes)
    no_gravados = sum(f['no_gravado'] for f in por_mes)
    iva_generado = sum(f['iva'] for f in por_mes)
    reteiva_fe = sum(f['reteiva'] for f in por_mes)

    incrngo = float(ficha.get('incrngo', 0) or 0)
    ganancias = float(ficha.get('ganancias_ocasionales', 0) or 0)
    devoluciones = float(ficha.get('devoluciones', 0) or 0)

    base = gravados + no_gravados - incrngo - ganancias - devoluciones
    base_uvt = base / uvt
    grupo = int(ficha['grupo'])
    tar = P.tarifa(grupo, base_uvt)
    anticipo = rnd(base * tar)

    # Componente territorial: el SIMPLE integra el ICA y se gira al municipio.
    municipios = ficha.get('municipios') or [{
        'codigo': ficha.get('cod_dane', ''),
        'nombre': ficha.get('municipio', ''),
        'depto': ficha.get('depto', ''),
        'ingresos': base + incrngo + ganancias,   # ingresos brutos del municipio
        'no_gravados_ica': float(ficha.get('ingresos_no_gravados_ica', 0) or 0),
        'tarifa': float(ficha['tarifa_ica']),
    }]
    filas_ica = []
    for m in municipios:
        ingresos_mun = float(m.get('ingresos', gravados + no_gravados))
        base_ica = ingresos_mun - float(m.get('no_gravados_ica', 0) or 0)
        filas_ica.append({
            'codigo': m.get('codigo', ''),
            'nombre': m.get('nombre', ''),
            'depto': m.get('depto', ''),
            'ingresos': ingresos_mun,
            'no_gravados_ica': float(m.get('no_gravados_ica', 0) or 0),
            'base': base_ica,
            'tarifa': float(m['tarifa']),
            'ica': rnd(base_ica * float(m['tarifa'])),
        })
    ica = sum(f['ica'] for f in filas_ica)

    nacional = anticipo - ica
    pension, planillas = _pension_empleador(fuente['seg_social'])
    descuento_pension = min(pension, max(0, nacional))
    retenciones_previas = float(ficha.get('retenciones_previas', 0) or 0)
    anticipo_neto = max(0, nacional - descuento_pension - retenciones_previas)

    # IVA del bimestre: se transfiere en el 2593 aunque la declaración sea anual.
    gravadas, excluidas = _clasificar_compras(fuente['compras'], P.TARIFA_IVA)
    iva_descontable = sum(c['iva'] for c in gravadas)
    saldo_iva = iva_generado - iva_descontable
    saldo_favor_iva = float(ficha.get('saldo_favor_iva_anterior', 0) or 0)
    iva_pagar = max(0.0, saldo_iva - reteiva_fe - saldo_favor_iva)

    inc = float(ficha.get('inc', 0) or 0)          # solo grupo 4 (bares y restaurantes)
    sanciones = float(ficha.get('sanciones', 0) or 0)
    total = anticipo_neto + ica + iva_pagar + inc + sanciones
    total_mil = rnd1000(total)

    reteiva_certificados = sum(a['contabilidad'] for a in fuente['reteiva'])

    liq = {
        'ano': ano, 'bimestre': bim, 'uvt': uvt, 'meses': meses,
        'nombre_bimestre': P.nombre_bimestre(bim),
        'por_mes': por_mes,
        'facturas': del_periodo,
        'facturas_fuera_periodo': fuera,
        'compras_gravadas': gravadas,
        'compras_excluidas': excluidas,
        'agentes_reteiva': fuente['reteiva'],
        'planillas': planillas,

        'ingresos_gravados': gravados,
        'ingresos_no_gravados': no_gravados,
        'incrngo': incrngo,
        'ganancias_ocasionales': ganancias,
        'devoluciones': devoluciones,
        'base': base,
        'base_uvt': base_uvt,
        'grupo': grupo,
        'tarifa': tar,
        'anticipo_consolidado': anticipo,

        'filas_ica': filas_ica,
        'ica': ica,
        'componente_nacional': nacional,
        'pension_patronal': pension,
        'descuento_pension': descuento_pension,
        'retenciones_previas': retenciones_previas,
        'anticipo_neto': anticipo_neto,

        'iva_generado': iva_generado,
        'iva_descontable': iva_descontable,
        'saldo_iva': saldo_iva,
        'reteiva': reteiva_fe,
        'reteiva_certificados': reteiva_certificados,
        'saldo_favor_iva_anterior': saldo_favor_iva,
        'iva_pagar': iva_pagar,

        'inc': inc,
        'sanciones': sanciones,
        'total': total,
        'total_mil': total_mil,
    }
    liq['totales_declarados'] = fuente.get('totales_declarados', {})
    liq['validaciones'] = validar(liq, ficha, fuente)
    liq['alertas'] = alertas(liq, ficha, fuente)
    liq['semaforo'] = semaforo(liq)
    return liq


# --------------------------------------------------------------- validación

def validar(liq, ficha, fuente):
    """Las razones que deben dar exactas. Son el equivalente, en el SIMPLE, de
    los topes precalculados de la DIAN en la declaración de renta."""
    v = []
    g, iva, rete = liq['ingresos_gravados'], liq['iva_generado'], liq['reteiva']

    razon_iva = iva / g if g else 0.0
    v.append({
        'nombre': 'IVA generado ÷ ingresos gravados',
        'valor': razon_iva, 'esperado': P.TARIFA_IVA, 'formato': '%',
        'ok': abs(razon_iva - P.TARIFA_IVA) <= TOL_RAZON, 'critica': True,
        'nota': 'Tarifa general del art. 468 ET. Si no da 19%, hay facturas con '
                'tarifa distinta o mal leídas.',
    })
    razon_rete = rete / iva if iva else 0.0
    v.append({
        'nombre': 'ReteIVA ÷ IVA generado',
        'valor': razon_rete, 'esperado': P.TARIFA_RETEIVA, 'formato': '%',
        'ok': abs(razon_rete - P.TARIFA_RETEIVA) <= TOL_RAZON, 'critica': True,
        'nota': 'Art. 437-1 ET. Una razón menor indica clientes que no le '
                'practicaron la retención debiendo hacerlo.',
    })
    dif = liq['reteiva_certificados'] - rete
    v.append({
        'nombre': 'ReteIVA: certificados vs. facturación electrónica',
        'valor': dif, 'esperado': 0.0, 'formato': '$',
        'ok': abs(dif) <= TOL_PESOS, 'critica': False,
        'nota': 'La DIAN cruza contra el certificado del agente retenedor, no '
                'contra la contabilidad.',
    })
    suma_facturas = sum(f['gravado'] + f['no_gravado'] for f in liq['facturas'])
    dif_base = suma_facturas - (liq['ingresos_gravados'] + liq['ingresos_no_gravados'])
    v.append({
        'nombre': 'Detalle de facturas vs. resumen mensual',
        'valor': dif_base, 'esperado': 0.0, 'formato': '$',
        'ok': abs(dif_base) <= TOL_PESOS, 'critica': True,
        'nota': 'Cuadre interno del libro: el detalle debe sumar el resumen.',
    })

    # Totales que el propio consolidado trae precalculados al pie de cada hoja.
    # Son al SIMPLE lo que los topes de la DIAN a la declaración de renta: si
    # nuestra suma no los reproduce, se leyó de más o de menos.
    declarados = fuente.get('totales_declarados', {})
    for hoja, pares in (
        ('F.VENTA', [('gravado', 'ingresos gravados', liq['ingresos_gravados']),
                     ('no_gravado', 'ingresos no gravados', liq['ingresos_no_gravados']),
                     ('iva', 'IVA generado', liq['iva_generado']),
                     ('reteiva', 'ReteIVA', liq['reteiva']),
                     ('base', 'base del anticipo', liq['ingresos_gravados'] + liq['ingresos_no_gravados'])]),
            ('F.COMPRA', [('iva', 'IVA descontable', liq['iva_descontable'])])):
        tot = declarados.get('ventas' if hoja == 'F.VENTA' else 'compras', {})
        for clave, etiqueta, calculado in pares:
            if clave not in tot or not tot[clave]:
                continue
            dif = calculado - tot[clave]
            v.append({
                'nombre': 'Total precalculado de %s — %s' % (hoja, etiqueta),
                'valor': dif, 'esperado': 0.0, 'formato': '$',
                'ok': abs(dif) <= TOL_PESOS, 'critica': True,
                'nota': 'El archivo trae $%s al pie de la hoja; el motor reconstruyó $%s.'
                        % (f'{tot[clave]:,.2f}'.replace(',', '.'),
                           f'{calculado:,.2f}'.replace(',', '.')),
            })
    return v


def alertas(liq, ficha, fuente):
    """Puntos que el contador debe revisar antes de presentar. Prioridad ALTA
    es lo que puede cambiar el valor a pagar o generar sanción."""
    a = []
    grupo = liq['grupo']
    if grupo != 2:
        alterno = P.tarifa(2, liq['base_uvt'])
        a.append({
            'prioridad': 'ALTA', 'tema': 'Grupo de actividad',
            'texto': 'La liquidación aplica el GRUPO %d (%s) con tarifa %.1f%%. '
                     'Confirma que el CIIU inscrito en el RUT lo respalde. Si '
                     'correspondiera el grupo 2 (%.1f%%), el anticipo sería $%s, y una '
                     'clasificación errada genera sanción por corrección e intereses.'
                     % (grupo, P.GRUPOS[grupo], liq['tarifa'] * 100, alterno * 100,
                        f'{rnd(liq["base"] * alterno):,.0f}'.replace(',', '.')),
        })
    proyeccion = liq['base_uvt'] * 6
    if proyeccion > P.TOPE_GRUPO3_UVT * 0.8:
        a.append({
            'prioridad': 'ALTA', 'tema': 'Cercanía al tope de %d UVT' % P.TOPE_GRUPO3_UVT,
            'texto': 'El bimestre da %.2f UVT. Proyectado a 6 bimestres son ~%.0f UVT '
                     'anuales, frente al tope de %d UVT ($%s). Si el año cierra por '
                     'encima, la tarifa anual sube de tramo y la declaración anual '
                     '(Form. 260) generará un mayor valor a pagar frente a los anticipos.'
                     % (liq['base_uvt'], proyeccion, P.TOPE_GRUPO3_UVT,
                        f'{P.TOPE_GRUPO3_UVT * liq["uvt"]:,.0f}'.replace(',', '.')),
        })
    # La diferencia relevante es la de cada agente frente a su certificado, no
    # el neto: los signos se compensan y esconden el problema.
    dif = sum(x['diferencia'] for x in fuente['reteiva'])
    if any(abs(x['diferencia']) > TOL_PESOS for x in fuente['reteiva']):
        mayores = sorted([x for x in fuente['reteiva'] if abs(x['diferencia']) > TOL_PESOS],
                         key=lambda x: -abs(x['diferencia']))[:4]
        detalle = '; '.join('%s (%s$%s)' % (x['tercero'].title(),
                                            '+' if x['diferencia'] > 0 else '−',
                                            f'{abs(x["diferencia"]):,.0f}'.replace(',', '.'))
                            for x in mayores)
        a.append({
            'prioridad': 'ALTA', 'tema': 'Diferencias en certificados de ReteIVA',
            'texto': 'Hay $%s de diferencia neta entre los certificados de los agentes '
                     'retenedores y lo contabilizado. Los casos mayores: %s. La DIAN cruza '
                     'contra el certificado, no contra tu contabilidad.'
                     % (f'{abs(dif):,.0f}'.replace(',', '.'), detalle or 'ver hoja 5'),
        })
    periodos = {p['periodo'] for p in liq['planillas']}
    if len(periodos) < 2:
        a.append({
            'prioridad': 'ALTA', 'tema': 'Completitud de las planillas de pensión',
            'texto': 'El archivo solo trae %s. La regla del Art. 903 Par. 4 ET es «pagado '
                     'en el bimestre»: la planilla del mes anterior al bimestre, si se pagó '
                     'dentro de él, también es descontable. Revísala y agrégala en las filas '
                     'amarillas de la hoja 7; la liquidación se recalcula sola.'
                     % (('la planilla de ' + ', '.join(sorted(periodos))) if periodos
                        else 'planillas incompletas'),
        })
    if liq['compras_gravadas']:
        nombres = ', '.join(sorted({c['proveedor'].title() for c in liq['compras_gravadas']})[:4])
        a.append({
            'prioridad': 'MEDIA', 'tema': 'Procedencia del IVA descontable',
            'texto': 'De las %d compras gravadas, verifica que todas cumplan el Art. 488 ET '
                     '(relación de causalidad con la actividad): %s. Un descontable '
                     'improcedente genera sanción por inexactitud.'
                     % (len(liq['compras_gravadas']), nombres),
        })
    combustible = [c for c in liq['compras_excluidas']
                   if 'eds' in c['proveedor'].lower() or 'combustible' in c['proveedor'].lower()
                   or 'estacion' in c['proveedor'].lower()]
    if combustible:
        a.append({
            'prioridad': 'MEDIA', 'tema': 'Combustible sin IVA descontable',
            'texto': 'Hay %d compras a estaciones de servicio registradas con IVA $0. En la '
                     'gasolina corriente el IVA está incorporado en la base; revisa si se '
                     'está perdiendo un descontable legítimo (Art. 488 ET).' % len(combustible),
        })
    if not ficha.get('dv') or not ficha.get('direccion_seccional'):
        a.append({
            'prioridad': 'ALTA', 'tema': 'DV y Dirección Seccional',
            'texto': 'Falta el dígito de verificación o el código de dirección seccional. '
                     'Tómalos del RUT antes de diligenciar el formulario.',
        })
    a.append({
        'prioridad': 'MEDIA', 'tema': 'Tarifa de ICA',
        'texto': 'Se usó la tarifa consolidada de %.4f (%s por mil) para %s. Confírmala '
                 'contra el Acuerdo municipal vigente para la actividad, incluyendo avisos '
                 'y tableros y sobretasa bomberil si aplican.'
                 % (liq['filas_ica'][0]['tarifa'], ('%g' % (liq['filas_ica'][0]['tarifa'] * 1000)),
                    liq['filas_ica'][0]['nombre'] or 'el municipio'),
    })
    if ficha.get('responsable_iva'):
        a.append({
            'prioridad': 'MEDIA', 'tema': 'Declaración anual de IVA',
            'texto': 'Al ser responsable de IVA en el SIMPLE, además de transferir el IVA en '
                     'cada recibo 2593 debes presentar la declaración ANUAL consolidada en el '
                     'Formulario 300 (Art. 915 ET).',
        })
    a.append({
        'prioridad': 'BAJA', 'tema': 'Firma del contador',
        'texto': 'Verifica si por patrimonio o ingresos brutos del año anterior se requiere '
                 'firma de contador público en la declaración anual (Form. 260).',
    })
    for aviso in fuente.get('avisos', []):
        a.append({'prioridad': 'MEDIA', 'tema': 'Lectura del archivo fuente', 'texto': aviso})
    if liq['facturas_fuera_periodo']:
        a.append({
            'prioridad': 'ALTA', 'tema': 'Facturas fuera del bimestre',
            'texto': 'El archivo trae %d facturas con fecha fuera de %s: quedaron excluidas '
                     'de esta liquidación. Verifica que correspondan a otro período.'
                     % (len(liq['facturas_fuera_periodo']), liq['nombre_bimestre'].lower()),
        })
    return a


def semaforo(liq):
    if any(not v['ok'] for v in liq['validaciones'] if v.get('critica')):
        return 'ROJO'
    if any(not v['ok'] for v in liq['validaciones']):
        return 'AMARILLO'
    if any(a['prioridad'] == 'ALTA' for a in liq['alertas']):
        return 'AMARILLO'
    return 'VERDE'
