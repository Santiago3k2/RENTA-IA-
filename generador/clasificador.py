# -*- coding: utf-8 -*-
"""Clasifica los registros de la exógena y aplica las reglas de depuración.

Señal principal: la columna «Uso declaración Sugerida» que la propia DIAN
incluye en el reporte. Señal secundaria: el texto del «Detalle». Cuando un
registro no encaja en ninguna regla NO se inventa un destino: queda como
«desconocido» y levanta una alerta ALTA para que el contador lo resuelva.
"""
import re
from collections import defaultdict

from parser_exogena import norm

UVT_POR_ANO = {
    '2020': 35607, '2021': 36308, '2022': 38004,
    '2023': 42412, '2024': 47065, '2025': 49799,
}

SUBGRUPO_PATRIMONIO = [
    (r'saldo cdt', 'cdt'),
    (r'saldo cuentas bancarias|saldo inversion en fondos|saldo en cuenta|'
     r'saldo final cuenta', 'cuentas'),
    (r'inversion, aporte o derecho social', 'inversiones'),
    (r'cuentas por cobrar|activos mandato|ingreso diferido premio|'
     r'programa fidelizacion', 'cuentas_cobrar'),
    (r'cesantias|aportes parafiscales', 'cesantias'),
    (r'avaluo catastral|base del impuesto predial', 'inmuebles'),
    (r'avaluo vehiculo', 'vehiculos'),
]


def tolerancia(tope):
    """Margen aceptable frente a un tope de la DIAN: unas decenas de pesos sobre
    miles de millones son redondeo, no una partida mal clasificada."""
    return max(10, abs(tope) * 1e-6)


def _tiene(u, renglon):
    return re.search(r'\b' + renglon + r'\b', u) is not None


def destinos(reg):
    """Lista de destinos de un registro. Vacía = no clasificado."""
    u, d = norm(reg.uso), norm(reg.detalle)

    # ── referencias (no son activos ni ingresos) ──
    if 'patrimonio bruto declarado en el ano anterior' in d:
        return ['ref_patrimonio_anterior']
    if 'saldo a favor' in d or _tiene(u, 'r131'):
        return ['ref_saldo_favor']
    if 'ingreso laboral promedio' in d:
        return ['ref_ingreso_promedio']
    if 'facturacion electronica susceptible' in d:
        return ['base_fe']
    # Recuperación de costos y deducciones (arts. 195 a 198 E.T.): el motor de
    # topes de la DIAN NO la suma al tope 1, así que no se computa como ingreso
    # corriente; puede constituir renta líquida especial y se alerta aparte.
    if 'recuperacion costos' in d or 'recuperacion de costos' in d:
        return ['ref_recuperacion']
    # Ventas registradas por el comprador vía «documento soporte»: la DIAN NO las
    # suma al tope 1, toma el MAYOR entre ese total y el de la exógena. Se dejan
    # como referencia y se alertan: pueden ser ingreso adicional a declarar.
    if 'documentos soporte' in d or 'documento soporte' in d:
        return ['ref_doc_soporte']

    out = []
    # ── topes y créditos ──
    if 'tope 3' in u or 'tarjeta credito o debito' in d:
        out.append('tope3')
    if 'tope 4' in u:
        out.append('tope4')
    if 'tope 5' in u or _tiene(u, 'r28') or 'facturas tras ajustes por notas' in d:
        out.append('tope5')
    if _tiene(u, 'r132') or 'retencion' in d:
        out.append('r132')

    # ── deudas ──
    if _tiene(u, 'r30') and 'si el saldo es negativo' not in u:
        out.append('r30')

    # ── ingresos por subcédula ──
    if _tiene(u, 'r32'):
        out.append('r32')
    if _tiene(u, 'r43'):
        out.append('r43')
    if _tiene(u, 'r58'):
        out.append('r58')
    if _tiene(u, 'r74'):
        out.append('r74')
    # Ingresos de mandato (concepto 4040) recaudados por administradores
    # inmobiliarios: la DIAN los sugiere en R74, pero el art. 338 E.T. incluye
    # expresamente los arrendamientos en las rentas de capital. Se reclasifican
    # a R58 solo cuando el mandatario es claramente inmobiliario; en los demás
    # casos se respeta la sugerencia y se levanta una alerta para revisarlo.
    if 'mandato' in d and 'r74' in out and re.search(
            r'inmobiliari|arrendamiento|propiedad horizontal|lonja', norm(reg.reportante)):
        out.remove('r74')
        out.append('r58')
    # Cesantías consignadas al fondo por el empleador: la columna sugerida de la
    # DIAN las marca solo como patrimonio, pero su propio motor de topes las
    # computa como ingreso — y el art. 27 num. 3 E.T. le da la razón: el ingreso
    # por auxilio de cesantías se realiza con el aporte al fondo. Se corrige.
    if 'cesantias consignadas al fondo' in d and 'r32' not in out:
        out.append('r32')

    es_ingreso = any(x in out for x in ('r32', 'r43', 'r58', 'r74'))
    if not es_ingreso and 'ingresos no constitutivos' in u:
        out.append('incrngo')

    # ── patrimonio ──
    if _tiene(u, 'r29') or (u.startswith('tope 2') and not out):
        out.append('r29')

    # ── respaldo por el texto del detalle ──
    # Los reportes de años anteriores traen la columna «Uso sugerido» vacía o
    # con otra redacción: aquí se clasifica por el detalle mismo.
    if not out:
        for patron, destino in RESPALDO_POR_DETALLE:
            if re.search(patron, d):
                out.append(destino)
                break

    return out


# (patrón sobre el detalle, destino) — se evalúa en orden, solo si «uso» no bastó
RESPALDO_POR_DETALLE = [
    (r'consumo tarjeta credito|consumos o gastos.*tarjeta|adquisiciones consumos', 'tope3'),
    (r'movimiento credito cuenta|movimientos en cuentas|inversion efectuada', 'tope4'),
    (r'facturas tras ajustes por notas', 'tope5'),
    (r'retencion', 'r132'),
    (r'cuentas por pagar|deuda a cargo', 'r30'),
    (r'saldo final cuenta|saldo cuentas bancarias|saldo cdt|saldo inversion', 'r29'),
    (r'cesantias acumuladas|aportes parafiscales', 'r29'),
    (r'inversion, aporte o derecho social', 'r29'),
    (r'avaluo catastral|base del impuesto predial|avaluo vehiculo', 'r29'),
    (r'cuentas por cobrar', 'r29'),
    (r'aportes? obligatorios?.*(salud|pension)', 'incrngo'),
    (r'pagos por salarios|prestaciones sociales|cesantias|honorarios|servicios|'
     r'otros pagos rentas de trabajo', 'r32'),
    (r'rendimientos|intereses', 'r58'),
    (r'ingresos recuperacion costos|revalorizacion de aportes', 'r74'),
]


def subgrupo(reg):
    d = norm(reg.detalle)
    for patron, g in SUBGRUPO_PATRIMONIO:
        if re.search(patron, d):
            return g
    return None


def _titulo(nombre):
    return ' '.join(w.capitalize() for w in str(nombre or '').split())


def procesar(parsed):
    """Aplica clasificación + depuración. Devuelve la estructura del caso."""
    regs = parsed['registros']
    ident = parsed['ident']
    topes = parsed['topes']
    avisos = []          # (severidad, hallazgo, detalle, accion)

    dest = {id(r): destinos(r) for r in regs}
    dep = {id(r): '' for r in regs}          # marca de depuración
    # La exclusión es POR BUCKET: una partida puede ser duplicada en patrimonio
    # y seguir siendo un ingreso válido — es el caso de las cesantías
    # consignadas al fondo, que la DIAN informa como R29 y R32 a la vez.
    excluido = defaultdict(set)
    dups = []

    # ── 1 · inmuebles concepto 1476: se toma el mayor por matrícula ──
    por_matricula = defaultdict(list)
    for r in regs:
        if 'r29' in dest[id(r)] and subgrupo(r) == 'inmuebles':
            por_matricula[r.matricula or f'sin-matricula-{r.fila}'].append(r)
    for lista in por_matricula.values():
        if len(lista) > 1:
            mayor = max(lista, key=lambda x: x.valor)
            for r in lista:
                dep[id(r)] = 'MAYOR VALOR'
                if r is not mayor:
                    excluido['r29'].add(id(r))

    # ── 2 · duplicadas: mismo NIT y mismo valor bajo detalles distintos ──
    for bucket in ('r29', 'r58', 'r32', 'r74', 'r30'):
        grupos = defaultdict(list)
        for r in regs:
            if id(r) in excluido[bucket] or bucket not in dest[id(r)]:
                continue
            grupos[(r.nit, round(r.valor, 2))].append(r)
        for lista in grupos.values():
            if len(lista) > 1 and len({norm(x.detalle) for x in lista}) > 1:
                # se conserva la partida con más destinos (la más informativa)
                lista.sort(key=lambda x: -len(dest[id(x)]))
                for r in lista:
                    dep[id(r)] = 'DUPLICADA'
                for r in lista[1:]:
                    excluido[bucket].add(id(r))
                    dups.append(r)

    # ── 3 · cesantías: prevalece el empleador sobre el fondo ──
    if any('cesantias consignadas al fondo' in norm(r.detalle) for r in regs):
        for r in regs:
            if 'cesantias abonadas' in norm(r.detalle):
                dep[id(r)] = 'FONDO — PREVALECE EMPLEADOR'
                for b in dest[id(r)]:
                    excluido[b].add(id(r))

    # ── 4 · titular secundario ──
    for r in regs:
        if r.secundario:
            dep[id(r)] = dep[id(r)] or 'TIT. SECUND.'

    def vivos(bucket):
        return [r for r in regs
                if bucket in dest[id(r)] and id(r) not in excluido[bucket]]

    # ═══════════ PATRIMONIO ═══════════
    grupos_pat = defaultdict(list)
    sin_grupo = []
    for r in vivos('r29'):
        g = subgrupo(r)
        if g:
            grupos_pat[g].append(r)
        else:
            grupos_pat['cuentas'].append(r)
            sin_grupo.append(r)

    cuentas = [(f'{r.reportante.title()} — {r.cuenta}' if r.cuenta else r.reportante.title(),
                r.tipo_cuenta or 'Cuenta de ahorros', int(round(r.valor)))
               for r in grupos_pat.get('cuentas', [])]
    cdt = [(f'{r.reportante.title()} — {r.cuenta}' if r.cuenta else r.reportante.title(),
            'TITULAR SECUNDARIO' if r.secundario else 'Titular principal',
            1.0, int(round(r.valor)), bool(r.secundario))
           for r in grupos_pat.get('cdt', [])]
    inversiones = [(r.reportante.title(), r.participacion or 1.0, int(round(r.valor)))
                   for r in grupos_pat.get('inversiones', [])]
    cxc = [(r.reportante.title(), _concepto(r), int(round(r.valor)))
           for r in grupos_pat.get('cuentas_cobrar', [])]
    cesantias = [(r.reportante.title(), 'FONDO POR CONFIRMAR', int(round(r.valor)))
                 for r in grupos_pat.get('cesantias', [])]
    # El avalúo del concepto 1476 es el del PREDIO COMPLETO: cuando hay
    # copropiedad, al contribuyente solo le corresponde su porcentaje. Es la
    # única familia de activos donde el porcentaje se aplica — en inversiones y
    # aportes el valor informado ya es el suyo.
    inmuebles = [(r.matricula or 'por confirmar', r.participacion or 1.0, int(round(r.valor)))
                 for r in grupos_pat.get('inmuebles', [])]
    vehiculos = [(r.placa or r.cuenta or 'por confirmar', r.reportante.title(), int(round(r.valor)))
                 for r in grupos_pat.get('vehiculos', [])]
    pasivos = [(r.reportante.title(), _concepto(r), int(round(r.valor))) for r in vivos('r30')]

    # ═══════════ INGRESOS ═══════════
    def partidas(bucket):
        return [(r.reportante.title(), _concepto(r), int(round(r.valor))) for r in vivos(bucket)]

    r43 = vivos('r43')
    rentas_trabajo = partidas('r32') + [
        (r.reportante.title(),
         _concepto(r) + ' — R43: sujeto a costos y gastos, SIN renta exenta del 25%',
         int(round(r.valor))) for r in r43]
    base_25_excluir = int(sum(r.valor for r in r43))
    idx_cesantias = [i for i, (_, c, _) in enumerate(rentas_trabajo)
                     if 'cesantia' in norm(c)]
    incrngo = partidas('incrngo')
    rentas_capital = partidas('r58')
    rentas_no_laborales = partidas('r74')

    # ═══════════ RETENCIONES agrupadas por concepto ═══════════
    grupos_ret = defaultdict(list)
    for r in vivos('r132'):
        clave = f'{r.reportante.title()} · {r.cuenta or _concepto(r)}'
        grupos_ret[clave].append(r)
    retenciones = [(k, [(r.reportante.title(), r.cuenta or _concepto(r), int(round(r.valor)))
                        for r in v]) for k, v in grupos_ret.items()]

    # ═══════════ TOPES ═══════════
    movimientos, movimientos_excl = [], []
    for r in vivos('tope4'):
        fila = (r.reportante.title(), r.cuenta or '', _tipo_mov(r), int(round(r.valor)))
        excluye = r.secundario or 'inversiones en fondos de inversion colectiva realizadas' in norm(r.detalle)
        (movimientos_excl if excluye else movimientos).append(fila)
    consumos = [(f'{r.reportante.title()} — {r.cuenta or "tarjeta"}', int(round(r.valor)))
                for r in vivos('tope3')]
    compras = int(sum(r.valor for r in vivos('tope5')))
    base_fe = int(sum(r.valor for r in vivos('base_fe')))
    pat_anterior = int(sum(r.valor for r in vivos('ref_patrimonio_anterior')))
    saldo_favor = int(sum(r.valor for r in vivos('ref_saldo_favor')))

    # ═══════════ VALIDACIÓN CONTRA LOS TOPES DE LA DIAN ═══════════
    ingresos = sum(v for _, _, v in rentas_trabajo) + \
        sum(v for _, _, v in rentas_capital) + sum(v for _, _, v in rentas_no_laborales)
    pat_bruto = (sum(v for _, _, v in cuentas) + sum(int(round(v * p)) for _, _, p, v, _ in cdt)
                 + sum(v for _, _, v in inversiones) + sum(v for _, _, v in cxc)
                 + sum(v for _, _, v in cesantias)
                 + sum(int(v * p) for _, p, v in inmuebles)
                 + sum(v for _, _, v in vehiculos))

    mios = {'ingresos': ingresos,
            'consumos': sum(v for _, v in consumos),
            'movimientos': sum(v for _, _, _, v in movimientos),
            'compras': compras}
    # El tope 2 es el MAYOR entre lo reconstruido de la exógena y el patrimonio
    # declarado el año anterior. Solo se puede validar la composición cuando el
    # tope viene de la exógena, es decir cuando supera al del año anterior.
    if topes.get('patrimonio') and topes['patrimonio'] > pat_anterior:
        mios['patrimonio'] = pat_bruto
    difs = {k: mios[k] - topes[k] for k in mios if topes.get(k)}
    descuadres = {k: v for k, v in difs.items() if abs(v) > tolerancia(topes[k])}

    # ═══════════ ALERTAS AUTOMÁTICAS ═══════════
    sin_clasificar = [r for r in regs if not dest[id(r)]]
    if sin_clasificar:
        avisos.append(('ALTA', f'{len(sin_clasificar)} registro(s) que el clasificador no pudo asignar',
                       ' · '.join(f'{r.reportante}: {r.detalle} (${r.valor:,.0f})'.replace(',', '.')
                                  for r in sin_clasificar[:4]),
                       'Clasificar a mano en el datos.py del cliente y añadir la regla al clasificador para los próximos casos.'))
    for k, v in descuadres.items():
        avisos.append(('ALTA', f'El tope de {k} no reconstruye el precalculado por la DIAN',
                       f'Reconstruido {mios[k]:,.0f} frente a {topes[k]:,.0f} de la DIAN: diferencia de {v:,.0f}.'.replace(',', '.'),
                       'Hay una partida mal clasificada o faltante. NO liberar el caso hasta cuadrarlo.'))
    secundarios = [r for r in regs if r.secundario]
    if secundarios:
        tot = sum(r.valor for r in secundarios if 'r29' in dest[id(r)])
        avisos.append(('ALTA', 'Partidas informadas en calidad de TITULAR SECUNDARIO',
                       f'{len(secundarios)} registro(s); {tot:,.0f} afectan el patrimonio bruto.'.replace(',', '.'),
                       'Solicitar a la entidad la certificación de titularidad y ajustar el porcentaje de participación en la hoja «2. Patrimonio».'))
    delta = pat_bruto - pat_anterior
    if pat_anterior and abs(delta) > 1000:
        base = (f'Patrimonio bruto reconstruido {pat_bruto:,.0f}; declarado el año anterior '
                f'{pat_anterior:,.0f}.').replace(',', '.')
        if delta > 0:
            # incremento: se compara contra la renta que puede respaldarlo
            respaldo = ingresos
            sin_justificar = delta - respaldo
            avisos.append((
                'ALTA' if sin_justificar > 0 else 'MEDIA',
                f'Incremento patrimonial de {delta:,.0f} frente al año anterior'.replace(',', '.'),
                base + (f' El incremento supera en {sin_justificar:,.0f} los ingresos del período '
                        f'({respaldo:,.0f}), sin contar los consumos.'.replace(',', '.')
                        if sin_justificar > 0 else
                        f' Los ingresos del período ({respaldo:,.0f}) lo respaldan.'.replace(',', '.')),
                'Art. 236 E.T. — si el incremento supera la renta gravable más los ingresos no constitutivos y las ganancias ocasionales, la diferencia es renta líquida gravable especial. La causa más frecuente y NO gravada es la valorización de los avalúos catastrales (art. 239 E.T.): documentarla antes de presentar.'))
        else:
            avisos.append(('ALTA', f'Disminución patrimonial de {abs(delta):,.0f} frente al año anterior'.replace(',', '.'),
                           base,
                           'Explicar antes de presentar: activos que no viajan por exógena (efectivo, muebles y enseres, préstamos a terceros), o enajenaciones que generarían ganancia ocasional. Una disminución sin soporte es foco de fiscalización.'))
    nits_ingreso = {r.nit for r in regs if any(x in dest[id(r)] for x in ('r32', 'r43', 'r58', 'r74'))}
    huerfanas = {r.reportante for r in vivos('r132') if r.nit not in nits_ingreso}
    if huerfanas:
        avisos.append(('ALTA', 'Retenciones sin el ingreso correlativo en la exógena',
                       'Agentes con retención pero sin ingreso reportado: ' + ', '.join(sorted(huerfanas)) + '.',
                       'Pedir el certificado de rendimientos o de ingresos y retenciones: declarar la retención sin su ingreso es una inconsistencia que la DIAN detecta automáticamente.'))
    if sin_grupo:
        avisos.append(('MEDIA', 'Activos de patrimonio sin grupo definido',
                       ' · '.join(f'{r.detalle} (${r.valor:,.0f})'.replace(',', '.') for r in sin_grupo[:4]),
                       'Se ubicaron provisionalmente en el grupo B (cuentas bancarias). Reubicarlos en el grupo correcto si procede.'))
    reclas = [r for r in regs if 'mandato' in norm(r.detalle) and 'r58' in dest[id(r)]]
    if reclas:
        avisos.append(('NORMATIVO', 'Arrendamientos vía mandato reclasificados de R74 a R58',
                       f'{len(reclas)} partida(s) por {sum(x.valor for x in reclas):,.0f}. La DIAN los sugiere en rentas no laborales, pero el art. 338 E.T. incluye expresamente los arrendamientos en las rentas de capital, y los mandatarios son administradores inmobiliarios.'.replace(',', '.'),
                       'Efecto fiscal nulo: ambas subcédulas integran la cédula general, admiten costos (art. 339 E.T.) y tributan con la misma tarifa del art. 241. Revertir en el datos.py si el mandato no era de arrendamiento.'))
    mandato_dudoso = [r for r in regs if 'mandato' in norm(r.detalle) and 'r74' in dest[id(r)]]
    if mandato_dudoso:
        avisos.append(('MEDIA', 'Ingresos de mandato que podrían ser arrendamientos',
                       ' · '.join(f'{r.reportante}: ${r.valor:,.0f}'.replace(',', '.') for r in mandato_dudoso[:4]),
                       'Quedaron en R74 según la sugerencia de la DIAN. Si el mandato es de arrendamiento, van a R58 (art. 338 E.T.): moverlos en el datos.py del cliente.'))
    copro = [(m, p, v) for m, p, v in inmuebles if p < 1]
    if copro:
        avisos.append(('NORMATIVO', 'Inmuebles en copropiedad: se aplicó el porcentaje de participación',
                       ' · '.join(f'matrícula {m}: {p * 100:.2f}% de ${v:,.0f}'.replace(',', '.')
                                  for m, p, v in copro),
                       'El avalúo del concepto 1476 es el del predio completo; al contribuyente solo le corresponde su cuota parte. Confirmar el porcentaje con la escritura o el certificado de tradición.'))
    docsop = vivos('ref_doc_soporte')
    if docsop:
        avisos.append(('MEDIA', 'Ventas registradas por «documento soporte»',
                       ' · '.join(f'{r.reportante}: ${r.valor:,.0f}'.replace(',', '.') for r in docsop)
                       + f'. Total {sum(r.valor for r in docsop):,.0f}.'.replace(',', '.'),
                       'La DIAN no las suma al tope 1 —toma el mayor entre ese total y el de la exógena— así que quedaron fuera del ingreso. Si el pagador es distinto de los ya reportados, es ingreso adicional que debe declararse: confirmarlo con el contribuyente.'))
    recup = vivos('ref_recuperacion')
    if recup:
        avisos.append(('MEDIA', 'Ingresos por recuperación de costos y deducciones',
                       ' · '.join(f'{r.reportante}: ${r.valor:,.0f}'.replace(',', '.') for r in recup)
                       + f'. Total {sum(r.valor for r in recup):,.0f}.'.replace(',', '.'),
                       'El motor de topes de la DIAN no los suma al tope 1, así que quedaron fuera del ingreso corriente. Los arts. 195 a 198 E.T. pueden hacerlos renta líquida por recuperación de deducciones: evaluar si en años anteriores se dedujo el costo que ahora se recupera.'))
    if not retenciones:
        avisos.append(('MEDIA', 'No hay ninguna retención informada en la exógena',
                       'El renglón R132 quedaría en cero.',
                       'Revisar los certificados de retención del contribuyente: cada peso no declarado es saldo a favor perdido.'))
    if dups:
        avisos.append(('VERIFICADO', f'{len(dups)} partida(s) duplicada(s), eliminadas del cómputo',
                       ' · '.join(f'{r.reportante}: {r.detalle} (${r.valor:,.0f})'.replace(',', '.') for r in dups[:4]),
                       'Misma partida informada bajo dos formatos por el mismo NIT y el mismo valor: se computa una sola vez.'))
    if difs and not descuadres:
        avisos.append(('VERIFICADO', 'Los topes de la DIAN se reconstruyen correctamente',
                       ' · '.join(f'{k}: diferencia {v:+,.0f}'.replace(',', '.') for k, v in difs.items()),
                       'La clasificación queda validada contra el motor de cálculo de la propia DIAN.'))

    ano = ident['ano'] or ''
    uvt = UVT_POR_ANO.get(ano)
    if not uvt:
        avisos.append(('ALTA', f'No se conoce la UVT del año gravable {ano}',
                       'El generador la dejó en 0 y toda la liquidación quedará mal.',
                       'Escribir la UVT del año en el campo «uvt» del datos.py y añadirla a UVT_POR_ANO en clasificador.py.'))
    primera = not pat_anterior and not saldo_favor

    detalle_exogena = []
    for r in regs:
        detalle_exogena.append((r.nit, r.reportante, r.detalle, r.valor,
                                _etiqueta(dest[id(r)]), dep[id(r)]))

    return {
        'ident': ident, 'topes': topes, 'uvt': uvt or 0,
        'mios': mios, 'difs': difs, 'descuadres': descuadres,
        'avisos': avisos, 'primera_declaracion': primera,
        'pat_anterior': pat_anterior, 'saldo_favor': saldo_favor,
        'pat_bruto': pat_bruto,
        'cuentas': cuentas, 'cdt': cdt, 'inversiones': inversiones,
        'cuentas_cobrar': cxc, 'cesantias': cesantias, 'inmuebles': inmuebles,
        'vehiculos': vehiculos, 'pasivos': pasivos,
        'rentas_trabajo': rentas_trabajo, 'indices_cesantias_exentas': idx_cesantias,
        'incrngo_trabajo': incrngo, 'rentas_capital': rentas_capital,
        'rentas_no_laborales': rentas_no_laborales, 'base_25_excluir': base_25_excluir,
        'retenciones': retenciones, 'movimientos': movimientos,
        'movimientos_excluidos': movimientos_excl, 'consumos_tarjeta': consumos,
        'compras_fe': compras, 'base_fe': base_fe,
        'detalle_exogena': detalle_exogena,
        'n_registros': len(regs),
    }


def _concepto(r):
    """Concepto legible: código tributario + descripción corta del detalle."""
    m = re.search(r'concepto:\s*(\d+)', norm(r.detalle))
    base = re.sub(r'\s*\(concepto:\s*\d+\)', '', r.detalle).strip()
    base = re.sub(r'^Certificado\s*-\s*', '', base).strip()
    return f'{m.group(1)} · {base}' if m else base


def _tipo_mov(r):
    d = norm(r.detalle)
    if 'inversion efectuada' in d or 'inversiones en fondos' in d:
        return 'CDT · inversión efectuada' if 'cdt' in d else 'Inversión en fondo colectivo'
    return r.tipo_cuenta or 'Movimiento en cuenta'


ETIQUETAS = {
    'r29': 'R29 · Patrimonio bruto', 'r30': 'R30 · Deudas',
    'r32': 'R32 · Rentas de trabajo', 'r43': 'R43 · Honorarios sujetos a costos',
    'r58': 'R58 · Rentas de capital', 'r74': 'R74 · Rentas no laborales',
    'incrngo': 'R33 · INCRNGO', 'r132': 'R132 · Retenciones',
    'tope3': 'Tope 3 · Consumos con tarjeta', 'tope4': 'Tope 4 · Consignaciones',
    'tope5': 'Tope 5 · Compras', 'base_fe': 'Base deducción 1% (art. 336 par. 5)',
    'ref_patrimonio_anterior': 'Referencia — patrimonio año anterior',
    'ref_saldo_favor': 'R131 · Saldo a favor año anterior',
    'ref_ingreso_promedio': 'Referencia — insumo art. 206 num. 4',
    'ref_recuperacion': 'Referencia — recuperación de costos (arts. 195-198 E.T.)',
    'ref_doc_soporte': 'Referencia — ventas por documento soporte',
}


def _etiqueta(destinos_lista):
    if not destinos_lista:
        return 'SIN CLASIFICAR'
    return ' + '.join(ETIQUETAS.get(d, d) for d in destinos_lista)

