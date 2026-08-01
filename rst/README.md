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
| `plazos.py` | Calendario oficial de vencimientos, por el **último dígito** del NIT. |
| `nube.py` | Supabase: `recibos_rst` y `alertas_rst`, tablas propias del módulo. |
| `fichas\` | Un archivo por contribuyente con lo que el consolidado no trae. Copiar `ejemplo.py`; las fichas reales no se versionan. |

## La entrada: el archivo crudo de la DIAN

El motor trabaja con la exportación **tal como la descarga la DIAN**, que solo
trae `Rp_Doc_<fecha>` y, a veces, `Rp_Docpras`. De ahí deriva todo lo demás, y
da exacto:

    gravado    = IVA ÷ 19 %          no gravado = Total − gravado − IVA
    ReteIVA    = IVA × 15 %          base de compra = IVA ÷ 19 %

Las hojas `F.VENTA`, `F.COMPRA` y `RETEIVA` son trabajo manual **redundante**:
si vienen, se respetan (el criterio del contador manda), pero ya no hacen falta.
Eso además resuelve el tope de subida: el archivo crudo del caso de referencia
pesa **0,04 MB** contra los 63 MB del consolidado trabajado.

### Venta o compra lo decide el NIT, no la hoja

La exportación de la DIAN **mezcla los documentos emitidos y los recibidos en la
misma hoja** `Rp_Doc_…` y los separa en la columna «Grupo». Lo que distingue una
factura de venta de una de compra no es la hoja en que viene: es si el
contribuyente figura como **emisor** o como **receptor**.

Tomar la hoja entera como ventas —que es lo que se hacía— tenía el error
corriendo en los dos sentidos, y los dos en contra del contribuyente: las
facturas que él **recibió** engordaban el ingreso, y encima su IVA no llegaba al
descontable. En un caso real de 77 documentos, 13 facturas de compra se estaban
declarando como ingreso:

| | Con el bug | Corregido |
|---|---:|---:|
| Base del anticipo | 76.890.183 | **73.414.349** |
| IVA descontable | 0 | **139.419** |
| Anticipo neto | 2.401.473 | **2.191.185** |
| IVA a pagar | 10.373.148 | **10.115.223** |

Medio millón de pesos de más en un solo bimestre, en un cliente pequeño.

El reparto lo hace `lector._lado` comparando el NIT del contribuyente contra
`NIT Emisor` y `NIT Receptor`, con la columna «Grupo» como respaldo cuando no se
sabe el NIT. El NIT sale de la ficha; si no aparece en **ninguna** fila del
archivo, se avisa: casi siempre significa que se subió el consolidado de otro
cliente.

La excepción que confirma la regla es el **documento soporte con no obligados a
facturar** (prefijo DSE): lo emite el comprador, así que el contribuyente
aparece como emisor aunque esté comprando. Es compra, y el proveedor es el
tercero que figura como receptor.

### El bimestre no se escoge: sale del archivo

Las fechas de los documentos ya dicen de qué período es el archivo, así que el
motor lo deduce solo y en el formulario el bimestre viene en «detectar del
archivo». Si se fuerza uno a mano y el archivo no trae **ningún** documento de
ese período, el proceso se aborta nombrando el correcto.

Esto no es comodidad: antes un consolidado de mayo-junio procesado como
bimestre 1 pasaba el filtro sin una sola factura y salía un libro **entero en
ceros con semáforo AMARILLO**, indistinguible de una declaración válida. Ahora
un período vacío teniendo el archivo documentos de otros va en **ROJO**. Un
bimestre realmente sin ventas sí se puede declarar en ceros: el SIMPLE obliga a
presentar el anticipo aunque no haya habido ingresos.

Si el archivo trae más de un período se liquida el que tenga más documentos y
el recibo avisa de los otros, que van en su propio recibo.

### Las notas crédito restan

El tipo de documento se clasifica por palabras sobre el nombre **ya
normalizado** (`lector.clasificar`), no por la frase completa. La DIAN escribe
«Nota de crédito electrónica»: comparar contra el literal «nota crédito» —con
tilde, contra un texto al que se le quitaron las tildes— no encontraba nada y
las notas crédito **sumaban** al ingreso en vez de restarlo, el doble de su
valor. Lo mismo del lado de las compras, inflando el IVA descontable.

`clasificar` recibe el lado ya resuelto y devuelve a dónde va el documento
—`'venta'`, `'compra'` o nada— junto con el signo. La nómina electrónica y los
«application response» (acuses de recibo) no son ninguna de las dos cosas.

Lo único que no sale de la facturación electrónica es el **aporte a pensión**
(planilla PILA, otro sistema). Se captura en la ficha o en el formulario de la
web; sin él el anticipo sale más alto de lo que el contribuyente debe pagar, y
el motor lo alerta.

### Cuidado con las razones derivadas

En modo crudo, «IVA ÷ ingresos gravados = 19 %» y «ReteIVA ÷ IVA = 15 %» se
cumplen **por construcción**: el motor las calculó así. Una comprobación que no
puede fallar no es una comprobación, y presentarla como si lo fuera daría un
verde falso. Por eso en ese modo quedan marcadas como DERIVADAS, dejan de ser
críticas para el semáforo y el texto lo dice. Si el archivo trae las hojas
trabajadas, vuelven a ser comprobaciones de verdad.

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

## Por qué se recalcula en Excel, y no basta con Python

`rst\verificar.ps1` abre el libro en Excel real y recalcula. No es un lujo:
openpyxl **escribe** fórmulas, no las evalúa, así que la aritmética de Python y
la del libro son dos implementaciones distintas de lo mismo y pueden
divergir sin que ninguna prueba de Python lo note.

Ya pasó dos veces, y las dos se cazaron ahí:

- La tarifa se busca con un `SUMIFS` sobre la tabla del art. 908. Una base por
  encima del último tramo (16.666 UVT bimestrales) no casaba con ninguna fila:
  Excel devolvía **0 %** y un anticipo de **$0**, mientras Python aplicaba la
  tarifa mayor. Ahora la fórmula acota la base al rango de la tabla antes de
  buscar.
- El descuento por pensión hacía `-MIN(pensión; F29)` sobre el componente
  nacional sin acotar: con un componente negativo el `MIN` se quedaba con el
  negativo y la resta lo convertía en un descuento **positivo**, que sumaba.
  Ahora es `MAX(0;F29)`, la misma guarda que tiene Python.

`python -m rst.pruebas` comprueba que esas dos cotas sigan en las fórmulas, pero
la comprobación de verdad es abrir el libro.

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

## Plazos

El anticipo del SIMPLE vence según el **último dígito del NIT** —uno solo—,
no según los dos últimos como en renta de personas naturales. Copiar la lógica
del otro calendario daría fechas equivocadas, y una fecha mal puesta cuesta
sanción por extemporaneidad.

El calendario del año gravable 2026 está cargado en `plazos.py`, transcrito de
la tabla oficial guardada en `referencia\calendario plazos RST.png`. Cada
anticipo vence en el mes siguiente al cierre del bimestre; el del sexto se corre
a **enero del año siguiente**. `_verificar()` exige las 60 combinaciones al
importar: un dígito perdido revienta de una vez en vez de dejar una fecha en
blanco o inventada.

El libro escribe la fecha real en la hoja 1, editable, con una fórmula al lado
que cuenta los días que faltan o los que lleva vencida.

## Pendiente

- **Subida por la web**: el consolidado de 63 MB no pasa el tope de 4 MB de la
  plataforma. Por ahora el formulario lo dice y explica cómo adelgazarlo; la
  salida completa es procesarlo desde el escritorio.
- Un segundo caso real, con otro grupo de actividad o varios municipios.
