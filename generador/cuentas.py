# -*- coding: utf-8 -*-
r"""Cuentas de usuario de RENTA IA — registro, acceso, roles, cupos y bitácora.

Solo librería estándar, como el resto del sistema.

Hasta ahora los usuarios eran dos constantes en variables de entorno: cambiar
una contraseña o abrirle acceso a alguien obligaba a desplegar el sitio otra
vez. Aquí cada cuenta es una fila que el administrador maneja desde el panel.

    import cuentas, db
    c = cuentas.Cuentas(db.Supabase.desde_env())
    fila, error = c.autenticar('admin', 'la contraseña')

Tres decisiones que conviene no deshacer sin pensarlo:

  · **La contraseña nunca se guarda.** Se guarda PBKDF2-HMAC-SHA256 con 600.000
    iteraciones y sal propia por cuenta — el número que recomienda OWASP para
    este algoritmo. Cuesta unos 180 ms, que es caro para quien prueba millones
    de claves y despreciable para quien entra una vez.

  · **Al entrar se verifica la contraseña ANTES que el estado de la cuenta.**
    Si se hiciera al revés, cualquiera podría averiguar qué usuarios existen y
    cuáles están inhabilitados sin saber ni una clave.

  · **Las sesiones no viven en una tabla.** Cada cuenta guarda `sesiones_desde`;
    una sesión firmada antes de esa marca deja de valer. Subirla a ahora es
    «cerrar todas las sesiones» de esa cuenta — sin sesiones que almacenar ni
    que limpiar, que es lo que conviene en funciones sin estado.
"""
import base64
import datetime
import hashlib
import hmac
import os
import re
import secrets
import string
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import db

# ── parámetros ──────────────────────────────────────────────────────────
ALGORITMO = 'pbkdf2_sha256'
ITERACIONES = 600_000
LARGO_SAL = 16

# Dos roles y no tres. El rol «contador» existía cuando se pensaba que el
# contador era quien atendía a los usuarios del sitio; hoy el usuario del sitio
# ES el contador, así que un tercer rol solo servía para confundir. Queda
# `cliente` —el que trabaja— y `admin` —el que administra la plataforma y, por
# decisión expresa, NO ve las declaraciones de nadie sin permiso concedido.
ROLES = ('admin', 'cliente')
ESTADOS = ('activo', 'pendiente', 'inhabilitado')

ROL_ET = {
    'admin':   ('Administrador', 'Maneja las cuentas; no ve declaraciones ajenas'),
    'cliente': ('Cliente',       'Ve solo lo que él mismo carga, con cupo'),
}
ESTADO_ET = {
    'activo':       'Activa',
    'pendiente':    'Pendiente de aprobación',
    'inhabilitado': 'Inhabilitada',
}

MIN_CLAVE = 10
MAX_CLAVE = 200          # ni una clave legítima llega ahí; frena el PBKDF2 largo
MIN_USUARIO, MAX_USUARIO = 3, 32

# Tras 5 intentos fallidos la cuenta se bloquea, y el bloqueo se duplica con
# cada fallo nuevo hasta una hora. Al acertar, el contador vuelve a cero.
FALLOS_ANTES_DE_BLOQUEAR = 5
BLOQUEO_BASE_MIN = 5
BLOQUEO_MAX_MIN = 60

# Hash de una contraseña que nadie tiene. Se compara contra él cuando el
# usuario no existe, para que responder «no existe» cueste lo mismo que
# responder «clave errada»: si no, el tiempo de respuesta delata las cuentas.
_HASH_SEÑUELO = None

RESERVADOS = {'admin', 'administrador', 'root', 'soporte', 'sistema', 'renta',
              'rentaia', 'renta-ia', 'contador', 'dian', 'null', 'none',
              'undefined', 'api', 'www', 'test'}

# Las que aparecen de primeras en cualquier diccionario de ataque. No es una
# lista seria de claves filtradas — es el mínimo para que nadie se registre
# con «contraseña» y crea que quedó protegido.
CLAVES_PROHIBIDAS = {
    'contrasena', 'contraseña', 'password', 'passw0rd', '1234567890',
    'contrasena1', 'qwertyuiop', 'administrador', 'bienvenido', 'declaracion',
    'rentaia2026', 'rentaia123', '12345678910', 'colombia123', 'password123',
}


class ErrorCuenta(Exception):
    """Algo que el usuario hizo mal y puede corregir. No es una falla técnica."""


# ── contraseñas ─────────────────────────────────────────────────────────
def cifrar(clave, iteraciones=ITERACIONES):
    """Deriva la contraseña. Devuelve 'algoritmo$iteraciones$sal$hash'.

    El número de iteraciones va dentro del texto guardado a propósito: el día
    que haya que subirlo, las claves viejas siguen validando con el suyo y se
    recifran solas la próxima vez que su dueño entre (ver `autenticar`).
    """
    if not isinstance(clave, str) or not clave:
        raise ErrorCuenta('La contraseña no puede estar vacía.')
    sal = secrets.token_bytes(LARGO_SAL)
    bruto = hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), sal, iteraciones)
    return '{}${}${}${}'.format(
        ALGORITMO, iteraciones,
        base64.b64encode(sal).decode('ascii'),
        base64.b64encode(bruto).decode('ascii'))


def comprobar(clave, guardado):
    """¿La contraseña corresponde a lo guardado? Nunca lanza: devuelve False."""
    try:
        algoritmo, iteraciones, sal, esperado = (guardado or '').split('$')
        if algoritmo != ALGORITMO:
            return False
        bruto = hashlib.pbkdf2_hmac('sha256', (clave or '').encode('utf-8'),
                                    base64.b64decode(sal), int(iteraciones))
    except Exception:
        return False
    return hmac.compare_digest(base64.b64encode(bruto).decode('ascii'), esperado)


def _iteraciones_de(guardado):
    """Iteraciones con que se cifró esa contraseña; 0 si no se puede leer."""
    try:
        return int((guardado or '').split('$')[1])
    except (IndexError, ValueError):
        return 0


def _quemar_tiempo():
    """Gasta lo mismo que una verificación real, para no delatar por el reloj
    que la cuenta no existe."""
    global _HASH_SEÑUELO
    if _HASH_SEÑUELO is None:
        _HASH_SEÑUELO = cifrar(secrets.token_urlsafe(24))
    comprobar('no importa qué', _HASH_SEÑUELO)


# Sin vocales ni caracteres que se confundan al dictarlos por teléfono: la
# clave temporal se lee en voz alta más veces de las que uno quisiera.
_ALFABETO_TEMPORAL = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def clave_temporal(largo=12):
    """Contraseña provisional legible, para restablecer la de alguien."""
    crudo = ''.join(secrets.choice(_ALFABETO_TEMPORAL) for _ in range(largo))
    return crudo[:4] + '-' + crudo[4:8] + '-' + crudo[8:]


# ── validaciones ────────────────────────────────────────────────────────
def normalizar(usuario):
    """Nombre de usuario canónico: sin espacios y en minúsculas.

    El nombre de usuario no es secreto, así que se perdonan los tropiezos de
    tecleo. La contraseña, en cambio, se respeta tal cual.
    """
    return ''.join((usuario or '').split()).lower()


def normalizar_correo(correo):
    """Correo en minúsculas, o None si viene vacío.

    Vacío tiene que ser None y no '': la columna es única y dos cadenas vacías
    chocarían entre sí.
    """
    c = (correo or '').strip().lower()
    return c or None


_RE_USUARIO = re.compile(r'^[a-z0-9][a-z0-9._-]*$')
_RE_CORREO = re.compile(r'^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$')


def validar_usuario(usuario, reservado_ok=False):
    """Devuelve el problema del nombre de usuario, o None si está bien.

    `reservado_ok` levanta la lista de nombres reservados. La lista existe para
    que nadie se registre solo como «admin» o «soporte» y se haga pasar por el
    sistema; el administrador sí puede crear esas cuentas desde el panel, y el
    propio arranque las necesita.
    """
    u = normalizar(usuario)
    if not u:
        return 'Escriba un nombre de usuario.'
    if len(u) < MIN_USUARIO:
        return f'El usuario debe tener al menos {MIN_USUARIO} caracteres.'
    if len(u) > MAX_USUARIO:
        return f'El usuario no puede pasar de {MAX_USUARIO} caracteres.'
    if not _RE_USUARIO.match(u):
        return ('El usuario solo admite letras sin tilde, números, punto, guion '
                'y guion bajo, y debe empezar por letra o número.')
    if u in RESERVADOS and not reservado_ok:
        return f'El usuario «{u}» está reservado. Elija otro.'
    return None


def validar_correo(correo, obligatorio=True):
    c = normalizar_correo(correo)
    if not c:
        return 'Escriba su correo electrónico.' if obligatorio else None
    if len(c) > 160 or not _RE_CORREO.match(c):
        return 'Ese correo no parece válido.'
    return None


def validar_clave(clave, usuario='', nombre=''):
    """Devuelve el problema de la contraseña, o None si sirve.

    Se pide longitud antes que «una mayúscula y un símbolo»: una frase larga
    resiste mucho más que «Renta*26» y es más fácil de recordar.
    """
    clave = clave or ''
    if len(clave) < MIN_CLAVE:
        return f'La contraseña debe tener al menos {MIN_CLAVE} caracteres.'
    if len(clave) > MAX_CLAVE:
        return f'La contraseña no puede pasar de {MAX_CLAVE} caracteres.'
    if clave.strip() != clave:
        return 'La contraseña no puede empezar ni terminar en espacio.'
    plana = clave.lower()
    if plana in CLAVES_PROHIBIDAS:
        return 'Esa contraseña es de las primeras que prueba cualquier ataque. Elija otra.'
    if usuario and normalizar(usuario) in plana:
        return 'La contraseña no puede contener su nombre de usuario.'
    for palabra in (nombre or '').split():
        if len(palabra) > 3 and palabra.lower() in plana:
            return 'La contraseña no puede contener su nombre.'
    if len(set(clave)) < 5:
        return 'La contraseña repite demasiado los mismos caracteres.'
    return None


def fuerza(clave):
    """Etiqueta orientativa de la contraseña: (0-4, texto). Solo para la vista."""
    clave = clave or ''
    puntos = 0
    if len(clave) >= MIN_CLAVE:
        puntos += 1
    if len(clave) >= 14:
        puntos += 1
    if len(set(clave)) >= 8:
        puntos += 1
    clases = sum(bool(set(clave) & set(g)) for g in
                 (string.ascii_lowercase, string.ascii_uppercase,
                  string.digits, string.punctuation + ' '))
    if clases >= 3:
        puntos += 1
    return puntos, ('Muy débil', 'Débil', 'Aceptable', 'Buena', 'Fuerte')[puntos]


# ── tiempo ──────────────────────────────────────────────────────────────
def ahora():
    return datetime.datetime.now(datetime.timezone.utc)


def iso(momento=None):
    return (momento or ahora()).isoformat()


def desde_iso(texto):
    """Fecha de Postgres a datetime con zona. None si no se puede leer.

    Postgres devuelve la Z o el desfase, y a veces microsegundos de más de seis
    cifras; `fromisoformat` de las versiones viejas se atraganta con ambos.
    """
    if not texto:
        return None
    t = str(texto).strip().replace('Z', '+00:00')
    if '.' in t:                                   # recorta a 6 decimales
        cabeza, _, cola = t.partition('.')
        digitos = ''
        for ch in cola:
            if ch.isdigit():
                digitos += ch
            else:
                break
        t = cabeza + '.' + digitos[:6].ljust(6, '0') + cola[len(digitos):]
    try:
        d = datetime.datetime.fromisoformat(t)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)


def hace_cuanto(texto):
    """«hace 3 horas», para la bitácora y la lista de cuentas."""
    d = desde_iso(texto)
    if not d:
        return '—'
    seg = (ahora() - d).total_seconds()
    if seg < 60:
        return 'hace un momento'
    if seg < 3600:
        m = int(seg // 60)
        return f'hace {m} minuto{"s" if m != 1 else ""}'
    if seg < 86400:
        h = int(seg // 3600)
        return f'hace {h} hora{"s" if h != 1 else ""}'
    dias = int(seg // 86400)
    if dias < 31:
        return f'hace {dias} día{"s" if dias != 1 else ""}'
    meses = dias // 30
    return f'hace {meses} mes{"es" if meses != 1 else ""}'


def fecha_corta(texto):
    d = desde_iso(texto)
    return d.strftime('%d/%m/%Y %H:%M') if d else '—'


# ── el gestor ───────────────────────────────────────────────────────────
CAMPOS = ('id,usuario,nombre,correo,telefono,rol,estado,cupo,debe_cambiar_clave,'
          'sesiones_desde,intentos_fallidos,bloqueado_hasta,ultimo_acceso,'
          'creado_en,creado_por,notas')


class Cuentas:
    """Todo lo que se hace con las cuentas, sobre una conexión a Supabase."""

    def __init__(self, supabase=None):
        self.s = supabase or db.Supabase.desde_env()

    # ── consulta ────────────────────────────────────────────────────
    def buscar(self, usuario, con_hash=False):
        u = normalizar(usuario)
        if not u:
            return None
        campos = CAMPOS + (',clave_hash' if con_hash else '')
        filas = self.s.seleccionar('usuarios', select=campos, usuario='eq.' + u)
        return filas[0] if filas else None

    def buscar_id(self, id_usuario, con_hash=False):
        if not id_usuario:
            return None
        campos = CAMPOS + (',clave_hash' if con_hash else '')
        filas = self.s.seleccionar('usuarios', select=campos,
                                   id='eq.' + str(id_usuario))
        return filas[0] if filas else None

    def por_correo(self, correo):
        c = normalizar_correo(correo)
        if not c:
            return None
        filas = self.s.seleccionar('usuarios', select=CAMPOS, correo='eq.' + c)
        return filas[0] if filas else None

    def listar(self, estado=None, rol=None):
        filtros = {'select': CAMPOS, 'order': 'creado_en.desc'}
        if estado:
            filtros['estado'] = 'eq.' + estado
        if rol:
            filtros['rol'] = 'eq.' + rol
        return self.s.seleccionar('usuarios', **filtros)

    def cuantos_admin(self, excepto=None):
        """Administradores activos. Impide quedarse sin nadie que mande."""
        filas = self.s.seleccionar('usuarios', select='id', rol='eq.admin',
                                   estado='eq.activo')
        return len([f for f in filas if str(f['id']) != str(excepto or '')])

    # ── alta ────────────────────────────────────────────────────────
    def crear(self, usuario, nombre, clave, correo=None, rol='cliente',
              estado='activo', cupo=None, creado_por=None, telefono=None,
              notas=None, debe_cambiar_clave=False, reservado_ok=False,
              exigir_clave_fuerte=True):
        """Crea una cuenta ya validada. Lanza ErrorCuenta con el motivo exacto.

        `exigir_clave_fuerte=False` es solo para las cuentas de arranque, cuya
        contraseña ya existía antes que estas reglas y su dueño ya la usa. Se
        acepta tal cual y se le marca el cambio obligatorio: rechazarla dejaría
        al administrador fuera de su propio sitio, que es peor remedio que la
        enfermedad.
        """
        u = normalizar(usuario)
        problema_clave = validar_clave(clave, u, nombre)
        if problema_clave and not exigir_clave_fuerte:
            if not clave:
                raise ErrorCuenta('La contraseña no puede estar vacía.')
            debe_cambiar_clave = True
            problema_clave = None
        for problema in (validar_usuario(u, reservado_ok),
                         problema_clave,
                         validar_correo(correo, obligatorio=False)):
            if problema:
                raise ErrorCuenta(problema)
        nombre = (nombre or '').strip()
        if len(nombre) < 3:
            raise ErrorCuenta('Escriba el nombre completo de la persona.')
        if rol not in ROLES:
            raise ErrorCuenta('Ese rol no existe.')
        if estado not in ESTADOS:
            raise ErrorCuenta('Ese estado no existe.')

        if self.buscar(u):
            raise ErrorCuenta(f'El usuario «{u}» ya está tomado. Elija otro.')
        correo_n = normalizar_correo(correo)
        if correo_n and self.por_correo(correo_n):
            raise ErrorCuenta('Ya hay una cuenta registrada con ese correo.')

        fila = {
            'usuario': u,
            'nombre': nombre[:120],
            'correo': correo_n,
            'telefono': (telefono or '').strip()[:40] or None,
            'clave_hash': cifrar(clave),
            'rol': rol,
            'estado': estado,
            'cupo': cupo,
            'debe_cambiar_clave': bool(debe_cambiar_clave),
            # Se escribe desde aquí y no se deja al `default now()` de la base:
            # la validez de una sesión se decide comparando esta marca contra el
            # reloj del servidor web, y si los dos relojes no son el mismo, una
            # cuenta recién creada podría rechazar el primer acceso de su dueño.
            'sesiones_desde': iso(),
            'creado_por': creado_por,
            'notas': notas,
        }
        creada = self.s.insertar('usuarios', fila)[0]
        self.anotar('cuenta_creada', creado_por, objeto=u,
                    detalle=f'rol {rol} · estado {estado} · '
                            f'cupo {"sin límite" if cupo is None else cupo}')
        return creada

    def registrar(self, usuario, nombre, clave, correo, telefono=None, ip=None):
        """Alta pública desde la pantalla de acceso.

        El rol y el cupo NO se aceptan del formulario: los pone el sistema
        según los ajustes. Si vinieran del navegador, cualquiera se registraría
        como administrador con cupo infinito.
        """
        if self.ajuste_bool('registro_abierto', True) is False:
            raise ErrorCuenta('El registro de cuentas nuevas está cerrado en este '
                              'momento. Escriba al administrador para pedir acceso.')
        aprobar = self.ajuste_bool('requiere_aprobacion', False)
        problema = validar_correo(correo, obligatorio=True)
        if problema:
            raise ErrorCuenta(problema)
        creada = self.crear(usuario, nombre, clave, correo=correo,
                            rol='cliente',
                            estado='pendiente' if aprobar else 'activo',
                            cupo=self.ajuste_int('cupo_por_defecto', 1),
                            creado_por='(registro)', telefono=telefono)
        self.anotar('registro', creada['usuario'], rol='cliente', ip=ip,
                    objeto=creada['usuario'],
                    detalle='queda pendiente de aprobación' if aprobar
                            else 'queda activa')
        return creada

    def asegurar_admin(self, usuario, clave, nombre='Administrador'):
        """Crea el primer administrador si todavía no hay ninguno.

        Es el seguro contra quedarse fuera: mientras la variable de entorno con
        la contraseña del administrador esté puesta, el sitio siempre tiene por
        dónde entrar aunque la tabla esté vacía. No toca una cuenta existente:
        si ya hay admin, esto no hace nada.
        """
        if not clave:
            return None
        existente = self.buscar(usuario)
        if existente:
            return existente
        if self.cuantos_admin():
            return None
        return self.crear(usuario, nombre, clave, rol='admin', estado='activo',
                          cupo=None, creado_por='(arranque)', reservado_ok=True,
                          exigir_clave_fuerte=False,
                          notas='Creada automáticamente al arrancar el sitio, '
                                'desde RENTA_IA_CLAVE_ADMIN.')

    def migrar_heredados(self, definiciones):
        """Trae a la tabla los usuarios que vivían en variables de entorno.

        Corre **una sola vez**, y queda anotado en los ajustes que ya corrió. Si
        fuera un respaldo permanente, una cuenta que el administrador elimine
        reaparecería sola en el siguiente acceso — que es exactamente lo
        contrario de lo que él pidió al eliminarla.

        `definiciones` es {usuario: {'clave', 'nombre', 'rol', 'cupo'}}.
        """
        if self.ajuste('migracion_heredados'):
            return []
        creadas, quedaron_pendientes = [], False
        for usuario, d in definiciones.items():
            if not d.get('clave') or self.buscar(usuario):
                continue
            try:
                creadas.append(self.crear(
                    usuario, d.get('nombre') or usuario, d['clave'],
                    rol=d.get('rol', 'cliente'), estado='activo',
                    cupo=d.get('cupo'), creado_por='(migración)', reservado_ok=True,
                    exigir_clave_fuerte=False,
                    notas='Migrada desde las variables de entorno, donde vivía '
                          'antes de que existiera la tabla de usuarios.'))
            except (ErrorCuenta, db.ErrorSupabase):
                # Que no se dé por hecha una migración que no terminó: el
                # próximo acceso la reintenta.
                quedaron_pendientes = True
        if not quedaron_pendientes:
            self.poner_ajuste('migracion_heredados', '1', por='(migración)')
        return creadas

    def migrar_rol_contador(self):
        """Retira el rol «contador», que dejó de existir (ver ROLES).

        Hace dos cosas, y la segunda es la que de verdad importa:

        1. Las cuentas con ese rol pasan a «cliente» **conservando su cupo tal
           como estaba** —lo tenían en None, o sea sin límite—, porque quitarles
           el acceso ilimitado sería un cambio que nadie pidió.

        2. Los casos que subió el equipo de escritorio quedaron a nombre de una
           cuenta técnica llamada «contador». Ahora que **nadie ve lo que no
           cargó**, esa cuenta inhabilitada los dejaría invisibles para todo el
           mundo. Pasan a nombre del administrador, que es de quien son.

        Corre una sola vez, como `migrar_heredados`: si el administrador después
        le pone cupo a alguien, esto no puede deshacérselo en el próximo acceso.
        """
        if self.ajuste('migracion_roles'):
            return []
        migradas = []
        try:
            antiguos = self.s.seleccionar('usuarios', select='id,usuario,cupo',
                                          rol='eq.contador')
        except db.ErrorSupabase:
            # La restricción de la base ya puede estar migrada y rechazar el
            # valor en la consulta. Sin filas que arreglar, nada que hacer.
            antiguos = []
        try:
            for fila in antiguos:
                self.s.actualizar('usuarios', {'rol': 'cliente'},
                                  id='eq.' + str(fila['id']))
                migradas.append(fila['usuario'])
                self.anotar('cuenta_rol', '(migración)', objeto=fila['usuario'],
                            detalle='contador → cliente; el rol «contador» '
                                    'desapareció y el cupo se conserva')
            # El dueño de los casos del escritorio. Las tablas del RST pueden no
            # existir en una base vieja, así que cada una va por su lado.
            for tabla in ('declaraciones', 'recibos_rst'):
                try:
                    movidas = self.s.actualizar(tabla, {'creada_por': 'admin'},
                                                creada_por='eq.contador')
                    if movidas:
                        self.anotar('migracion_dueno', '(migración)', objeto=tabla,
                                    detalle=f'{len(movidas)} caso(s) del equipo de '
                                            f'escritorio pasan a «admin»')
                except db.ErrorSupabase:
                    pass
        except db.ErrorSupabase:
            return migradas              # se reintenta en el próximo acceso
        self.poner_ajuste('migracion_roles', '1', por='(migración)')
        return migradas

    # ── acceso ──────────────────────────────────────────────────────
    def autenticar(self, usuario, clave, ip=None):
        """Devuelve (fila, None) si entra, o (None, 'motivo en español').

        El orden importa: primero la contraseña, después el estado. Al revés,
        cualquiera podría inventariar qué cuentas existen sin saber ni una clave.
        """
        u = normalizar(usuario)
        fila = self.buscar(u, con_hash=True) if u else None

        if not fila:
            _quemar_tiempo()
            self.anotar('acceso_fallido', u or '(vacío)', ip=ip, exito=False,
                        detalle='el usuario no existe')
            return None, 'Usuario o contraseña incorrectos.'

        bloqueo = desde_iso(fila.get('bloqueado_hasta'))
        if bloqueo and bloqueo > ahora():
            faltan = max(1, int((bloqueo - ahora()).total_seconds() // 60) + 1)
            self.anotar('acceso_bloqueado', u, ip=ip, exito=False,
                        detalle=f'intento durante el bloqueo; faltaban {faltan} min')
            return None, (f'Demasiados intentos fallidos. Vuelva a probar en '
                          f'{faltan} minuto{"s" if faltan != 1 else ""}.')

        if not comprobar(clave, fila.get('clave_hash')):
            self._contar_fallo(fila, ip)
            return None, 'Usuario o contraseña incorrectos.'

        if fila['estado'] == 'pendiente':
            self.anotar('acceso_denegado', u, rol=fila['rol'], ip=ip, exito=False,
                        detalle='cuenta pendiente de aprobación')
            return None, ('Su cuenta está creada pero todavía no ha sido aprobada. '
                          'El administrador la revisa y le avisa por correo.')
        if fila['estado'] == 'inhabilitado':
            self.anotar('acceso_denegado', u, rol=fila['rol'], ip=ip, exito=False,
                        detalle='cuenta inhabilitada')
            return None, ('Su cuenta está inhabilitada. Escriba al administrador '
                          'si cree que es un error.')

        cambios = {'intentos_fallidos': 0, 'bloqueado_hasta': None,
                   'ultimo_acceso': iso()}
        if _iteraciones_de(fila.get('clave_hash')) < ITERACIONES:
            # La única ocasión en que existe la contraseña en claro es esta.
            # Si el costo recomendado subió desde que se guardó, se aprovecha
            # el momento para recifrarla; el dueño no se entera de nada.
            cambios['clave_hash'] = cifrar(clave)
        self.s.actualizar('usuarios', cambios, id='eq.' + fila['id'])
        self.anotar('acceso', u, rol=fila['rol'], ip=ip)
        fila.pop('clave_hash', None)
        return fila, None

    def _contar_fallo(self, fila, ip=None):
        """Suma el intento fallido y bloquea si se pasó de la raya."""
        intentos = int(fila.get('intentos_fallidos') or 0) + 1
        cambios = {'intentos_fallidos': intentos}
        detalle = f'contraseña incorrecta (intento {intentos})'
        if intentos >= FALLOS_ANTES_DE_BLOQUEAR:
            minutos = min(BLOQUEO_BASE_MIN * 2 ** (intentos - FALLOS_ANTES_DE_BLOQUEAR),
                          BLOQUEO_MAX_MIN)
            cambios['bloqueado_hasta'] = iso(
                ahora() + datetime.timedelta(minutes=minutos))
            detalle += f'; cuenta bloqueada {minutos} min'
        try:
            self.s.actualizar('usuarios', cambios, id='eq.' + fila['id'])
        except db.ErrorSupabase:
            pass                      # que no se caiga el acceso por la cuenta
        self.anotar('acceso_fallido', fila['usuario'], rol=fila.get('rol'),
                    ip=ip, exito=False, detalle=detalle)

    # ── modificación ────────────────────────────────────────────────
    def _actualizar(self, id_usuario, cambios):
        filas = self.s.actualizar('usuarios', cambios, id='eq.' + str(id_usuario))
        return filas[0] if filas else None

    def cambiar_estado(self, id_usuario, estado, por=None):
        if estado not in ESTADOS:
            raise ErrorCuenta('Ese estado no existe.')
        fila = self.buscar_id(id_usuario)
        if not fila:
            raise ErrorCuenta('Esa cuenta ya no existe.')
        if (estado != 'activo' and fila['rol'] == 'admin'
                and fila['estado'] == 'activo' and not self.cuantos_admin(excepto=id_usuario)):
            raise ErrorCuenta('No puede inhabilitar al único administrador activo: '
                              'el sitio se quedaría sin quien lo maneje. Cree o '
                              'active otro administrador primero.')
        cambios = {'estado': estado}
        if estado != 'activo':
            # Inhabilitar tiene que echar de una vez a quien esté dentro.
            cambios['sesiones_desde'] = iso()
        if estado == 'activo':
            cambios.update({'intentos_fallidos': 0, 'bloqueado_hasta': None})
        actualizada = self._actualizar(id_usuario, cambios)
        self.anotar('cuenta_' + ('activada' if estado == 'activo' else
                                 'inhabilitada' if estado == 'inhabilitado'
                                 else 'a_pendiente'),
                    por, objeto=fila['usuario'], detalle=f'estado → {estado}')
        return actualizada

    def cambiar_rol(self, id_usuario, rol, por=None):
        if rol not in ROLES:
            raise ErrorCuenta('Ese rol no existe.')
        fila = self.buscar_id(id_usuario)
        if not fila:
            raise ErrorCuenta('Esa cuenta ya no existe.')
        if (fila['rol'] == 'admin' and rol != 'admin'
                and not self.cuantos_admin(excepto=id_usuario)):
            raise ErrorCuenta('No puede quitarle el rol al único administrador activo. '
                              'Nombre otro administrador primero.')
        # El administrador no procesa declaraciones para clientes: no se le mide
        # cupo. El cliente sí, y ese cupo es lo que se vende.
        cambios = {'rol': rol}
        if rol == 'admin':
            cambios['cupo'] = None
        actualizada = self._actualizar(id_usuario, cambios)
        self.anotar('cuenta_rol', por, objeto=fila['usuario'],
                    detalle=f'{fila["rol"]} → {rol}')
        return actualizada

    def cambiar_cupo(self, id_usuario, cupo, por=None):
        """`cupo` None = sin límite. Es la palanca principal del panel."""
        fila = self.buscar_id(id_usuario)
        if not fila:
            raise ErrorCuenta('Esa cuenta ya no existe.')
        if cupo is not None:
            cupo = int(cupo)
            if cupo < 0:
                raise ErrorCuenta('El cupo no puede ser negativo.')
            if cupo > 100000:
                raise ErrorCuenta('Ese cupo no es razonable. Déjelo sin límite.')
        actualizada = self._actualizar(id_usuario, {'cupo': cupo})
        self.anotar('cuenta_cupo', por, objeto=fila['usuario'],
                    detalle=f'{"sin límite" if fila["cupo"] is None else fila["cupo"]}'
                            f' → {"sin límite" if cupo is None else cupo}')
        return actualizada

    def editar(self, id_usuario, nombre=None, correo=None, telefono=None,
               notas=None, por=None):
        fila = self.buscar_id(id_usuario)
        if not fila:
            raise ErrorCuenta('Esa cuenta ya no existe.')
        cambios = {}
        if nombre is not None:
            nombre = nombre.strip()
            if len(nombre) < 3:
                raise ErrorCuenta('Escriba el nombre completo de la persona.')
            cambios['nombre'] = nombre[:120]
        if correo is not None:
            problema = validar_correo(correo, obligatorio=False)
            if problema:
                raise ErrorCuenta(problema)
            c = normalizar_correo(correo)
            otra = self.por_correo(c) if c else None
            if otra and str(otra['id']) != str(id_usuario):
                raise ErrorCuenta('Ya hay otra cuenta registrada con ese correo.')
            cambios['correo'] = c
        if telefono is not None:
            cambios['telefono'] = telefono.strip()[:40] or None
        if notas is not None:
            cambios['notas'] = notas.strip()[:1000] or None
        if not cambios:
            return fila
        actualizada = self._actualizar(id_usuario, cambios)
        self.anotar('cuenta_editada', por, objeto=fila['usuario'],
                    detalle=', '.join(sorted(cambios)))
        return actualizada

    def cambiar_clave(self, id_usuario, clave_actual, clave_nueva, por=None):
        """Cambio hecho por el propio dueño: exige la contraseña vigente."""
        fila = self.buscar_id(id_usuario, con_hash=True)
        if not fila:
            raise ErrorCuenta('Esa cuenta ya no existe.')
        if not comprobar(clave_actual, fila.get('clave_hash')):
            self.anotar('clave_cambio_fallido', fila['usuario'], exito=False,
                        detalle='la contraseña actual no coincide')
            raise ErrorCuenta('La contraseña actual no es correcta.')
        if clave_actual == clave_nueva:
            raise ErrorCuenta('La contraseña nueva debe ser distinta de la actual.')
        problema = validar_clave(clave_nueva, fila['usuario'], fila['nombre'])
        if problema:
            raise ErrorCuenta(problema)
        # sesiones_desde: cambiar la clave cierra las sesiones abiertas en otros
        # equipos, que es justo lo que se espera al cambiarla porque se filtró.
        self._actualizar(id_usuario, {'clave_hash': cifrar(clave_nueva),
                                      'debe_cambiar_clave': False,
                                      'sesiones_desde': iso()})
        self.anotar('clave_cambiada', por or fila['usuario'], objeto=fila['usuario'])
        return True

    def restablecer_clave(self, id_usuario, por=None, clave=None):
        """El administrador asigna una contraseña provisional.

        Devuelve la contraseña en claro UNA sola vez, para que el admin se la
        entregue a su dueño. No se guarda en ninguna parte: al entrar, el
        sistema obliga a cambiarla.
        """
        fila = self.buscar_id(id_usuario)
        if not fila:
            raise ErrorCuenta('Esa cuenta ya no existe.')
        nueva = clave or clave_temporal()
        problema = validar_clave(nueva, fila['usuario'], fila['nombre'])
        if problema:
            raise ErrorCuenta(problema)
        self._actualizar(id_usuario, {'clave_hash': cifrar(nueva),
                                      'debe_cambiar_clave': True,
                                      'intentos_fallidos': 0,
                                      'bloqueado_hasta': None,
                                      'sesiones_desde': iso()})
        self.anotar('clave_restablecida', por, objeto=fila['usuario'],
                    detalle='se le exigirá cambiarla al entrar')
        return nueva

    def cerrar_sesiones(self, id_usuario, por=None):
        """Invalida toda sesión abierta de esa cuenta, aquí y ahora."""
        fila = self.buscar_id(id_usuario)
        if not fila:
            raise ErrorCuenta('Esa cuenta ya no existe.')
        self._actualizar(id_usuario, {'sesiones_desde': iso()})
        self.anotar('sesiones_cerradas', por, objeto=fila['usuario'])
        return True

    def desbloquear(self, id_usuario, por=None):
        fila = self.buscar_id(id_usuario)
        if not fila:
            raise ErrorCuenta('Esa cuenta ya no existe.')
        self._actualizar(id_usuario, {'intentos_fallidos': 0,
                                      'bloqueado_hasta': None})
        self.anotar('cuenta_desbloqueada', por, objeto=fila['usuario'])
        return True

    def eliminar(self, id_usuario, por=None, con_declaraciones=False):
        """Borra la cuenta. `con_declaraciones` decide qué pasa con sus casos.

        Sin ese argumento las declaraciones se quedan: son papeles de trabajo de
        un contribuyente real, no propiedad de quien las subió. Con él, se
        borran también sus archivos del Storage — para eso está la pantalla de
        confirmación.
        """
        fila = self.buscar_id(id_usuario)
        if not fila:
            raise ErrorCuenta('Esa cuenta ya no existe.')
        if fila['rol'] == 'admin' and not self.cuantos_admin(excepto=id_usuario):
            raise ErrorCuenta('No puede eliminar al único administrador activo. '
                              'Nombre otro administrador antes.')
        borradas = 0
        if con_declaraciones:
            for d in self.s.seleccionar('declaraciones', select='id',
                                        creada_por='eq.' + fila['usuario']):
                self.s.eliminar_declaracion(d['id'])
                borradas += 1
        self.s.borrar('usuarios', id='eq.' + str(id_usuario))
        self.anotar('cuenta_eliminada', por, objeto=fila['usuario'],
                    detalle=(f'con sus {borradas} declaración(es)' if con_declaraciones
                             else 'sus declaraciones se conservaron'))
        return borradas

    # ── cupo ────────────────────────────────────────────────────────
    def cuantas_lleva(self, usuario):
        """Declaraciones que esa cuenta ha cargado — el cupo se mide con esto."""
        return self.s.contar('declaraciones', creada_por='eq.' + normalizar(usuario))

    def cupo_de(self, fila):
        """(usadas, tope) para pintar la barra, o None si no tiene límite."""
        if not fila or fila.get('cupo') is None:
            return None
        return self.cuantas_lleva(fila['usuario']), int(fila['cupo'])

    # ── ajustes globales ────────────────────────────────────────────
    def ajustes(self):
        filas = self.s.seleccionar('ajustes', order='clave.asc')
        return {f['clave']: f for f in filas}

    def ajuste(self, clave, defecto=None):
        filas = self.s.seleccionar('ajustes', select='valor', clave='eq.' + clave)
        return filas[0]['valor'] if filas else defecto

    def ajuste_bool(self, clave, defecto=False):
        v = self.ajuste(clave)
        if v is None:
            return defecto
        return str(v).strip().lower() in ('1', 'si', 'sí', 'true', 'on')

    def ajuste_int(self, clave, defecto=0):
        try:
            return int(str(self.ajuste(clave, defecto)).strip())
        except (TypeError, ValueError):
            return defecto

    def poner_ajuste(self, clave, valor, por=None):
        self.s.insertar('ajustes', {'clave': clave, 'valor': str(valor),
                                    'actualizado_por': por}, conflicto='clave')
        self.anotar('ajuste', por, objeto=clave, detalle=f'→ {valor}')

    # ── bitácora ────────────────────────────────────────────────────
    def anotar(self, accion, usuario=None, rol=None, objeto=None, detalle=None,
               ip=None, exito=True):
        """Deja constancia. Nunca lanza: un fallo aquí no puede tumbar la acción.

        Si la bitácora se cayera y arrastrara consigo el acceso al sitio, el
        remedio sería peor que la enfermedad.
        """
        try:
            self.s.insertar('bitacora', {
                'usuario': (usuario or None) and str(usuario)[:60],
                'rol': rol,
                'accion': str(accion)[:60],
                'objeto': objeto and str(objeto)[:200],
                'detalle': detalle and str(detalle)[:500],
                'ip': ip and str(ip)[:60],
                'exito': bool(exito),
            })
        except Exception:
            pass

    def bitacora(self, limite=100, usuario=None, accion=None):
        filtros = {'order': 'ocurrido_en.desc', 'limit': str(int(limite))}
        if usuario:
            filtros['usuario'] = 'eq.' + normalizar(usuario)
        if accion:
            filtros['accion'] = 'eq.' + accion
        return self.s.seleccionar('bitacora', **filtros)


# ── comprobación rápida desde la consola ────────────────────────────────
if __name__ == '__main__':
    inicio = time.time()
    h = cifrar('una frase larga de prueba')
    print(f'Hash calculado en {int((time.time() - inicio) * 1000)} ms')
    print(f'  {h[:60]}…')
    assert comprobar('una frase larga de prueba', h)
    assert not comprobar('otra cosa', h)
    print('Verificación correcta.')
    try:
        c = Cuentas()
        print(f'Cuentas registradas: {len(c.listar())}')
        for f in c.listar():
            print(f'  {f["usuario"]:20} {f["rol"]:9} {f["estado"]:13} '
                  f'cupo {"—" if f["cupo"] is None else f["cupo"]}')
    except db.ErrorSupabase as ex:
        print('Sin conexión a Supabase: ' + str(ex)[:120])
