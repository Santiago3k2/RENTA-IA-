# -*- coding: utf-8 -*-
r"""Acceso a Supabase para RENTA IA — solo librería estándar (urllib).

Toda la escritura pasa por la clave de servicio: las tablas tienen RLS activa y
sin políticas, así que nadie más entra. Nunca se expone esta clave al navegador.

    import db
    s = db.Supabase.desde_env()
    s.guardar_caso(calc, libro=ruta_xlsx, exogena=ruta_xlsx_fuente)

Los archivos van a dos buckets privados (`libros`, `exogenas`) y se sirven con
URL firmada de vigencia corta, jamás con enlace público: son datos tributarios
de personas reales.
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import config

BUCKET_LIBROS = 'libros'
BUCKET_EXOGENAS = 'exogenas'
BUCKET_CONSOLIDADOS = 'consolidados'   # módulo RST: facturación electrónica
TIPO_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class ErrorSupabase(Exception):
    """Falla de comunicación con Supabase, ya traducida al español."""


class ErrorPermiso(ErrorSupabase):
    """El usuario no tiene derecho a hacer eso. No es una falla del sistema."""


DUENO_POR_DEFECTO = 'admin'    # lo que sube sincronizar.py desde el escritorio


def carpeta_dueno(usuario):
    """El nombre de la cuenta, seguro como segmento de carpeta del Storage.

    Cada cuenta guarda sus archivos en su propia subcarpeta: dos personas que
    trabajen la misma declaración generan libros con el mismo nombre, y sin
    esto el segundo pisaría el archivo del primero aunque cada uno tenga su
    fila. Se filtra el nombre —aunque al crear la cuenta ya se valida— porque
    una barra colada aquí escribiría en la carpeta de otro.
    """
    limpio = ''.join(c for c in str(usuario or '').lower()
                     if c.isalnum() or c in '._-')
    # Lo que queda en puros puntos ('.', '..') no es un nombre: es la carpeta
    # de arriba. Un usuario válido nunca empieza por punto, pero esto es la
    # última barrera antes de escribir en el Storage.
    return limpio if limpio.strip('.-') else DUENO_POR_DEFECTO


def _traducir(codigo, cuerpo, url):
    if codigo == 401:
        return ('Supabase rechazó la clave (401). Si la acaba de crear o rotar, '
                'espere unos minutos y reintente: la clave tarda en propagarse y '
                'mientras tanto responde 401. Si persiste, la '
                'SUPABASE_SERVICE_ROLE_KEY del .env está revocada, incompleta o '
                'es de otro proyecto; genere una nueva en Project Settings → '
                'API Keys → «Create new secret key».')
    if codigo == 403:
        return ('Supabase respondió 403: la clave no tiene permiso. Debe ser la '
                'clave SECRETA (service role), no la publicable.')
    if codigo == 404:
        return (f'Supabase respondió 404 en {url}. Verifique que el esquema esté '
                'aplicado (db/esquema.sql) y que la URL del proyecto sea la correcta.')
    if codigo == 409 and 'ano_gravable' in (cuerpo or ''):
        # El único choque posible aquí es la llave única vieja, la que no lleva
        # el dueño dentro. Sin este mensaje, el error crudo de Postgres deja al
        # usuario adivinando —y, peor, delata que alguien más tiene ese caso—.
        return ('Falta terminar de actualizar la base: corra una vez el archivo '
                'db\\migracion-copia-por-cuenta.sql en el SQL Editor de Supabase. '
                'Mientras tanto, este caso no se puede guardar.')
    return f'Supabase respondió {codigo}: {cuerpo[:300]}'


class Supabase:
    def __init__(self, url, clave):
        self.url = (url or '').rstrip('/')
        self.clave = clave or ''

    # ── construcción ────────────────────────────────────────────────
    @classmethod
    def desde_env(cls, exigir=True):
        a = config.ajustes()
        fallas = config.revisar(a)
        if exigir and fallas:
            raise ErrorSupabase('Configuración incompleta:\n  · ' + '\n  · '.join(fallas))
        return cls(a.get('SUPABASE_URL'), a.get('SUPABASE_SERVICE_ROLE_KEY'))

    @property
    def configurado(self):
        return bool(self.url and self.clave)

    # ── transporte ──────────────────────────────────────────────────
    def _pedir(self, metodo, ruta, cuerpo=None, cabeceras=None, binario=None,
               tipo='application/json', con_cabeceras=False):
        url = self.url + ruta
        datos = binario if binario is not None else (
            json.dumps(cuerpo, ensure_ascii=False).encode('utf-8') if cuerpo is not None else None)
        cab = {'apikey': self.clave, 'Authorization': 'Bearer ' + self.clave}
        if datos is not None:
            cab['Content-Type'] = tipo
        cab.update(cabeceras or {})
        req = urllib.request.Request(url, data=datos, headers=cab, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                crudo = r.read()
                recibidas = dict(r.headers)
        except urllib.error.HTTPError as ex:
            cuerpo_err = ex.read().decode('utf-8', 'replace')
            raise ErrorSupabase(_traducir(ex.code, cuerpo_err, url)) from None
        except urllib.error.URLError as ex:
            raise ErrorSupabase(f'No se pudo conectar con Supabase: {ex.reason}') from None
        if crudo:
            try:
                salida = json.loads(crudo.decode('utf-8'))
            except ValueError:
                salida = crudo
        else:
            salida = None
        return (salida, recibidas) if con_cabeceras else salida

    # ── tablas ──────────────────────────────────────────────────────
    @staticmethod
    def filtro_dueno(solo_de):
        """Filtro «solo los casos que cargaron estos usuarios».

        Acepta un nombre suelto o una lista, porque desde agosto de 2026 un
        usuario puede ver, además de lo suyo, la cartera de quien le concedió
        permiso temporal.

        `None` significa sin restricción. Una lista **vacía** no significa lo
        mismo: significa «no ve nada», y se traduce a un filtro que no puede
        casar con ninguna fila. Confundir las dos cosas abriría la cartera
        entera al primer descuido.
        """
        if solo_de is None:
            return None
        if isinstance(solo_de, str):
            return 'eq.' + solo_de
        nombres = sorted({str(u) for u in solo_de if u})
        if not nombres:
            return 'in.("")'          # ningún usuario se llama así: no ve nada
        return 'in.(' + ','.join('"%s"' % n.replace('"', '') for n in nombres) + ')'

    def seleccionar(self, tabla, **filtros):
        params = {'select': filtros.pop('select', '*')}
        orden = filtros.pop('order', None)
        if orden:
            params['order'] = orden
        params.update({k: v for k, v in filtros.items()})
        return self._pedir('GET', f'/rest/v1/{tabla}?' + urllib.parse.urlencode(params)) or []

    def insertar(self, tabla, filas, conflicto=None):
        """Inserta o actualiza (upsert) y devuelve las filas resultantes."""
        filas = filas if isinstance(filas, list) else [filas]
        if not filas:
            return []
        ruta = f'/rest/v1/{tabla}'
        prefer = 'return=representation'
        if conflicto:
            ruta += '?on_conflict=' + urllib.parse.quote(conflicto)
            prefer = 'resolution=merge-duplicates,' + prefer
        return self._pedir('POST', ruta, filas, {'Prefer': prefer}) or []

    def actualizar(self, tabla, cambios, **filtros):
        ruta = f'/rest/v1/{tabla}?' + urllib.parse.urlencode(filtros)
        return self._pedir('PATCH', ruta, cambios,
                           {'Prefer': 'return=representation'}) or []

    def borrar(self, tabla, **filtros):
        if not filtros:
            # Un DELETE sin filtro vacía la tabla entera. Es un error de
            # programación tan caro que vale la pena atajarlo aquí.
            raise ErrorSupabase('Borrado sin filtro: se negó por seguridad.')
        ruta = f'/rest/v1/{tabla}?' + urllib.parse.urlencode(filtros)
        return self._pedir('DELETE', ruta, cabeceras={'Prefer': 'return=minimal'})

    def contar(self, tabla, **filtros):
        """Cuántas filas cumplen el filtro, sin traérselas.

        Se pide un rango vacío y se lee el total de la cabecera Content-Range
        («0-0/9»). Traer las filas solo para medir su longitud funciona con
        nueve declaraciones y deja de funcionar con nueve mil.
        """
        params = {'select': 'id'}
        params.update(filtros)
        ruta = f'/rest/v1/{tabla}?' + urllib.parse.urlencode(params)
        _, cabeceras = self._pedir('GET', ruta, con_cabeceras=True, cabeceras={
            'Prefer': 'count=exact', 'Range-Unit': 'items', 'Range': '0-0'})
        rango = ''
        for k, v in cabeceras.items():
            if k.lower() == 'content-range':
                rango = v
                break
        total = rango.partition('/')[2].strip()
        return int(total) if total.isdigit() else 0

    def ping(self):
        """Comprueba credenciales y esquema. Devuelve texto de diagnóstico."""
        self.seleccionar('declaraciones', select='id', limit='1')
        return 'Conexión correcta: las tablas responden con la clave de servicio.'

    # ── almacenamiento ──────────────────────────────────────────────
    def asegurar_buckets(self):
        """Crea los buckets privados si faltan. Idempotente."""
        creados = []
        existentes = {b.get('name') for b in (self._pedir('GET', '/storage/v1/bucket') or [])}
        for nombre in (BUCKET_LIBROS, BUCKET_EXOGENAS, BUCKET_CONSOLIDADOS):
            if nombre in existentes:
                continue
            self._pedir('POST', '/storage/v1/bucket',
                        {'id': nombre, 'name': nombre, 'public': False})
            creados.append(nombre)
        return creados

    def subir_bytes(self, bucket, ruta_destino, contenido, tipo=TIPO_XLSX):
        """Sube (o reemplaza) contenido en memoria; devuelve la ruta en el bucket."""
        destino = urllib.parse.quote(ruta_destino)
        self._pedir('POST', f'/storage/v1/object/{bucket}/{destino}',
                    binario=contenido, tipo=tipo, cabeceras={'x-upsert': 'true'})
        return ruta_destino

    def subir(self, bucket, ruta_destino, ruta_local, tipo=TIPO_XLSX):
        """Sube (o reemplaza) un archivo del disco."""
        with open(ruta_local, 'rb') as f:
            return self.subir_bytes(bucket, ruta_destino, f.read(), tipo)

    def descargar_bytes(self, bucket, ruta_destino):
        """Baja un objeto del bucket. Devuelve bytes, o None si no está.

        Hace falta desde que la carga va en dos pasos: la exógena se guarda en
        un sitio provisional mientras el usuario revisa lo que salió, y al
        confirmar hay que recuperarla para archivarla en su ruta definitiva.
        """
        destino = urllib.parse.quote(ruta_destino)
        try:
            salida = self._pedir('GET', f'/storage/v1/object/{bucket}/{destino}')
        except ErrorSupabase:
            return None
        # `_pedir` intenta leer JSON y devuelve los bytes crudos cuando no lo es
        # —que es siempre, tratándose de un .xlsx—. Un dict aquí significaría un
        # error de Storage disfrazado de respuesta correcta.
        return salida if isinstance(salida, (bytes, bytearray)) else None

    def url_firmada(self, bucket, ruta_destino, segundos=3600):
        """URL temporal de descarga. Vence sola: nunca se publica el bucket."""
        r = self._pedir('POST',
                        f'/storage/v1/object/sign/{bucket}/{urllib.parse.quote(ruta_destino)}',
                        {'expiresIn': segundos})
        firmada = (r or {}).get('signedURL', '')
        # Supabase devuelve la ruta con los espacios del nombre del libro sin
        # codificar; así como viene, la descarga falla.
        ruta, sep, consulta = firmada.partition('?')
        return self.url + '/storage/v1' + urllib.parse.quote(ruta, safe='/') + sep + consulta

    def borrar_objeto(self, bucket, ruta_destino):
        """Borra un archivo del bucket. No se queja si ya no estaba.

        Al eliminar una declaración hay que llevarse el libro y la exógena: son
        datos tributarios de una persona real y dejarlos sueltos en el Storage,
        sin fila que los referencie, es peor que no haber borrado nada.
        """
        if not ruta_destino:
            return False
        destino = urllib.parse.quote(ruta_destino)
        try:
            self._pedir('DELETE', f'/storage/v1/object/{bucket}/{destino}')
            return True
        except ErrorSupabase:
            return False

    # ── el caso completo ────────────────────────────────────────────
    def guardar_caso(self, calc, libro=None, exogena=None, estado=None,
                     creada_por=None, libro_bytes=None, exogena_bytes=None,
                     nombre_libro=None, nombre_exogena=None):
        """Persiste un caso ya calculado. Devuelve la fila de `declaraciones`.

        Los archivos entran por ruta (modo escritorio) o por bytes (funciones
        sin disco). Reemplaza por completo las alertas del caso: son un derivado
        del clasificador, no notas del contador. La revisión humana (estado,
        liberación) sí se conserva: solo se pisa si se pasa `estado`.

        **Cada cuenta tiene su propia copia del caso.** La fila que se toca es
        la de (contribuyente, año, `creada_por`), nunca la de otro: si dos
        personas trabajan la misma declaración, cada una guarda la suya, ninguna
        pisa a la otra y ninguna se entera de que la otra existe. Reprocesar lo
        suyo actualiza su fila; nunca crea una segunda a su nombre.
        """
        C = calc['cliente']
        contribuyente = self.insertar('contribuyentes', {
            'identificacion': str(C['identificacion']).replace('.', '').strip(),
            'nombre': C['nombre'],
            'nombre_titulo': C['nombre_titulo'],
        }, conflicto='identificacion')[0]

        fila = {
            'contribuyente_id': contribuyente['id'],
            'ano_gravable': str(C['ano_gravable']),
            'semaforo': calc['semaforo'],
            'uvt': C.get('uvt'),
            'fuente': C.get('fuente'),
            'n_registros': C.get('registros'),
            'ingresos': int(calc['ingresos']),
            'impuesto': int(calc['impuesto']),
            'saldo': int(calc['saldo']),
            'patrimonio_bruto': int(calc['pat_bruto']),
            'patrimonio_liquido': int(calc['pat_liquido']),
            'retenciones': int(calc['retenciones']),
            'datos': C,
            'topes_dian': calc['topes_dian'],
            'difs_topes': calc['difs_topes'],
        }
        if estado:
            fila['estado'] = estado

        # El dueño va SIEMPRE en la fila: es parte de la llave con la que se
        # busca cuál actualizar. Sin él, dos cuentas terminarían peleándose la
        # misma fila.
        dueno = creada_por or DUENO_POR_DEFECTO
        fila['creada_por'] = dueno
        # La suya, si ya la tiene. Lo que hayan cargado otras cuentas del mismo
        # contribuyente y año no se mira ni se toca: no es asunto de esta.
        mias = self.seleccionar(
            'declaraciones', select='id',
            contribuyente_id='eq.' + fila['contribuyente_id'],
            ano_gravable='eq.' + fila['ano_gravable'],
            creada_por='eq.' + dueno)

        # Los archivos van bajo la carpeta de su dueño, para que el libro de una
        # cuenta no sobrescriba el de otra: el nombre que genera el programa es
        # el mismo para el mismo contribuyente.
        carpeta = (f"{fila['contribuyente_id']}/AG{fila['ano_gravable']}"
                   f"/{carpeta_dueno(dueno)}")
        if libro_bytes is not None:
            fila['libro_path'] = self.subir_bytes(
                BUCKET_LIBROS, f'{carpeta}/{nombre_libro or "libro.xlsx"}', libro_bytes)
        elif libro and os.path.isfile(libro):
            fila['libro_path'] = self.subir(
                BUCKET_LIBROS, f'{carpeta}/{os.path.basename(libro)}', libro)
        if exogena_bytes is not None:
            fila['exogena_path'] = self.subir_bytes(
                BUCKET_EXOGENAS, f'{carpeta}/{nombre_exogena or "exogena.xlsx"}', exogena_bytes)
        elif exogena and os.path.isfile(exogena):
            fila['exogena_path'] = self.subir(
                BUCKET_EXOGENAS, f'{carpeta}/{os.path.basename(exogena)}', exogena)

        # Actualizar la suya o crear una nueva, decidido en Python y no con un
        # `on_conflict`: así el código funciona igual antes y después de correr
        # db\migracion-copia-por-cuenta.sql, y no depende de cómo se llame la
        # restricción en la base.
        hechas = (self.actualizar('declaraciones', fila, id='eq.' + mias[0]['id'])
                  if mias else None)
        decl = hechas[0] if hechas else self.insertar('declaraciones', fila)[0]

        # Las alertas se rehacen enteras: son un derivado del clasificador, no
        # notas del contador. Pero **la revisión humana sí se conserva**: si el
        # contador ya dio por resuelta la alerta A3 y el caso se reprocesa con
        # el archivo corregido, esa marca no puede desaparecer sin más. Se
        # guardan por código antes de borrar y se reponen sobre las nuevas.
        marcas = {}
        for vieja in self.seleccionar('alertas',
                                      select='codigo,resuelta,nota_contador,resuelta_en',
                                      declaracion_id='eq.' + decl['id']):
            if vieja.get('resuelta'):
                marcas[vieja['codigo']] = vieja
        self.borrar('alertas', declaracion_id='eq.' + decl['id'])
        alertas = []
        for a in C.get('alertas', []):
            nueva = {'declaracion_id': decl['id'], 'codigo': a[0], 'severidad': a[1],
                     'hallazgo': a[2], 'detalle': a[3], 'accion': a[4]}
            previa_marca = marcas.get(a[0])
            if previa_marca:
                nueva['resuelta'] = True
                nueva['nota_contador'] = previa_marca.get('nota_contador')
                nueva['resuelta_en'] = previa_marca.get('resuelta_en')
            alertas.append(nueva)
        if alertas:
            self.insertar('alertas', alertas)
        return decl

    def alertas_de(self, declaracion_id):
        """Las alertas guardadas de un caso, con su marca de revisión."""
        return self.seleccionar(
            'alertas',
            select='id,codigo,severidad,hallazgo,detalle,accion,resuelta,'
                   'nota_contador,resuelta_en',
            declaracion_id='eq.' + str(declaracion_id), order='id.asc')

    def marcar_alerta(self, alerta_id, resuelta, nota=None, por=None):
        """Da por resuelta una alerta, o le quita la marca.

        La nota es lo que de verdad sirve dentro de tres meses: «resuelta» sin
        el porqué no le dice nada a quien vuelva al caso —ni al propio contador
        que la marcó—. Se guarda quién y cuándo junto al texto.
        """
        cambios = {'resuelta': bool(resuelta)}
        if resuelta:
            nota = (nota or '').strip()[:500]
            firma = f'{por} · ' if por else ''
            cambios['nota_contador'] = (firma + nota) if nota else (firma + 'sin nota')
            cambios['resuelta_en'] = datetime.datetime.now(
                datetime.timezone.utc).isoformat()
        else:
            cambios['nota_contador'] = None
            cambios['resuelta_en'] = None
        filas = self.actualizar('alertas', cambios, id='eq.' + str(alerta_id))
        return filas[0] if filas else None

    def liberar(self, declaracion_id, por):
        """Marca el caso como liberado. Solo lo hace el contador, nunca el motor."""
        ahora = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return self.actualizar('declaraciones',
                               {'estado': 'liberada', 'liberada_por': por,
                                'liberada_en': ahora},
                               id='eq.' + str(declaracion_id))

    def cambiar_estado(self, declaracion_id, estado, por=None):
        """Mueve el caso por el flujo de revisión: borrador → en_revision → liberada."""
        if estado not in ('borrador', 'en_revision', 'liberada'):
            raise ErrorSupabase(f'Estado desconocido: {estado}')
        if estado == 'liberada':
            return self.liberar(declaracion_id, por)
        return self.actualizar('declaraciones',
                               {'estado': estado, 'liberada_en': None,
                                'liberada_por': None},
                               id='eq.' + str(declaracion_id))

    def eliminar_declaracion(self, declaracion_id):
        """Borra el caso entero: fila, alertas, libro y exógena.

        Devuelve lo que borró (para dejarlo escrito en la bitácora) o None si
        ya no estaba. Las alertas se van solas por la cascada de la clave
        foránea; los archivos del Storage no, hay que ir por ellos.

        Si el contribuyente se queda sin ninguna declaración, también se
        elimina: su nombre y su cédula están sujetos a reserva y no tiene
        sentido conservarlos sin un caso al que pertenezcan.
        """
        filas = self.seleccionar(
            'declaraciones',
            select='id,ano_gravable,libro_path,exogena_path,creada_por,'
                   'contribuyente_id,contribuyentes(nombre_titulo,identificacion)',
            id='eq.' + str(declaracion_id))
        if not filas:
            return None
        d = filas[0]
        self.borrar_objeto(BUCKET_LIBROS, d.get('libro_path'))
        self.borrar_objeto(BUCKET_EXOGENAS, d.get('exogena_path'))
        self.borrar('declaraciones', id='eq.' + str(declaracion_id))
        if d.get('contribuyente_id') and not self.contar(
                'declaraciones', contribuyente_id='eq.' + d['contribuyente_id']):
            self.borrar('contribuyentes', id='eq.' + d['contribuyente_id'])
        return d


if __name__ == '__main__':
    try:
        s = Supabase.desde_env()
        print(s.ping())
        creados = s.asegurar_buckets()
        print('Buckets creados: ' + ', '.join(creados) if creados
              else 'Buckets `libros` y `exogenas` ya existen.')
    except ErrorSupabase as ex:
        print('✗ ' + str(ex))
        sys.exit(1)
