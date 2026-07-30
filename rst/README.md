# Módulo RST — Régimen Simple de Tributación

Segundo apartado de RENTA IA. Misma forma que el módulo de renta: **entra un
archivo de la DIAN, sale un libro de trabajo de 9 hojas**. Aquí el entregable es
el **Formulario 2593** (recibo electrónico del anticipo bimestral), no una
declaración anual.

```
# desde la raíz del proyecto — `rst` es un paquete
python -m rst.generar --consolidado "CONSOLIDADO ...xlsx" --ficha rst\fichas\mi-cliente.py
python -m rst.pruebas          # regresión del motor: TODAS LAS PRUEBAS PASAN
python -m rst.pruebas_web      # regresión del apartado publicado
.\rst\verificar.ps1 -Ruta "libro.xlsx"   # recalcula en Excel real
```

## Piezas

| archivo | qué hace |
|---|---|
| `parametros.py` | UVT por año, tabla de tarifas del art. 908 ET, tarifas de IVA/ReteIVA/pensión y fundamento normativo. Lo único que hay que tocar cuando cambia la norma. |
| `lector.py` | Consolidado de facturación electrónica → ventas, compras, certificados de ReteIVA y planillas de PILA. |
| `calculos.py` | Liquidación completa en Python puro + validaciones + alertas + semáforo. |
| `libro.py` | Las 9 hojas, en memoria (`construir` / `a_bytes`), listas también para la web. |
| `generar.py` | Línea de comandos. |
| `nube.py` | Supabase: `recibos_rst` y `alertas_rst`, tablas propias del módulo. |
| `fichas\` | Un archivo por contribuyente con lo que el consolidado no trae. Copiar `ejemplo.py`; las fichas reales no se versionan. |

## El principio de autoverificación, aquí

En renta la señal son los topes precalculados de la DIAN. En el SIMPLE son
**razones que deben dar exactas** y **los totales que el propio consolidado
trae al pie de cada hoja**:

- IVA generado ÷ ingresos gravados = **19 %** (art. 468 ET)
- ReteIVA ÷ IVA generado = **15 %** (art. 437-1 ET)
- las sumas del motor contra los totales al pie de `F.VENTA` y `F.COMPRA`

Si algo de eso no cuadra, el semáforo va a **ROJO** y no se debe presentar.
`AMARILLO` es «cuadra, pero quedan alertas ALTA por resolver»; el caso modelo
está en amarillo a propósito.

## Trampas del archivo fuente, ya resueltas en el lector

- El consolidado pesa 63 MB pero solo tiene ~300 filas con datos: es formato
  fantasma sobre 1.048.576 filas. Se abre en `read_only=True` y **se corta por
  la primera fila vacía, nunca por `max_row`** (así tarda 0,1 s).
- `F.VENTA` trae dos columnas parecidas: `Rete IVA` viene en cero y la buena es
  `RETEIVA`. Las columnas se localizan por nombre, no por posición.
- En `F.COMPRA` la base gravable viene en la columna **sin encabezado** que
  precede a `Total`.
- El reporte de emitidos incluye **documentos soporte con no obligados**
  (prefijo DSE): son compras, no ingresos. Contarlos infla la base.
- Las últimas filas de cada hoja no son documentos: son los **totales
  precalculados**. Se capturan y se usan como validación.
- `S.SOCIAL` es un reporte de PILA con maquetación libre (un bloque por
  administradora), no una tabla.

## Caso de referencia

El motor se validó contra un libro real hecho a mano —una intermediaria de
seguros del grupo 3, un bimestre completo— y reproduce **las 16 casillas** del
Formulario 2593, verificado abriendo el libro generado en Excel y recalculando.

El caso concreto no se versiona: es información sujeta a la reserva del art. 583
E.T. Vive en `rst\caso_referencia.py` (ignorado por git) junto con las cifras
congeladas, y `python -m rst.pruebas` lo usa si está presente. Sin ese archivo
la suite corre igual y solo omite ese bloque.

## En la web

El apartado **RST** está publicado junto al de Renta; la barra superior alterna
entre los dos. Bandeja con semáforo, detalle del recibo con las comprobaciones
y las casillas del 2593, descarga del libro por URL firmada y el mismo flujo de
revisión (borrador → en revisión → liberada).

Decisiones tomadas (30-jul-2026):

- **Tablas propias** `recibos_rst` / `alertas_rst`, no un campo de tipo sobre
  `declaraciones`. La razón es la clave del caso: aquí es (contribuyente, año,
  **bimestre**). `contribuyentes` sí se comparte, así que un mismo cliente
  puede estar en los dos regímenes y se ve como una sola ficha.
- **Solo los anticipos bimestrales.** La declaración anual del SIMPLE
  (Formulario 260) queda fuera; de ahí `recibos_rst` y no `declaraciones_rst`.

## Pendiente

- **Subida por la web**: el consolidado de 63 MB no pasa el tope de 4 MB de la
  plataforma. Por ahora el formulario lo dice y explica cómo adelgazarlo; la
  salida completa es procesarlo desde el escritorio.
- **Calendario de plazos del SIMPLE**, distinto del de renta de personas
  naturales. Falta el decreto o la tabla oficial: no se inventa.
- Un segundo caso real, con otro grupo de actividad o varios municipios.
