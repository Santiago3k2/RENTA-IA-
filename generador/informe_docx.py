# -*- coding: utf-8 -*-
r"""Escribe un .docx de verdad sin instalar nada.

Un documento de Word es un ZIP con unos cuantos XML dentro. Aquí se arma a mano
—cuatro archivos y el texto— porque el proyecto entero corre con la librería
estándar más `openpyxl`, y meter una dependencia nueva para escribir un informe
sería pagar caro un adorno.

    import informe_docx
    doc = informe_docx.Documento('Informe de cambios')
    doc.titulo('RENTA IA')
    doc.h1('Lo que se hizo')
    doc.p('Un párrafo con **algo en negrita** dentro.')
    doc.guardar(r'C:\...\informe.docx')

Marcas admitidas en el texto: `**negrita**`. Nada más — con eso alcanza para un
informe y el que lee no necesita más.
"""
import re
import zipfile

# El mínimo que Word acepta sin quejarse. Cada archivo tiene su porqué:
#   [Content_Types].xml   qué es cada cosa dentro del ZIP
#   _rels/.rels           dónde empieza el documento
#   word/document.xml     el texto
#   word/styles.xml       cómo se ve
_CONTENT_TYPES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''

_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

_DOC_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

# Tinta #18181B y verde petróleo #0D6E64: los mismos del sitio y del libro.
_STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr>
  <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/>
  <w:color w:val="18181B"/></w:rPr></w:rPrDefault>
  <w:pPrDefault><w:pPr><w:spacing w:after="140" w:line="276" w:lineRule="auto"/>
  </w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:styleId="Titulo"><w:name w:val="Title"/><w:pPr>
  <w:spacing w:after="60"/></w:pPr><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/>
  <w:b/><w:sz w:val="56"/><w:color w:val="0D6E64"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Subtitulo"><w:name w:val="Subtitle"/><w:pPr>
  <w:spacing w:after="360"/></w:pPr><w:rPr><w:sz w:val="24"/><w:color w:val="52525B"/>
  </w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="H1"><w:name w:val="heading 1"/><w:pPr>
  <w:spacing w:before="400" w:after="140"/><w:pBdr><w:bottom w:val="single" w:sz="6"
  w:color="D4D4D8"/></w:pBdr></w:pPr><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/>
  <w:b/><w:sz w:val="34"/><w:color w:val="0D6E64"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="H2"><w:name w:val="heading 2"/><w:pPr>
  <w:spacing w:before="280" w:after="100"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/>
  <w:color w:val="18181B"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Nota"><w:name w:val="Nota"/><w:pPr>
  <w:pBdr><w:left w:val="single" w:sz="18" w:color="0D6E64" w:space="8"/></w:pBdr>
  <w:ind w:left="220"/><w:spacing w:before="140" w:after="200"/></w:pPr>
  <w:rPr><w:color w:val="3F3F46"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Vineta"><w:name w:val="List Bullet"/><w:pPr>
  <w:ind w:left="360" w:hanging="220"/><w:spacing w:after="80"/></w:pPr></w:style>
</w:styles>'''


def _escapar(t):
    return (str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def _corridas(texto):
    """Parte el texto en tramos normales y en negrita, según los `**`."""
    piezas = []
    for i, tramo in enumerate(re.split(r'\*\*', str(texto))):
        if not tramo:
            continue
        negrita = '<w:rPr><w:b/></w:rPr>' if i % 2 else ''
        piezas.append(f'<w:r>{negrita}<w:t xml:space="preserve">'
                      f'{_escapar(tramo)}</w:t></w:r>')
    return ''.join(piezas)


class Documento:
    def __init__(self, titulo='Documento'):
        self.titulo_doc = titulo
        self.cuerpo = []

    def _parrafo(self, texto, estilo=None):
        pr = f'<w:pPr><w:pStyle w:val="{estilo}"/></w:pPr>' if estilo else ''
        self.cuerpo.append(f'<w:p>{pr}{_corridas(texto)}</w:p>')

    def titulo(self, t):
        self._parrafo(t, 'Titulo')

    def subtitulo(self, t):
        self._parrafo(t, 'Subtitulo')

    def h1(self, t):
        self._parrafo(t, 'H1')

    def h2(self, t):
        self._parrafo(t, 'H2')

    def p(self, t=''):
        self._parrafo(t)

    def nota(self, t):
        self._parrafo(t, 'Nota')

    def punto(self, t):
        self._parrafo('•  ' + str(t), 'Vineta')

    def salto(self):
        self.cuerpo.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    def guardar(self, ruta):
        documento = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>' + ''.join(self.cuerpo) +
            '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1418" w:right="1418" w:bottom="1418" w:left="1418"/>'
            '</w:sectPr></w:body></w:document>')
        with zipfile.ZipFile(ruta, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('[Content_Types].xml', _CONTENT_TYPES)
            z.writestr('_rels/.rels', _RELS)
            z.writestr('word/_rels/document.xml.rels', _DOC_RELS)
            z.writestr('word/styles.xml', _STYLES)
            z.writestr('word/document.xml', documento)
        return ruta
