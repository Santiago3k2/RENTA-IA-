# RENTA IA

Declaraciones de renta de personas naturales en Colombia, a partir del reporte
de información exógena de la DIAN.

El contribuyente sube su `reporteExogena.xlsx` del prevalidador MUISCA; RENTA IA
lo lee, clasifica cada registro, **valida los totales contra los topes que la
propia DIAN precalcula en ese mismo reporte** y arma un libro de trabajo de
9 hojas con la liquidación completa. El contador revisa y libera.

> ⚠️ **Documento de trabajo.** La liquidación se revisa antes de presentarla a
> la DIAN. La exógena no reemplaza la realidad económica del contribuyente.

---

## El principio: autoverificación

El reporte de la DIAN trae cinco topes precalculados (ingresos, patrimonio,
consumos con tarjeta, consignaciones y compras). El motor reconstruye esas mismas
cifras desde los registros uno por uno. Si coinciden dentro del margen de
redondeo, la clasificación es correcta; si no, hay una partida mal asignada.

De ahí sale el semáforo:

| | Significado |
|---|---|
| 🟢 **VERDE** | Los topes cuadran y no hay hallazgos de severidad alta |
| 🟡 **AMARILLO** | Los topes cuadran, pero hay alertas ALTA por resolver |
| 🔴 **ROJO** | Los totales no cuadran — el caso **no debe liberarse** |

Cuando el clasificador encuentra un registro que ninguna regla cubre, **no lo
adivina**: lo marca SIN CLASIFICAR y el caso queda en rojo.

## Estructura

```
generador/
  parser_exogena.py   lee el reporte del prevalidador MUISCA
  clasificador.py     reglas de clasificación, depuración y alertas
  autogen.py          tubería completa: .xlsx → datos.py → libro
  generar.py          datos.py → libro de 9 hojas
  build_lib.py        sistema de diseño del libro (paleta, formatos, layout)
  sheet_*.py          una por hoja
  calculos.py         validador en Python puro (semáforo)
  casos.py            descubre los casos de clientes/ (lo usan la web y la nube)
  config.py           lee el .env y diagnostica lo que falte
  db.py               Supabase: tablas + Storage, solo librería estándar
  sincronizar.py      sube los casos locales a la nube (idempotente)
  pruebas.py          suite de regresión contra casos congelados
  regresion.py        compara clasificación automática vs. manual
db/esquema.sql        tablas, índices y RLS
web/app.py            bandeja del contador (puerto 8765, o el de $PUERTO)
```

## Uso local

```bash
pip install openpyxl
cd web && python app.py        # → http://localhost:8765
```

O sin interfaz:

```bash
cd generador
python autogen.py "ruta/reporteExogena.xlsx"
python pruebas.py              # debe decir «TODAS LAS PRUEBAS PASAN»
```

## Respaldo en la nube (Supabase)

Copie `.env.example` a `.env` y complete la clave secreta del proyecto. Después:

```bash
cd generador
python config.py               # qué falta configurar
python db.py                   # prueba la conexión y crea los buckets
python sincronizar.py --ver    # qué se subiría, sin escribir nada
python sincronizar.py          # sube todo
```

También hay un botón **Sincronizar con la nube** en la bandeja.

Cada caso se identifica por (contribuyente, año gravable): volver a sincronizar
actualiza, no duplica, y **no pisa el estado de revisión** que el caso ya tenga
en la nube. Los libros y las exógenas van a dos buckets privados y se descargan
con URL firmada de vigencia corta; el acceso público está cerrado.

Si acaba de crear o rotar la clave, Supabase responde 401 unos minutos mientras
se propaga. No es un error de configuración: reintente.

## Web publicada (Vercel)

`api/index.py` es la misma bandeja sobre funciones sin estado: procesa la
exógena en memoria, guarda en Supabase y sirve el libro con URL firmada. El
HTML es el mismo de la versión local (`web/render.py`), así que la interfaz no
se bifurca.

Todo el sitio pide usuario y contraseña — son declaraciones de personas reales,
sujetas a la reserva del art. 583 E.T. Dos usuarios:

| Usuario | Ve | Puede procesar |
|---|---|---|
| `admin` | toda la cartera | sin límite |
| `pruebapiloto2026` | solo lo que él mismo cargó | hasta 5 declaraciones |

El cupo se comprueba en el servidor, no solo ocultando el botón, y un usuario
restringido no puede sobrescribir un caso cargado por otro.

Variables de entorno que deben existir en Vercel:

```
SUPABASE_URL                 la misma del .env
SUPABASE_SERVICE_ROLE_KEY    la misma del .env
RENTA_IA_CLAVE_ADMIN         contraseña de admin
RENTA_IA_CLAVE_PILOTO        contraseña del piloto
RENTA_IA_CUPO_PILOTO         opcional, por defecto 5
```

Si falta cualquiera, el sitio responde 503 y no muestra nada: preferible fuera
de servicio que abierto.

## Alcance actual

**Cubre** la cédula general: rentas de trabajo (R32), de capital (R58) y no
laborales (R74), con su depuración separada, el límite del art. 336 num. 3, la
tabla del art. 241 y el anticipo del art. 807.

**No liquida todavía** pensiones, dividendos ni ganancias ocasionales. Cuando
aparecen, el clasificador los detecta, se detiene y marca el caso en rojo — no
los liquida mal en silencio.

## Datos sensibles

Los casos de contribuyentes **nunca** se versionan: `clientes/`, `subidas/`,
`referencia/` y todo `.xlsx`/`.pdf` están en `.gitignore`. Son datos tributarios
de personas reales (Ley 1581 de 2012 y secreto profesional). `generador/datos.py`
también está excluido; en el repo solo viaja `datos.ejemplo.py`, anonimizado.

Las credenciales van en variables de entorno, nunca en el código.
