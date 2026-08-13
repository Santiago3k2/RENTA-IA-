# RENTA IA — Arquitectura

> **RENTA IA** es el nombre del producto.
> *Declaraciones de renta de personas naturales, desde la exógena de la DIAN.*

Visión: una aplicación web donde el cliente sube su reporte de exógena, el
sistema arma el borrador completo, y **el contador lo revisa y lo libera** antes
de que el cliente lo reciba. Decisiones tomadas (jul-2026):

| Decisión | Elección |
|---|---|
| Flujo | El cliente sube → el sistema genera → **el contador revisa y libera** |
| Entregable | El libro de 9 hojas **y** el borrador del Formulario 210 |
| Plataforma | Aplicación web |

## El principio que lo hace viable: autoverificación

El reporte de la DIAN trae sus **topes precalculados**. El motor reconstruye
esas mismas cifras desde los registros; si coinciden (± redondeo), la
clasificación es correcta; si no, el caso se marca para revisión. Esto permite
un semáforo automático por caso:

- **Verde** — topes cuadran y no hay alertas ALTA → revisión rápida.
- **Amarillo** — topes cuadran pero hay alertas ALTA → revisar las alertas.
- **Rojo** — topes no cuadran → clasificación incompleta, no sale del sistema.

## Componentes

```
┌────────────┐   sube exógena    ┌──────────────────────────────┐
│  Cliente    │ ────────────────► │  MOTOR (Python, sin web)      │
│  (web)      │   + formulario    │  1 parser.py    lee el xlsx   │
└────────────┘   de faltantes     │  2 clasificador reglas→destino│
      ▲                           │  3 validador    topes DIAN    │
      │ descarga                  │  4 libro.py     9 hojas       │
      │ liberada                  │  5 f210.py      borrador 210  │
┌────────────┐   bandeja de       └──────────────┬───────────────┘
│  Contador   │ ◄─────────────────────────────────┘
│  (revisa)   │   caso + semáforo + alertas
└────────────┘
```

- **Motor** — Python puro, sin dependencias web. Los pasos 4 (libro) ya existen
  y están validados: `generador\` produce el libro completo desde `datos.py` y
  la regresión contra el modelo aprobado da coincidencia exacta en las 13 cifras
  clave. Los pasos 1–2 (parser + clasificador automático del xlsx de exógena)
  son el siguiente hito: hoy la clasificación se hace a mano llenando `datos.py`
  según `PROCEDIMIENTO.md`.
- **Backend** — API que recibe el archivo, corre el motor, guarda el caso y
  expone la bandeja del contador. Recomendado FastAPI (mismo lenguaje del
  motor, sin reescrituras).
- **Frontend** — portal del cliente (subir archivo + formulario de datos que no
  vienen por exógena: declaración anterior, dependientes, créditos, residencia)
  y bandeja del contador (semáforo, alertas, editar, liberar).
- **Datos** — Postgres para casos/estados/usuarios; almacenamiento de archivos
  cifrado. Los xlsx de exógena y los libros generados son datos personales
  tributarios: acceso solo autenticado, nada público.

## Fases

1. **Motor data-driven** ✅ *(jul-2026)*
   `datos.py` → libro de 9 hojas. Regresión exacta contra el modelo aprobado
   (Sepúlveda AG 2025) y contra un segundo cliente real con declaración ya
   presentada (Suárez Moya AG 2024: topes $0 de diferencia, impuesto 0 = 210).
1b. **Validador + bandeja local** ✅ *(jul-2026)*
   `generador\calculos.py` replica la liquidación en Python puro y compara
   contra `topes_dian` → semáforo VERDE/AMARILLO/ROJO. `web\app.py` (stdlib,
   puerto 8765) muestra la bandeja, el detalle de validación y las alertas, y
   descarga el libro. Es el embrión de la web interna.
2. **Parser + clasificador automático** ✅ *(jul-2026)*
   `parser_exogena.py` lee el reporte del prevalidador (detección de cabecera,
   topes, metadata de la columna «Información Adicional»). `clasificador.py`
   asigna destino a cada registro usando la columna «Uso declaración Sugerida»
   de la DIAN como señal principal y el detalle como respaldo, aplica las cuatro
   reglas de depuración y genera las alertas. `autogen.py` encadena todo hasta
   el libro. **Nunca inventa un destino**: lo que no encaja queda SIN CLASIFICAR
   y dispara alerta ALTA + semáforo ROJO.
   Regresión (`regresion.py`): 22/22 cifras exactas contra la clasificación
   manual, en los dos casos de referencia.
2b. **Subida por web** ✅ — la bandeja acepta el .xlsx arrastrado, corre la
   tubería y redirige a la ficha del caso. Todo con librería estándar.
3. **Borrador 210** — módulo `f210.py`: mapa renglón → valor desde las anclas
   del libro, exportable como hoja adicional o archivo para el prevalidador.
4. **Web interna completa** ✅ *(jul-2026)*
   `db.py` guarda contribuyentes, declaraciones y alertas en Supabase, y los
   libros y exógenas en dos buckets privados con URL firmada. `sincronizar.py`
   sube lo que hoy vive en `clientes\`, es idempotente y respeta el estado de
   revisión que el caso ya tenga en la nube. Los estados
   (borrador / en revisión / liberada) se mueven desde la ficha del caso, y solo
   los mueve quien ve toda la cartera.
4b. **Cuentas y panel de administración** ✅ *(30-jul-2026)*
   Los usuarios dejan de ser dos constantes en variables de entorno y pasan a
   ser filas de `usuarios`, con contraseña cifrada (PBKDF2-SHA256, 600.000
   iteraciones), rol, estado y cupo. Cualquiera puede registrarse; el
   administrador aprueba, inhabilita, elimina, fija cupos y borra declaraciones
   desde `/admin`. Todo queda escrito en `bitacora`, y `ajustes` permite abrir o
   cerrar el registro sin volver a desplegar.
   La lógica está en `generador\cuentas.py`, el HTML en `web\admin.py` y los
   permisos en `api\index.py` — esa separación es deliberada: si una vista
   empieza a decidir permisos, algo se coló donde no debía.
4c. **Privacidad, descargo y carga en dos pasos** ✅ *(13-ago-2026)*
   Tres decisiones de producto que cambiaron el modelo de permisos:
   - **Un solo rol operativo.** Se retiró «contador»: quien usa el programa es
     el contador. Quedan `admin` y `cliente`.
   - **Nadie ve lo que no cargó, ni el administrador.** De la cartera ajena solo
     se informa cuántos casos lleva cada cuenta. Para entrar hay que pedirle
     permiso a su dueño, que lo concede por 24 h / 7 / 30 días y puede
     revocarlo; el permiso vence solo (`generador\permisos.py`, tabla
     `permisos`). La bitácora dejó de escribir nombres de contribuyentes.
   - **La carga va en dos pasos** (`generador\borradores.py`, tabla
     `borradores`): subir no crea nada ni gasta cupo; en la pantalla de
     confirmación se ven las cifras, se responden las cinco preguntas que la
     exógena no trae (`generador\perfil.py`) y se **acepta el descargo**
     (`generador\legal.py`), que es obligatorio y queda anotado. Reprocesar un
     caso propio no consume cupo nuevo: eso destraba a quien subió el archivo
     equivocado sin reabrir el agujero de reciclar cupo borrando.
   - Las **alertas se marcan como resueltas**, con nota, autor y fecha, y
     sobreviven a que el caso se reprocese. Liberar exige que no queden ALTAS
     abiertas, comprobado en el servidor.

5. **Portal del cliente** — el registro, la subida y el formulario de faltantes
   ya están; faltan las notificaciones por correo y la descarga de la versión
   liberada como entregable distinto del papel de trabajo.

## Lo que nunca se automatiza

- Las decisiones de criterio tributario nuevas (cada regla del clasificador se
  agrega a la tabla con su sustento normativo, revisada por el contador).
- La liberación final de un caso: siempre pasa por el contador.
- Datos que solo tiene el contribuyente: se piden, no se estiman.

## Estado actual del código

```
Plantilla Renta\
  PROCEDIMIENTO.md      <- paso a paso operativo (modo asistido, vigente hoy)
  ARQUITECTURA.md       <- este documento
  plantilla\            <- modelo aprobado (referencia visual y de regresión)
  generador\
      build_lib.py         sistema de diseño (paleta, formatos, layout)
      datos.py             estructura de entrada + caso modelo
      sheet_*.py           una por hoja (9)
      generar.py           datos.py → libro
      parser_exogena.py    lee el reporte del prevalidador MUISCA
      clasificador.py      reglas de clasificación y depuración + alertas
      autogen.py           TUBERÍA COMPLETA: .xlsx → datos.py → libro
      calculos.py          validador en Python puro (semáforo)
      regresion.py         auto vs manual, cifra por cifra
      verificar.ps1        cifras clave + errores de fórmula en Excel real
      capturar.ps1         capturas PNG para revisión visual
      casos.py             descubre los casos de clientes\ (web + nube)
      config.py            lee el .env; dice qué falta sin conectarse
      db.py                Supabase: tablas y Storage (solo stdlib)
      cuentas.py           usuarios, contraseñas, roles, cupos, bitácora, ajustes
      inicializar.py       prepara la nube para el sistema de cuentas
      sincronizar.py       sube los casos locales a la nube
      pruebas_cuentas.py   regresión del sistema de cuentas
      pruebas_web.py       regresión de extremo a extremo del sitio publicado
  db\esquema.sql        <- tablas, índices y RLS (pegar en el SQL Editor)
  web\app.py            <- RENTA IA: bandeja del contador + subida (puerto 8765)
  web\render.py         <- el HTML de la bandeja, compartido por local y nube
  web\login.py          <- acceso, registro y cambio de contraseña
  web\admin.py          <- el HTML del panel de administración
  api\index.py          <- el sitio publicado; también corre en local (8766)
  clientes\             <- una carpeta por contribuyente, una subcarpeta por año:
                           clientes\<Nombre>\AG2025\{datos.py, libro.xlsx, exógena}
  referencia\           <- patrones congelados para la suite de pruebas
  subidas\              <- archivos recibidos por la web
```

## Interfaz

La bandeja agrupa **por contribuyente**, no por caso suelto: una ficha por
persona con sus años gravables adentro, cada uno con su semáforo, sus cifras y
sus acciones. Arriba, una franja con el conteo de contribuyentes, declaraciones
y cuántas están listas / con alertas / sin liberar. Buscador por nombre o cédula
para cuando la lista crezca a cientos.

Identidad visual heredada del libro de Excel aprobado: verde petróleo `#0D6E64`,
tinta `#12262B`, acento `#48B9AA`, títulos en Georgia, cuerpo en Segoe UI y el
crema `#FDF6E7` reservado para lo editable.

## Cómo se opera hoy

1. `cd web && python app.py` → http://localhost:8765
2. Arrastrar el `reporteExogena.xlsx` y pulsar «Procesar».
3. Leer el semáforo. ROJO = no liberar; el detalle dice qué partida falla.
4. Descargar el libro y terminarlo en Excel con los certificados.

Desde consola, sin web: `python autogen.py "<ruta al xlsx>"`.
