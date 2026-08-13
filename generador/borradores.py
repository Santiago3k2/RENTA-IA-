# -*- coding: utf-8 -*-
r"""El paso intermedio de la carga: procesar sin comprometer nada todavía.

Solo librería estándar.

Antes, subir la exógena era un solo movimiento: llegaba el archivo y salía la
declaración creada, el cupo gastado y el libro hecho. Con cupo 1, equivocarse
de archivo dejaba a la cuenta atascada y solo el administrador podía sacarla.

Ahora son dos. En el primero se lee y se clasifica el archivo —que es lo caro—
pero **no se crea nada**: el resultado queda aquí, en un borrador que vence
solo. En el segundo, el usuario ve de quién es, de qué año y qué cifras dieron,
responde lo que la exógena no trae, acepta el descargo, y **entonces** se crea
la declaración y se cuenta el cupo.

Por qué guardar el caso ya procesado y no el archivo a secas: para poder
enseñarle al usuario las cifras de verdad antes de que decida. Un «¿está
seguro?» sin datos no evita ni un error.

El borrador guarda el CLIENTE y los TEXTOS —el caso ya clasificado— y deja la
exógena en `borradores/<id>/` del bucket. Al confirmar se arma el libro con eso
y se archiva el original en su sitio definitivo; al cancelar o al vencer, se
borran los dos.
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import cuentas
import db

TABLA = 'borradores'
CAMPOS = ('id,usuario,cliente,textos,exogena_path,nombre_exogena,creado_en,expira_en')

# Cuánto sobrevive un borrador sin confirmar. Dos horas es de sobra para
# revisar unas cifras y llamar al cliente a preguntarle si tiene hipoteca, y lo
# bastante corto para que no se acumulen archivos de gente que se fue.
HORAS_VIGENCIA = 2
PREFIJO = 'borradores'


class ErrorBorrador(Exception):
    """Algo que el usuario hizo mal y puede corregir."""


class Borradores:
    def __init__(self, supabase=None):
        self.s = supabase or db.Supabase.desde_env()

    def crear(self, usuario, cliente, textos, exogena_bytes=None,
              nombre_exogena=None):
        """Guarda el caso procesado. No crea declaración ni gasta cupo."""
        self.limpiar(usuario)
        fila = {
            'usuario': cuentas.normalizar(usuario),
            'cliente': cliente,
            'textos': textos,
            'nombre_exogena': nombre_exogena,
        }
        creado = self.s.insertar(TABLA, fila)[0]
        if exogena_bytes:
            # El archivo va aparte de la fila: en Postgres no se guardan
            # binarios de megabytes, y aquí encima serían de un caso que a lo
            # mejor se cancela en el siguiente clic.
            ruta = f"{PREFIJO}/{creado['id']}/{nombre_exogena or 'exogena.xlsx'}"
            self.s.subir_bytes(db.BUCKET_EXOGENAS, ruta, exogena_bytes)
            creado = self.s.actualizar(TABLA, {'exogena_path': ruta},
                                       id='eq.' + creado['id'])[0]
        return creado

    def buscar(self, ref, usuario):
        """El borrador, solo si es de quien lo pide y no ha vencido."""
        filas = self.s.seleccionar(TABLA, select=CAMPOS, id='eq.' + str(ref),
                                   usuario='eq.' + cuentas.normalizar(usuario))
        if not filas:
            return None
        fila = filas[0]
        vence = cuentas.desde_iso(fila.get('expira_en'))
        if vence and vence <= cuentas.ahora():
            self.borrar(fila)
            return None
        return fila

    def borrar(self, fila):
        """Se lleva la fila y el archivo. Nunca lanza: es limpieza."""
        if not fila:
            return
        try:
            if fila.get('exogena_path'):
                self.s.borrar_objeto(db.BUCKET_EXOGENAS, fila['exogena_path'])
        except Exception:
            pass
        try:
            self.s.borrar(TABLA, id='eq.' + str(fila['id']))
        except Exception:
            pass

    def limpiar(self, usuario=None):
        """Retira los borradores vencidos. Sin tarea programada que mantener:
        se hace al crear uno nuevo, que es cuando importa que no se acumulen."""
        filtros = {'select': CAMPOS, 'expira_en': 'lt.' + cuentas.iso()}
        if usuario:
            filtros['usuario'] = 'eq.' + cuentas.normalizar(usuario)
        try:
            vencidos = self.s.seleccionar(TABLA, **filtros)
        except db.ErrorSupabase:
            return 0
        for fila in vencidos:
            self.borrar(fila)
        return len(vencidos)

    def exogena(self, fila):
        """Los bytes del archivo que subió, para archivarlo al confirmar."""
        if not fila or not fila.get('exogena_path'):
            return None
        return self.s.descargar_bytes(db.BUCKET_EXOGENAS, fila['exogena_path'])
