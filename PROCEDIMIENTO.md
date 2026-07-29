# RENTA IA — Procedimiento operativo

Paso a paso para producir el libro de trabajo de 9 hojas de un cliente nuevo,
idéntico en estructura al modelo aprobado (`plantilla\MODELO APROBADO - Sepulveda
Orejarena AG2025.xlsx`). El generador vive en `generador\` y el único archivo que
cambia por cliente es su `datos.py`.

---

## 0 · Requisitos

- Python con `openpyxl` (`python -c "import openpyxl"` debe funcionar).
- Excel de escritorio (solo para la verificación y las capturas).
- El reporte de exógena del cliente descargado del prevalidador MUISCA.

## 1 · Carpeta del cliente

Una carpeta por contribuyente, una subcarpeta por año gravable:

```
clientes\<Apellidos Nombre>\AG2025\
    reporteExogena.xlsx        <- el archivo fuente, sin tocar
    datos.py                   <- generado por autogen, o editado a mano
    Declaracion Renta AG2025 - <Nombre>.xlsx
```

Lo normal es no crearla a mano: subir la exógena en RENTA IA
(`cd web && python app.py` → http://localhost:8765) la crea sola.

## 2 · Clasificar la exógena

Leer registro por registro y asignar cada uno a su destino. Tabla de referencia:

| Qué reporta el tercero (concepto) | Destino |
|---|---|
| Pagos por salarios, prestaciones, cesantías consignadas o pagadas (2276) | **R32** rentas de trabajo |
| Aportes obligatorios a salud / pensión del trabajador (2276) | **R33** INCRNGO |
| Cesantías abonadas por el fondo (formato del fondo) | R32 — pero si el empleador ya reportó la consignación, prevalece el valor del empleador |
| Rendimientos de CDT, cartera colectiva, intereses (1020, 5063, 6) | **R58** rentas de capital |
| Ingresos brutos de mandato — arrendamientos (4040) | **R58** (criterio art. 338 E.T.; la DIAN sugiere R74 — dejar el callout de reclasificación) |
| Revalorización de aportes (5059) | **R74** rentas no laborales |
| Ingreso distribuido por consorcio (4070) | R74, **en pareja** con su retención 4070 |
| Siniestros por daño emergente (5048) | R74 y a la vez R76 como INCRNGO |
| Retención practicada (cualquier concepto) | **R132** retenciones |
| Saldos a 31-dic: CDT, cuentas, FIC, aportes sociales (1010/1020) | **R29** patrimonio bruto |
| Avalúo catastral y base predial (1476) | R29 — **solo el MAYOR de los dos por predio** |
| Avalúo de vehículo (1480) | R29 |
| Cuentas por cobrar (2202/2206/2240) | R29 — si 2206 y 2240 llegan con mismo NIT y valor, es UNA partida |
| Activos parafiscales/cesantías (2214) vs. cesantías consignadas (2276) | R29 — una sola vez |
| Cuentas por pagar (1315/1317) | **R30** deudas |
| Movimientos en cuentas / inversiones efectuadas | **Tope 4** consignaciones |
| Consumos con tarjeta (1023) | **Tope 3** |
| Facturación electrónica (suma y monto susceptible) | **Tope 5** + base de la deducción del 1% |
| Patrimonio bruto declarado año anterior / saldo a favor | Referencias (conciliación y R131) |

**Inmuebles en copropiedad (concepto 1476).** El avalúo que informa el municipio
es el del **predio completo**. Cuando la columna «Información Adicional» trae un
porcentaje de participación menor al 100% (herencias, sucesiones, edificios con
varios dueños), al contribuyente solo le corresponde su cuota parte:
`valor patrimonial = avalúo × participación`. Es la única familia de activos donde
el porcentaje se aplica — en inversiones y aportes sociales el valor informado ya
es el del contribuyente. Ignorarlo infla el patrimonio en órdenes de magnitud.

Reglas de depuración que siempre se revisan:

1. **Predios (1476):** el municipio manda avalúo y base predial por cada predio → tomar el mayor, marcar `MAYOR VALOR`.
2. **Duplicados:** misma partida bajo dos formatos (mismo NIT + mismo valor, conceptos distintos) → computar una vez, marcar `DUPLICADA`.
3. **Titular secundario:** saldos e inversiones como titular secundario → alerta ALTA; en el tope 4 se excluyen; en patrimonio queda al 100% con el % editable para prorratear.
4. **Consorcios (4070):** ingreso y retención van juntos — si se excluye uno, se excluye el otro.

**Validación obligatoria:** los totales reconstruidos deben reproducir los **cinco
topes** precalculados por la DIAN (vienen en el mismo reporte). La tolerancia es
relativa —una millonésima del tope— porque la DIAN redondea. Si no cuadran, hay
una partida mal clasificada. Esta es la prueba de que la clasificación quedó bien.

El **tope 2 (patrimonio)** solo valida la composición cuando supera al patrimonio
declarado el año anterior; si es igual a ese, la DIAN tomó el del año anterior y
no hay nada que contrastar.

## 3 · Llenar `datos.py`

Copiar `generador\datos.py` a la carpeta del cliente y reemplazar **todas** las
secciones (identificación, declaración anterior, patrimonio, ingresos,
retenciones, consignaciones, alertas, detalle) y **todos** los `TEXTOS` —son
prosa del caso, no plantilla—. Si una clave de texto no aplica, dejar `''` y el
bloque se omite solo.

Datos que hay que pedirle al cliente (no vienen por exógena):
patrimonio bruto declarado el año anterior, impuesto neto del año anterior,
saldo a favor, anticipo liquidado, dependientes, créditos hipotecario/educativo,
certificados. Si aún no se tienen, dejar `0`: quedan como casillas crema.

## 4 · Generar

```
cd generador
python generar.py --datos "..\clientes\<Apellidos Nombre>\datos.py"
```

El libro sale en `clientes\<Apellidos Nombre>\Declaracion Renta AG<año> - <nombre>.xlsx`.

## 4b · Suite de pruebas del motor

```
python pruebas.py
```

Corre todos los casos conocidos, verifica los topes y compara contra los patrones
congelados en `referencia\`. **Debe decir «TODAS LAS PRUEBAS PASAN» después de
cualquier cambio al clasificador.**

## 5 · Verificar (obligatorio)

```
.\verificar.ps1 -Ruta "..\clientes\<...>\Declaracion Renta ....xlsx"
```

- Las **cifras clave** (nombres definidos) deben cuadrar con los topes DIAN y
  con la clasificación del paso 2.
- **ERRORES DE FORMULA** debe decir `ninguno`.

## 6 · Revisión visual

```
.\capturar.ps1 -Ruta "..." -Hoja 1 -Rango "B1:I36" -Png "resumen.png"
```

Revisar como mínimo: Resumen, Patrimonio, Liquidación y Alertas.

## 7 · Entregar

- Recordar al cliente las casillas crema y los 4 datos de la declaración anterior.
- Las alertas ALTA se resuelven **antes** de diligenciar el formulario.

---

## Reglas de oro (no negociables)

- Todo total es **fórmula**; nunca valores pegados.
- Lo editable va en **crema** (`FDF6E7` / borde `D9BE86`).
- Fecha exacta del plazo: sale del calendario oficial cargado en
  `generador\plazos.py`, por los **dos últimos dígitos** del documento. Para un
  año gravable que no esté en esa tabla —y para el componente inflacionario—
  sigue siendo **casilla en blanco con nota**, nunca un dato inventado.
  Al llegar el decreto de un año nuevo, se añade su bloque a `plazos.py` y se
  regeneran los libros; el módulo exige las 100 combinaciones de dígitos.
- Se dice **"caja"**, nunca "bóveda".
- El archivo fuente de exógena no se modifica jamás.
