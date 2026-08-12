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
  cuentas.py          usuarios: contraseñas, roles, cupos, bitácora y ajustes
  inicializar.py      deja la nube lista para el sistema de cuentas
  sincronizar.py      sube los casos locales a la nube (idempotente)
  pruebas.py          regresión del motor, contra casos congelados
  pruebas_cuentas.py  regresión del sistema de cuentas
  pruebas_web.py      regresión de extremo a extremo del sitio publicado
  regresion.py        compara clasificación automática vs. manual
rst/                  módulo del Régimen Simple (ver rst/README.md)
  parametros.py       UVT, tabla de tarifas del art. 908 ET y fundamento normativo
  lector.py           consolidado de facturación electrónica → ventas, compras, PILA
  calculos.py         liquidación del 2593 + validaciones + semáforo
  libro.py            las 9 hojas del libro del SIMPLE, en memoria
  generar.py          línea de comandos del módulo
  nube.py             Supabase: recibos_rst y alertas_rst
  pruebas.py          regresión contra el caso modelo
  pruebas_web.py      regresión del apartado RST publicado
db/esquema.sql        tablas, índices y RLS
db/esquema_rst.sql    tablas propias del módulo RST
web/app.py            bandeja del contador (puerto 8765, o el de $PUERTO)
web/render.py         el HTML de la bandeja, compartido por local y nube
web/rst_vista.py      el HTML del apartado RST
web/login.py          acceso, registro y cambio de contraseña
web/admin.py          el HTML del panel de administración
api/index.py          el sitio publicado (y `python index.py` para verlo en local)
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
sujetas a la reserva del art. 583 E.T.

Variables de entorno que deben existir en Vercel:

```
SUPABASE_URL                 la misma del .env
SUPABASE_SERVICE_ROLE_KEY    la misma del .env
RENTA_IA_CLAVE_ADMIN         contraseña del primer administrador
RENTA_IA_SECRETO             recomendada: firma las sesiones
```

Sin las dos de Supabase el sitio responde 503 y no muestra nada: preferible
fuera de servicio que abierto.

Para ver el sitio publicado tal cual, pero en el equipo:

```bash
cd api && python index.py      # → http://localhost:8766
```

## Cuentas y panel de administración

Cada usuario es una fila de la tabla `usuarios`; nada de contraseñas en el
código ni en variables de entorno. Cualquiera puede **registrarse** desde la
pantalla de acceso, y el administrador decide desde el panel qué puede hacer.

| Rol | Ve | Cupo |
|---|---|---|
| **Administrador** | toda la cartera, y maneja las cuentas | sin límite |
| **Contador** | toda la cartera | sin límite |
| **Cliente** | solo lo que él mismo carga | el que le fije el administrador |

El **cupo** es cuántas declaraciones puede procesar esa cuenta en total. Se
comprueba en el servidor, no ocultando el botón, y un cliente no puede
sobrescribir un caso cargado por otro.

Una declaración **no se elimina desde ninguna parte del sitio**: ni su dueño ni
el administrador pueden borrarla, y eliminar una cuenta conserva las suyas. El
cupo es lo que se vende, y si borrar lo devolviera, una cuenta de cupo 1 podría
procesar sin límite subiendo, borrando y volviendo a subir. Para cortarle el
servicio a alguien se inhabilita la cuenta; para ampliárselo, se le sube el cupo.

El panel (`/admin`, solo para el rol administrador) tiene cinco secciones:

- **Panel** — cuentas por aprobar, cuentas bloqueadas, cifras y últimos movimientos.
- **Cuentas** — aprobar, inhabilitar, cambiar rol y cupo, editar datos,
  restablecer la contraseña, cerrar sesiones a distancia y eliminar.
- **Declaraciones** — todas las de la plataforma, para consultarlas. No se
  borran: ver arriba por qué.
- **Bitácora** — quién entró, qué miró y qué borró, con la hora y la dirección IP.
- **Ajustes** — abrir o cerrar el registro, exigir aprobación previa, fijar el
  cupo con el que nace una cuenta y poner un aviso en la bandeja. Cambian el
  sitio al instante, sin volver a publicarlo.

Cómo se guardan las contraseñas: PBKDF2-HMAC-SHA256 con 600.000 iteraciones y
sal propia por cuenta — el costo que recomienda OWASP. Nadie, ni el
administrador, puede leer la contraseña de nadie; restablecerla genera una
provisional que se muestra **una sola vez** y obliga a cambiarla al entrar.

Otras defensas que conviene no deshacer sin pensarlo:

- Al entrar se verifica la contraseña **antes** que el estado de la cuenta; al
  revés, cualquiera podría inventariar qué cuentas existen sin saber ni una clave.
- Cinco intentos fallidos bloquean la cuenta, y el bloqueo se duplica con cada
  fallo nuevo hasta una hora.
- Cada petición relee la cuenta: inhabilitar a alguien lo echa en el acto, no
  cuando venza su cookie.
- Toda acción que escribe exige un testigo anti-CSRF atado a la sesión, además
  de la cookie `HttpOnly; Secure; SameSite=Lax`.
- Nada irreversible ocurre por un enlace: borrar pasa por una pantalla de
  confirmación que dice, con números, qué se va a perder.

**Arranque.** `RENTA_IA_CLAVE_ADMIN` es el seguro contra quedarse fuera: si la
tabla se quedara sin ningún administrador, el primer acceso vuelve a crear la
cuenta `admin` con esa contraseña. Para preparar la nube por primera vez:

```bash
cd generador
python inicializar.py            # dice qué falta, sin escribir nada
python inicializar.py --aplicar  # crea lo que falte
python pruebas_cuentas.py        # debe decir «TODAS LAS PRUEBAS PASAN»
python pruebas_web.py            # recorre el sitio como un navegador
```

## Los dos apartados

La aplicación atiende dos regímenes y la barra superior alterna entre ellos:

- **Renta** — declaración anual de personas naturales desde la exógena de la DIAN.
- **RST** — anticipo bimestral del Régimen Simple (Formulario 2593) desde el
  consolidado de facturación electrónica. Tablas propias, porque la clave del
  caso es (contribuyente, año, **bimestre**) y no (contribuyente, año).
  `contribuyentes` sí se comparte: un mismo cliente puede estar en los dos.

El alcance del RST son **solo los anticipos bimestrales**; la declaración anual
del SIMPLE (Formulario 260) queda fuera por ahora.

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
