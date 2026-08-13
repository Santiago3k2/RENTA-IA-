# -*- coding: utf-8 -*-
r"""El descargo de responsabilidad de RENTA IA, en un solo sitio.

Igual que `render.py` es la única definición del HTML, este es el único sitio
donde vive el texto legal. Aparece en la pantalla de confirmación, en el
formulario del RST, en la ficha de cada caso, en el pie de todas las páginas y
—reforzado— dentro de los libros de Excel. Si estuviera escrito cinco veces,
tarde o temprano dirían cinco cosas distintas.

Vive en `generador\` y no en `web\` justamente por eso: lo necesitan los dos
lados. El motor lo escribe en la hoja «1. Resumen» del libro y en la portada
del recibo del SIMPLE; la web lo muestra y hace que se acepte.

Lo que sostiene el descargo, y por qué no es una fórmula vacía:

  · La exógena **no es la realidad económica del contribuyente**. Es lo que
    terceros le reportaron a la DIAN. Faltan activos que nadie reporta, sobran
    partidas mal clasificadas en origen y no vienen los soportes propios.
  · El sistema **avisa cuando algo no cuadra** —el semáforo, los topes, las
    alertas— pero no puede saber lo que el archivo no trae.
  · Quien firma la declaración ante la DIAN es el contador y su cliente, y las
    sanciones del art. 647 y siguientes del E.T. recaen sobre ellos. Un
    programa no puede asumir eso, y ninguno lo hace.

Por eso la aceptación es **obligatoria y se comprueba en el servidor**: sin la
casilla marcada el libro no se genera. Y queda anotada en la bitácora con el
usuario, el caso y la hora — que es lo que convierte un aviso en un respaldo.
"""

TITULO = 'ALERTA PROFESIONAL · REVISIÓN OBLIGATORIA ANTES DE PRESENTAR:'

# Una línea. Para el pie de página y las cintas estrechas.
CORTO = ('RENTA IA entrega un documento de trabajo, no una declaración lista '
         'para presentar: revise cada cifra antes de radicarla ante la DIAN.')

# El texto que se acepta, redactado por el titular de RENTA IA (13-ago-2026).
# Va tal cual, palabra por palabra: es la declaración de alcance y de tratamiento
# de datos del producto, no una glosa que se pueda reescribir por estilo. Lo
# único que pone el programa son las negritas, que son formato y no contenido.
PARRAFOS = (
    'RENTA IA procesa automáticamente la información suministrada por el '
    'usuario, generando un resultado preliminar con base en los datos '
    'reportados en MUISCA – DIAN, como apoyo para la elaboración de la '
    'declaración de renta. Si la información presenta errores, '
    'inconsistencias, omisiones o una clasificación inadecuada, corresponde al '
    'profesional identificar, analizar y realizar los ajustes que resulten '
    'procedentes.',

    'RENTA IA <b>no reemplaza el conocimiento, experiencia ni criterio '
    'profesional del Contador Público</b>. Por ello, es indispensable que el '
    'profesional analice, interprete, verifique y valide la información, '
    'confrontándola con los respectivos soportes antes de presentar la '
    'declaración.',

    '<b>Protección de datos:</b> La información cargada en RENTA IA se utiliza '
    'exclusivamente para su procesamiento dentro de la herramienta, bajo '
    'medidas de seguridad y confidencialidad orientadas a proteger los datos '
    'personales, financieros y tributarios suministrados.',
)

# El mismo texto seguido, para donde no caben tres párrafos.
LARGO = ' '.join(PARRAFOS)

# Lo que dice la casilla que hay que marcar.
CASILLA = ('Entiendo que este es un documento de trabajo, que debo revisar la '
           'información antes de presentarla ante la DIAN, y que RENTA IA no '
           'responde por los errores que yo no corrija.')

# El mismo descargo, en texto plano y comprimido, para el libro de Excel.
# Sin etiquetas: allí se escribe dentro de una celda.
LIBRO = (
    'DOCUMENTO DE TRABAJO — NO ES UNA DECLARACIÓN PRESENTADA. Liquidación '
    'propuesta, elaborada automáticamente sobre información exógena; no es un '
    'formulario oficial de la DIAN. La exógena no reemplaza la realidad '
    'económica del contribuyente: antes de diligenciar el formulario deben '
    'incorporarse los soportes propios —las casillas de fondo crema de cada '
    'hoja están para eso— y resolverse las partidas de la hoja de alertas. '
    'Quien presenta la declaración es responsable de revisar y validar cada '
    'cifra; RENTA IA no responde por errores, mayores impuestos, intereses ni '
    'sanciones derivados de presentarla sin revisar.')

# El mismo, ajustado al recibo del SIMPLE: allí la fuente no es la exógena sino
# la facturación electrónica, y lo que sale no es una declaración anual sino el
# recibo del anticipo bimestral.
LIBRO_RST = (
    'DOCUMENTO DE TRABAJO — NO ES UN RECIBO PRESENTADO. Liquidación propuesta '
    'del anticipo bimestral del SIMPLE, elaborada automáticamente a partir del '
    'archivo de facturación electrónica de la DIAN; no es un formulario '
    'oficial. La facturación electrónica no recoge todo: el aporte a pensión '
    'viene de la PILA, el grupo de actividad y la tarifa de ICA son decisiones '
    'de criterio, y puede haber documentos por fuera del período o del '
    'archivo. Quien presenta el recibo es responsable de revisar y validar '
    'cada casilla y de resolver las alertas de la hoja 9; RENTA IA no responde '
    'por errores, mayores impuestos, intereses ni sanciones derivados de '
    'presentarlo sin revisar.')

# El error exacto cuando alguien intenta generar sin aceptar. Se comprueba en
# el servidor y no ocultando el botón: es la diferencia entre una cortesía y
# una condición.
NO_ACEPTADO = ('Para generar el documento tiene que marcar la casilla de '
               'revisión. Es lo que deja constancia de que usted sabe que '
               'debe revisarlo antes de presentarlo.')

NOMBRE_CAMPO = 'descargo'          # el name= de la casilla, en los dos apartados


def aceptado(campos):
    """¿Vino marcada la casilla? Se pregunta en el servidor, siempre."""
    return bool((campos or {}).get(NOMBRE_CAMPO))


def bloque(destacado=True):
    """El descargo completo, para las pantallas donde hay que aceptarlo.

    Los tres párrafos van separados y no corridos: el tercero es el de
    protección de datos y dice algo distinto de los dos primeros.
    """
    clase = 'descargo' + ('' if destacado else ' suave')
    cuerpo = ''.join(f'<p>{p}</p>' for p in PARRAFOS)
    return f'<div class="{clase}"><h3>{TITULO}</h3>{cuerpo}</div>'


def casilla(marcada=False):
    """La casilla obligatoria. Va junto al botón que genera."""
    chk = ' checked' if marcada else ''
    return (f'<label class="descargo-check">'
            f'<input type="checkbox" name="{NOMBRE_CAMPO}" value="1" required{chk}>'
            f'<span>{CASILLA}</span></label>')


def cinta():
    """Recordatorio de una línea, para la ficha de un caso ya generado."""
    return f'<div class="descargo suave"><p>{CORTO}</p></div>'


ESTILO = """
/* ── DESCARGO DE RESPONSABILIDAD ── */
.descargo{border:1px solid var(--ambar-b);border-left:3px solid var(--ambar);
background:var(--ambar-f);border-radius:11px;padding:16px 18px;margin:18px 0}
.descargo h3{font-size:13.5px;color:var(--ambar-t);margin-bottom:7px}
.descargo p{font-size:12.7px;color:var(--text2);line-height:1.6;max-width:88ch}
.descargo p + p{margin-top:9px}
.descargo b{color:var(--ink);font-weight:600}
.descargo.suave{border-color:var(--bord);border-left-color:var(--z400);
background:var(--z50)}
.descargo.suave p{font-size:12.4px}
.descargo-check{display:flex;align-items:flex-start;gap:10px;margin-top:16px;
font-size:12.9px;line-height:1.5;color:var(--text2);cursor:pointer;
border:1px solid var(--bord-2);border-radius:10px;padding:13px 15px;background:var(--sup)}
.descargo-check:hover{border-color:var(--z400)}
.descargo-check input{width:17px;height:17px;accent-color:var(--tinta);cursor:pointer;
flex:none;margin-top:1px}
.descargo-check:has(input:checked){border-color:var(--verde);background:var(--verde-f)}
"""
