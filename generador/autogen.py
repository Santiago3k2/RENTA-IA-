# -*- coding: utf-8 -*-
r"""Tubería completa: exógena .xlsx → datos.py → libro de 9 hojas.

    python autogen.py "ruta\reporteExogena.xlsx"

Crea clientes\<Nombre>\ con el datos.py generado y el libro, y deja el caso
listo en la bandeja. Si la clasificación no reconstruye los topes de la DIAN,
el caso queda marcado en ROJO y no debe liberarse.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(BASE)
sys.path.insert(0, BASE)

import parser_exogena
import clasificador


def _sinacento(t):
    t = unicodedata.normalize('NFD', str(t or ''))
    return ''.join(c for c in t if unicodedata.category(c) != 'Mn')


def _titulo(nombre):
    return ' '.join(w.capitalize() for w in str(nombre or '').split())


def _carpeta(nombre):
    limpio = re.sub(r'[^A-Za-z0-9 ]', '', _sinacento(_titulo(nombre)))
    return re.sub(r'\s+', ' ', limpio).strip() or 'Cliente'


def _py(v, ind=0):
    """Serializa listas de tuplas de forma legible."""
    if isinstance(v, list):
        if not v:
            return '[]'
        filas = ',\n'.join(' ' * (ind + 4) + _py(x, ind + 4) for x in v)
        return '[\n' + filas + ',\n' + ' ' * ind + ']'
    if isinstance(v, tuple):
        return '(' + ', '.join(_py(x, ind) for x in v) + ')'
    if isinstance(v, float) and v.is_integer():
        return repr(int(v)) if abs(v) >= 1 else repr(v)
    return repr(v)


PLANTILLA = '''# -*- coding: utf-8 -*-
r"""
DATOS DEL CLIENTE — {nombre_titulo} · AG {ano}
GENERADO AUTOMÁTICAMENTE por autogen.py desde: {fuente_archivo}

Revise antes de liberar. Los campos marcados «POR CONFIRMAR» y las alertas de
la hoja 7 requieren decisión del contador. Editar este archivo y volver a correr
    python generar.py --datos "<esta ruta>"
regenera el libro con los cambios.

Validación contra los topes precalculados por la DIAN:
{resumen_topes}
"""

CLIENTE = {{
    # ─────────── 1 · IDENTIFICACIÓN ───────────
    'nombre':          {nombre!r},
    'nombre_titulo':   {nombre_titulo!r},
    'nombre_archivo':  {nombre_archivo!r},
    'identificacion':  {identificacion!r},
    'ultimos_digitos': {ultimos!r},
    'ano_gravable':    {ano!r},
    'ano_siguiente':   {ano_sig!r},
    'ano_anterior':    {ano_ant!r},
    'uvt':             {uvt},
    'fuente':          {fuente!r},
    'registros':       {n_registros},

    'topes_dian': {topes_dian},
    'base_25_excluir': {base_25_excluir},

    # ─────────── 2 · DECLARACIÓN ANTERIOR ───────────
    # Solo el patrimonio y el saldo a favor vienen por exógena. El impuesto neto
    # y el anticipo del año anterior se toman de esa declaración: si están en 0,
    # quedan como casillas editables en el libro.
    'patrimonio_bruto_anterior': {pat_anterior},
    'saldo_favor_anterior':      {saldo_favor},
    'anticipo_previo':           0,
    'impuesto_neto_anterior':    0,
    'porcentaje_anticipo':       {pct_anticipo},

    # ─────────── 3 · PATRIMONIO ───────────
    'efectivo': ['Efectivo en caja', 'Efectivo en caja menor'],
    'cuentas': {cuentas},
    'cdt': {cdt},
    'inversiones': {inversiones},
    'cuentas_cobrar': {cuentas_cobrar},
    'cuentas_cobrar_filas_libres': 1,
    'cesantias': {cesantias},
    'inmuebles': {inmuebles},
    'inmuebles_filas_libres': 2,
    'vehiculos': {vehiculos},
    'pasivos': {pasivos},

    # ─────────── 4 · INGRESOS ───────────
    'rentas_trabajo': {rentas_trabajo},
    'indices_cesantias_exentas': {idx_cesantias},
    'incrngo_trabajo': {incrngo_trabajo},
    'rentas_capital': {rentas_capital},
    'rentas_no_laborales': {rentas_no_laborales},

    # ─────────── 5 · RETENCIONES ───────────
    'retenciones': {retenciones},
    'retenciones_esperadas': [],

    # ─────────── 6 · CONSIGNACIONES Y TOPES ───────────
    'movimientos': {movimientos},
    'movimientos_excluidos': {movimientos_excluidos},
    'consumos_tarjeta': {consumos_tarjeta},
    'compras_fe': {compras_fe},
    'base_fe': {base_fe},

    # ─────────── 7 · ALERTAS (generadas por el clasificador) ───────────
    'alertas': {alertas},

    # ─────────── 8 · DETALLE DE LA EXÓGENA ───────────
    'detalle_exogena': {detalle_exogena},
}}


TEXTOS = {{
    'sub_resumen': {sub_resumen!r},
    'sub_patrimonio': 'Activos agrupados de mayor a menor liquidez. Cada grupo separa lo que informó la exógena de lo que debe diligenciarse con el certificado de la entidad, deja espacio para el ajuste fiscal y termina en el valor patrimonial que se lleva al formulario. Cierra con la conciliación patrimonial frente al año anterior.',
    'sub_ingresos': 'Los ingresos del período distribuidos por subcédula. Cada partida enfrenta lo REPORTADO en el prevalidador de la DIAN contra lo CERTIFICADO por el tercero, y muestra la diferencia. Cada subcédula cierra con sus ingresos no constitutivos, sus costos y el tope del 60% que los costos no deben superar.',
    'sub_retenciones': {sub_retenciones!r},
    'sub_anticipo': 'El artículo 807 E.T. permite calcular el anticipo por dos métodos y optar por el que arroje el MENOR valor. El porcentaje es del 25% el primer año de declaración, 50% el segundo y 75% del tercero en adelante.',
    'sub_alertas': 'Generadas por el clasificador automático y ordenadas por impacto. Las de severidad ALTA deben resolverse antes de liberar el caso.',
    'sub_consignaciones': {sub_consignaciones!r},
    'sub_detalle': {sub_detalle!r},

    'nota_cuentas': 'NOTA 2 — «Valor real» es el saldo que certifica la entidad y «Valor patrimonial» el que se declara. Las cuentas que se movieron pero no reportaron saldo quedan abiertas para diligenciarlas con el extracto a 31-dic.',
    'nota_cdt': 'NOTA 3 — «Valor real» es el saldo que emite la entidad y «Valor patrimonial» el declarado en el prevalidador MUISCA: Valor real × Porcentaje + Ajuste fiscal.',
    'nota_inversiones': 'NOTA 4 — El costo fiscal queda en blanco hasta tener el certificado de cada sociedad. El valor patrimonial muestra el declarado en el prevalidador MUISCA mientras las casillas estén vacías.',
    'nota_cxc': 'NOTA 5 — Deudor, concepto y valor reportado en el prevalidador MUISCA. La última fila queda abierta para cuentas por cobrar que no viajan por exógena.',
    'nota_cesantias': 'NOTA 6 — Diligencie el fondo y el saldo del año anterior con el certificado. El valor patrimonial es la suma del saldo anterior y lo consignado en el período.',
    'nota_pasivos': 'NOTA 9 — Art. 283 E.T.: los pasivos deben estar respaldados con documentos de fecha cierta. Diligencie la columna «Certificado» con el extracto de cada acreedor.',
    'callout_brecha': ('DIFERENCIA PATRIMONIAL POR EXPLICAR',
        {texto_brecha!r}),

    'nota_trabajo': 'NOTA 11 — «Reportado» es lo que informó el tercero en el prevalidador. Si el certificado difiere, declare el mayor valor y ajuste la casilla «Ingreso».',
    'nota_capital': '',
    'callout_reclasificacion': {callout_reclas},
    'nota_r36': 'Cesantías e intereses exentos del art. 206 num. 4. Verificar el umbral de 350 UVT de ingreso mensual promedio con el certificado del empleador.',

    'nota_retencion': 'Al diligenciar el formulario, el total se redondea al múltiplo de mil más cercano (art. 577 E.T.).',
    'nota_esperadas': '',

    'nota_x_anticipo': 'El dato X se toma de la declaración del año anterior y se diligencia en la primera columna de la tabla siguiente: decide qué método del art. 807 E.T. conviene.',
    'nota_tabla_anticipo': 'El método 2 es más favorable siempre que el impuesto neto del año anterior haya sido inferior al de este año. La columna de saldo a pagar aún no descuenta el anticipo liquidado en la declaración anterior.',
    'nota_saldo_anticipo': 'No disponible en la exógena: se obtiene de la declaración del año anterior.',
    'callout_rango': ('RANGO DE RESULTADOS',
        'El saldo a pagar depende del método de anticipo elegido y del impuesto neto del año anterior. Conseguir esa declaración es la tarea de mayor impacto económico pendiente.'),

    'sensibilidad': '',

    'nota_tope4': {nota_tope4!r},
    'callout_cruce': ('LECTURA DEL CRUCE: MOVIMIENTOS FRENTE A INGRESOS',
        {texto_cruce!r}),
    'label_consumos_total': 'Total consumos con tarjeta',

    'callout_prioridad': ('PRIORIDAD DE GESTIÓN',
        {texto_prioridad!r}),

    'como_leer': 'La columna «Valor» es el dato en BRUTO tal como lo reportó el tercero: sumarla NO da los totales de las hojas anteriores, porque todavía incluye las partidas depuradas. La columna «Depuración» señala por qué: MAYOR VALOR = pareja avalúo catastral / base predial del mismo inmueble; DUPLICADA = misma partida bajo dos formatos, computada una sola vez; TIT. SECUND. = el contribuyente figura como titular secundario.',

    'validacion_cruzada': {validacion!r},
    'kpi_ingresos_foot': 'Trabajo, capital y no laborales',
    'kpi_impuesto_foot': 'Tabla del art. 241 E.T.',
    'plazo_grande': {plazo!r},
}}
'''


def _pesos(v):
    return f'$ {int(round(v)):,}'.replace(',', '.')


def construir_datos_py(caso, fuente_archivo):
    ident = caso['ident']
    nombre = ident['nombre'] or 'CONTRIBUYENTE'
    ano = ident['ano'] or ''
    ano_i = int(ano) if ano.isdigit() else 0
    ident_txt = f"{ident['tipo_doc'].replace('. ', '.').strip()} {int(ident['identificacion']):,}".replace(',', '.') \
        if (ident['identificacion'] or '').isdigit() else str(ident['identificacion'])

    lineas = []
    for k, v in caso['difs'].items():
        estado = 'exacto' if v == 0 else (f'{v:+,.0f} (redondeo)'.replace(',', '.') if abs(v) <= clasificador.tolerancia(caso['topes'][k])
                                          else f'{v:+,.0f}  ← DESCUADRE'.replace(',', '.'))
        lineas.append(f'    {k:12} DIAN {caso["topes"][k]:>15,.0f}   reconstruido {caso["mios"][k]:>15,.0f}   {estado}'.replace(',', '.'))
    resumen = '\n'.join(lineas) or '    (el reporte no trae topes precalculados)'

    n_altas = sum(1 for a in caso['avisos'] if a[0] == 'ALTA')
    alertas = [(f'A{i + 1}', sev, hall, det, acc)
               for i, (sev, hall, det, acc) in enumerate(caso['avisos'])]

    reclas = ("('HONORARIOS SUJETOS A COSTOS (R43)',\n        'La DIAN clasificó parte de los ingresos en la subcédula de honorarios y compensación de servicios personales sujetos a costos y gastos (R43). La consecuencia es doble: pueden restarse costos con soporte contra ese ingreso, pero se pierde la renta exenta del 25% sobre esa porción (num. 10, art. 206 E.T.). Este libro ya lo excluye de la base del 25%.')"
              if caso['base_25_excluir'] else "('', '')")

    txt = PLANTILLA.format(
        nombre=nombre, nombre_titulo=_titulo(nombre), nombre_archivo=_carpeta(nombre),
        identificacion=ident_txt,
        ultimos=(ident['identificacion'] or '')[-2:],
        ano=ano, ano_sig=str(ano_i + 1) if ano_i else '', ano_ant=str(ano_i - 1) if ano_i else '',
        uvt=caso['uvt'],
        fuente=f'Exógena DIAN · corte {ident["fecha_corte"]:%d-%b-%Y}' if ident['fecha_corte'] else 'Exógena DIAN',
        fuente_archivo=os.path.basename(fuente_archivo),
        n_registros=caso['n_registros'], resumen_topes=resumen,
        topes_dian=_py(caso['topes'], 4).replace("'", "'"),
        base_25_excluir=caso['base_25_excluir'],
        pat_anterior=caso['pat_anterior'], saldo_favor=caso['saldo_favor'],
        pct_anticipo=0.25 if caso['primera_declaracion'] else 0.75,
        cuentas=_py(caso['cuentas'], 4), cdt=_py(caso['cdt'], 4),
        inversiones=_py(caso['inversiones'], 4), cuentas_cobrar=_py(caso['cuentas_cobrar'], 4),
        cesantias=_py(caso['cesantias'], 4), inmuebles=_py(caso['inmuebles'], 4),
        vehiculos=_py(caso['vehiculos'], 4), pasivos=_py(caso['pasivos'], 4),
        rentas_trabajo=_py(caso['rentas_trabajo'], 4),
        idx_cesantias=_py(caso['indices_cesantias_exentas'], 4),
        incrngo_trabajo=_py(caso['incrngo_trabajo'], 4),
        rentas_capital=_py(caso['rentas_capital'], 4),
        rentas_no_laborales=_py(caso['rentas_no_laborales'], 4),
        retenciones=_py(caso['retenciones'], 4),
        movimientos=_py(caso['movimientos'], 4),
        movimientos_excluidos=_py(caso['movimientos_excluidos'], 4),
        consumos_tarjeta=_py(caso['consumos_tarjeta'], 4),
        compras_fe=caso['compras_fe'], base_fe=caso['base_fe'],
        alertas=_py(alertas, 4), detalle_exogena=_py(caso['detalle_exogena'], 4),
        sub_resumen=f'Clasificación automática de los {caso["n_registros"]} registros del reporte de exógena, con la depuración separada por cédula, la liquidación del impuesto y el anticipo. Las casillas de fondo crema son editables y el libro entero se recalcula con ellas.',
        sub_retenciones=(f'{sum(len(v) for _, v in caso["retenciones"])} certificado(s) de retención agrupados por concepto.'
                         if caso['retenciones'] else 'La exógena no informa ninguna retención: el renglón R132 queda en cero. Revisar los certificados del contribuyente antes de cerrarlo.'),
        sub_consignaciones=f'{len(caso["movimientos"]) + len(caso["movimientos_excluidos"])} movimiento(s) informado(s). No se llevan a ningún renglón del formulario —no son ingreso— pero determinan la obligación de declarar y son el primer cruce que hace la DIAN contra los ingresos denunciados.',
        sub_detalle=f'Los {caso["n_registros"]} registros originales del reporte con la clasificación asignada a cada uno. Permite auditar cualquier cifra de las hojas anteriores hasta su fuente.',
        texto_brecha=(f'El patrimonio bruto reconstruido desde la exógena es de {_pesos(caso["pat_bruto"])} frente a {_pesos(caso["pat_anterior"])} declarados el año anterior. La diferencia debe explicarse antes de presentar: activos que no llegan por exógena (efectivo, muebles y enseres, préstamos a terceros, criptoactivos, inmuebles en otros municipios), o enajenaciones ocurridas durante el año que generarían ganancia ocasional. Diligencie los grupos con los certificados y la diferencia se irá cerrando sola.'
                      if caso['pat_anterior'] else
                      f'La exógena no informa patrimonio del año anterior. El patrimonio bruto reconstruido es de {_pesos(caso["pat_bruto"])}: complete los grupos con los certificados del contribuyente, porque la exógena rara vez reporta el efectivo, los muebles y enseres o los activos en entidades que no informan.'),
        callout_reclas=reclas,
        nota_tope4=(f'El subtotal computable reconstruye el tope 4 precalculado por la DIAN con una diferencia de {caso["difs"].get("movimientos", 0):+,.0f}.'.replace(',', '.')
                    if 'movimientos' in caso['difs'] else 'Movimientos informados por las entidades financieras.'),
        texto_cruce=f'Se movieron {_pesos(caso["mios"]["movimientos"])} contra ingresos brutos de {_pesos(caso["mios"]["ingresos"])}. Una diferencia grande es normal —traslados entre cuentas propias, renovación de CDT, recaudos que luego se giran— pero es exactamente el indicador que activa un requerimiento. Conviene dejar preparada la conciliación con los extractos de todas las cuentas.',
        texto_prioridad=(f'{n_altas} alerta(s) de severidad ALTA concentran el riesgo: resuélvalas antes de diligenciar el formulario para no tener que corregir la declaración.'
                         if n_altas else 'Sin alertas de severidad alta: la clasificación reconstruye los topes de la DIAN y no hay partidas sin resolver. Revisar de todos modos las casillas crema antes de presentar.'),
        validacion=('Los totales reconstruidos coinciden con los topes precalculados por la DIAN dentro del margen de redondeo: '
                    + ' · '.join(f'{k} {caso["mios"][k]:,.0f} frente a {caso["topes"][k]:,.0f}'.replace(',', '.') for k in caso['difs'])
                    + '. Esto confirma que la asignación de cada partida a su subcédula es correcta.'
                    ) if caso['difs'] and not caso['descuadres'] else
        ('ATENCIÓN: los totales reconstruidos NO coinciden con los topes de la DIAN — ' +
         ' · '.join(f'{k}: diferencia {v:+,.0f}'.replace(',', '.') for k, v in caso['descuadres'].items()) +
         '. Hay una partida mal clasificada: no libere el caso hasta cuadrarlo.'),
        plazo=f'SE PRESENTA ENTRE AGOSTO Y OCTUBRE DE {ano_i + 1}' if ano_i else 'CONSULTE EL DECRETO DE PLAZOS',
    )
    return txt, _carpeta(nombre)


def procesar_archivo(ruta_xlsx, salida_base=None):
    parsed = parser_exogena.leer(ruta_xlsx)
    caso = clasificador.procesar(parsed)
    txt, carpeta = construir_datos_py(caso, ruta_xlsx)

    # Una carpeta por contribuyente y una subcarpeta por año gravable:
    #     clientes\<Nombre>\AG2025\
    # Así los años de una misma persona quedan juntos y no se pisan entre sí.
    ano = caso['ident']['ano'] or 'SA'
    destino = salida_base or os.path.join(RAIZ, 'clientes', carpeta, f'AG{ano}')
    os.makedirs(destino, exist_ok=True)
    dpath = os.path.join(destino, 'datos.py')
    with open(dpath, 'w', encoding='utf-8') as f:
        f.write(txt)
    # copia del archivo fuente, para trazabilidad
    try:
        shutil.copy2(ruta_xlsx, os.path.join(destino, os.path.basename(ruta_xlsx)))
    except shutil.SameFileError:
        pass

    libro = os.path.join(destino,
                         f"Declaracion Renta AG{caso['ident']['ano']} - {carpeta}.xlsx")
    r = subprocess.run([sys.executable, os.path.join(BASE, 'generar.py'),
                        '--datos', dpath, '--salida', libro],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    ok = r.returncode == 0
    return {'caso': caso, 'carpeta': carpeta, 'datos_py': dpath,
            'generado': ok, 'salida': (r.stdout or '') + (r.stderr or ''),
            'descuadres': caso['descuadres'],
            'n_altas': sum(1 for a in caso['avisos'] if a[0] == 'ALTA')}


def main():
    ap = argparse.ArgumentParser(description='Exógena → libro de declaración de renta')
    ap.add_argument('archivo')
    ap.add_argument('--salida', default=None)
    args = ap.parse_args()
    res = procesar_archivo(args.archivo, args.salida)
    caso = res['caso']
    print(f"Cliente : {caso['ident']['nombre']}  ·  AG {caso['ident']['ano']}")
    print(f"Registros: {caso['n_registros']}   UVT: {caso['uvt']:,}".replace(',', '.'))
    print('\nValidación contra los topes de la DIAN:')
    for k, v in caso['difs'].items():
        marca = 'OK' if abs(v) <= clasificador.tolerancia(caso['topes'][k]) else 'DESCUADRE'
        print(f'  {k:12} DIAN {caso["topes"][k]:>15,.0f}  reconstruido {caso["mios"][k]:>15,.0f}  dif {v:>+12,.0f}  {marca}'.replace(',', '.'))
    print(f"\nAlertas: {len(caso['avisos'])} ({res['n_altas']} ALTA)")
    for sev, hall, _, _ in caso['avisos']:
        print(f'  [{sev:11}] {hall}')
    print('\n' + res['salida'].strip())
    print('SEMAFORO:', 'ROJO' if res['descuadres'] else ('AMARILLO' if res['n_altas'] else 'VERDE'))


if __name__ == '__main__':
    main()

