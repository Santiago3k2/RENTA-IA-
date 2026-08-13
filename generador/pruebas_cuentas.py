# -*- coding: utf-8 -*-
r"""Regresión del sistema de cuentas.

    python pruebas_cuentas.py

Las pruebas de cifrado y validación no tocan la red. Las demás sí trabajan
contra Supabase, porque lo que hay que comprobar es justamente que la fila se
escriba, el bloqueo persista y el borrado se lleve lo que tiene que llevarse —
un simulacro en memoria no probaría nada de eso. Todo lo que crean lo crean
bajo un usuario de un solo uso («zzprueba<azar>») y lo borran al terminar,
también si la prueba falla.

Debe decir «TODAS LAS PRUEBAS PASAN» tras cualquier cambio a cuentas.py.
"""
import os
import secrets
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import cuentas
import db

fallos = []
hechas = 0


def revisar(condicion, titulo):
    global hechas
    hechas += 1
    if condicion:
        print(f'  ok   {titulo}')
    else:
        print(f'  FALLA {titulo}')
        fallos.append(titulo)


def revisar_error(fn, fragmento, titulo):
    """La operación debe rechazarse, y el motivo debe mencionar `fragmento`."""
    global hechas
    hechas += 1
    try:
        fn()
    except cuentas.ErrorCuenta as ex:
        if fragmento.lower() in str(ex).lower():
            print(f'  ok   {titulo}')
            return
        print(f'  FALLA {titulo} — se rechazó, pero dijo: {ex}')
    except Exception as ex:
        print(f'  FALLA {titulo} — error inesperado: {ex}')
    else:
        print(f'  FALLA {titulo} — no se rechazó')
    fallos.append(titulo)


# ── sin red ─────────────────────────────────────────────────────────────
def probar_cifrado():
    print('\nCifrado de contraseñas')
    h = cuentas.cifrar('una frase larga de prueba')
    revisar(h.startswith('pbkdf2_sha256$600000$'), 'el formato guardado es el esperado')
    revisar('una frase larga' not in h, 'la contraseña no aparece en el texto guardado')
    revisar(cuentas.comprobar('una frase larga de prueba', h), 'la contraseña correcta valida')
    revisar(not cuentas.comprobar('una frase larga de prueb', h), 'una letra menos no valida')
    revisar(cuentas.cifrar('x' * 12) != cuentas.cifrar('x' * 12),
            'dos cuentas con la misma clave dan hashes distintos (sal propia)')
    revisar(not cuentas.comprobar('lo que sea', ''), 'un hash vacío no valida nada')
    revisar(not cuentas.comprobar('lo que sea', 'basura$sin$formato'),
            'un hash corrupto no revienta: devuelve falso')
    revisar(cuentas._iteraciones_de(h) == 600000, 'se lee el costo con que se cifró')


def probar_validaciones():
    print('\nValidaciones')
    revisar(cuentas.normalizar('  Prueba Piloto 2026 ') == 'pruebapiloto2026',
            'el usuario se normaliza sin espacios y en minúsculas')
    revisar(cuentas.normalizar_correo('  A@B.CO ') == 'a@b.co', 'el correo se normaliza')
    revisar(cuentas.normalizar_correo('   ') is None,
            'un correo vacío queda en None y no choca con la unicidad')

    revisar(cuentas.validar_usuario('ab'), 'un usuario de dos letras se rechaza')
    revisar(cuentas.validar_usuario('admin'), 'un usuario reservado se rechaza')
    revisar(cuentas.validar_usuario('juan pérez'), 'un usuario con tilde o espacio se rechaza')
    revisar(cuentas.validar_usuario('.juan'), 'un usuario que empieza en punto se rechaza')
    revisar(cuentas.validar_usuario('juan.perez_1') is None, 'un usuario correcto pasa')

    revisar(cuentas.validar_clave('corta'), 'una clave corta se rechaza')
    revisar(cuentas.validar_clave('password'), 'una clave de diccionario se rechaza')
    revisar(cuentas.validar_clave('aaaaaaaaaaaa'), 'una clave de un solo carácter se rechaza')
    revisar(cuentas.validar_clave('juanperez2026x', usuario='juanperez'),
            'la clave no puede contener el usuario')
    revisar(cuentas.validar_clave('mesa verde 2026 sol', usuario='juanperez') is None,
            'una frase larga pasa sin exigir símbolos raros')

    revisar(cuentas.validar_correo('sin-arroba') is not None, 'un correo sin @ se rechaza')
    revisar(cuentas.validar_correo('a@b.co') is None, 'un correo válido pasa')

    revisar(cuentas.desde_iso('2026-07-29T19:23:08.901+00:00') is not None,
            'se lee la marca de tiempo de Postgres')
    revisar(cuentas.desde_iso('2026-07-29T19:23:08.901234567Z') is not None,
            'se leen los microsegundos de más de seis cifras')
    revisar(cuentas.desde_iso(None) is None, 'una fecha vacía no revienta')

    temporal = cuentas.clave_temporal()
    revisar(cuentas.validar_clave(temporal) is None,
            'la clave temporal que genera el sistema pasa sus propias reglas')


# ── contra Supabase ─────────────────────────────────────────────────────
def probar_ciclo(c):
    print('\nCiclo de vida de una cuenta')
    u = 'zzprueba' + secrets.token_hex(4)
    clave = 'colina lejana 24 marzo'
    creada = c.crear(u, 'Persona De Ensayo', clave, correo=u + '@ejemplo.co',
                     rol='cliente', cupo=2, creado_por='pruebas')
    revisar(creada['usuario'] == u, 'la cuenta se crea')
    revisar(creada['cupo'] == 2, 'el cupo queda escrito')

    revisar_error(lambda: c.crear(u, 'Otro Nombre', 'muralla lejana 88'),
                  'ya está tomado', 'no se puede repetir el nombre de usuario')
    revisar_error(lambda: c.crear('zzp' + secrets.token_hex(3), 'Otro Nombre',
                                  'muralla lejana 88', correo=u + '@ejemplo.co'),
                  'ese correo', 'no se puede repetir el correo')
    revisar_error(lambda: c.crear('zzp' + secrets.token_hex(3), 'Otro Nombre',
                                  'corta'),
                  'al menos', 'no se puede crear con una clave corta')

    fila, error = c.autenticar(u, clave)
    revisar(fila and not error, 'entra con la contraseña correcta')
    revisar(fila and 'clave_hash' not in fila,
            'la fila que se devuelve no lleva el hash de la contraseña')

    fila, error = c.autenticar(u, clave + 'x')
    revisar(fila is None and 'incorrect' in (error or ''), 'no entra con la contraseña errada')

    fila, error = c.autenticar('zznadie' + secrets.token_hex(3), 'lo que sea')
    revisar(error == 'Usuario o contraseña incorrectos.',
            'un usuario inexistente da el mismo mensaje que una clave errada')

    return u, creada, clave


def probar_estado(c, u, creada, clave):
    print('\nEstado, rol y cupo')
    c.cambiar_estado(creada['id'], 'inhabilitado', por='pruebas')
    fila, error = c.autenticar(u, clave)
    revisar(fila is None and 'inhabilitada' in (error or ''),
            'una cuenta inhabilitada no entra ni con la contraseña buena')

    fila, error = c.autenticar(u, clave + 'x')
    revisar('incorrect' in (error or ''),
            'a quien no sabe la clave no se le revela que la cuenta está inhabilitada')

    c.cambiar_estado(creada['id'], 'pendiente', por='pruebas')
    fila, error = c.autenticar(u, clave)
    revisar(fila is None and 'aprobada' in (error or ''), 'una cuenta pendiente no entra')

    c.cambiar_estado(creada['id'], 'activo', por='pruebas')
    fila, _ = c.autenticar(u, clave)
    revisar(bool(fila), 'reactivada, vuelve a entrar')

    antes = c.buscar_id(creada['id'])['sesiones_desde']
    c.cerrar_sesiones(creada['id'], por='pruebas')
    revisar(c.buscar_id(creada['id'])['sesiones_desde'] != antes,
            'cerrar sesiones mueve la marca que invalida las cookies')

    c.cambiar_cupo(creada['id'], 7, por='pruebas')
    revisar(c.buscar_id(creada['id'])['cupo'] == 7, 'el cupo se cambia')
    c.cambiar_cupo(creada['id'], None, por='pruebas')
    revisar(c.buscar_id(creada['id'])['cupo'] is None, 'el cupo se puede quitar')
    revisar_error(lambda: c.cambiar_cupo(creada['id'], -1), 'negativo',
                  'no se admite un cupo negativo')

    c.cambiar_cupo(creada['id'], 3, por='pruebas')
    c.cambiar_rol(creada['id'], 'admin', por='pruebas')
    revisar(c.buscar_id(creada['id'])['cupo'] is None,
            'ascender a administrador quita el cupo: no procesa para terceros')
    c.cambiar_rol(creada['id'], 'cliente', por='pruebas')
    revisar_error(lambda: c.cambiar_rol(creada['id'], 'contador', por='pruebas'),
                  'no existe', 'el rol «contador» ya no se puede asignar')

    revisar(c.cuantas_lleva(u) == 0, 'una cuenta nueva no ha cargado declaraciones')


def probar_claves(c, u, creada, clave):
    print('\nContraseñas')
    revisar_error(lambda: c.cambiar_clave(creada['id'], 'la que no es', 'otra clave larga 99'),
                  'no es correcta', 'cambiar la clave exige la actual')
    revisar_error(lambda: c.cambiar_clave(creada['id'], clave, clave),
                  'distinta', 'la clave nueva no puede ser igual a la vieja')
    revisar_error(lambda: c.cambiar_clave(creada['id'], clave, 'corta'),
                  'al menos', 'la clave nueva pasa por las mismas reglas')

    nueva = 'ribera dorada 31 agosto'
    c.cambiar_clave(creada['id'], clave, nueva, por='pruebas')
    revisar(bool(c.autenticar(u, nueva)[0]), 'entra con la clave nueva')
    revisar(c.autenticar(u, clave)[0] is None, 'la clave vieja deja de servir')

    temporal = c.restablecer_clave(creada['id'], por='pruebas')
    fila, _ = c.autenticar(u, temporal)
    revisar(bool(fila), 'entra con la clave temporal que asignó el administrador')
    revisar(fila and fila['debe_cambiar_clave'] is True,
            'tras un restablecimiento queda marcada para cambiarla')
    return temporal


def probar_bloqueo(c, u, creada):
    print('\nFreno a la fuerza bruta')
    for _ in range(cuentas.FALLOS_ANTES_DE_BLOQUEAR):
        c.autenticar(u, 'no es la clave')
    fila = c.buscar_id(creada['id'])
    revisar(fila['intentos_fallidos'] >= cuentas.FALLOS_ANTES_DE_BLOQUEAR,
            'los intentos fallidos se cuentan y quedan guardados')
    revisar(bool(fila['bloqueado_hasta']),
            f'la cuenta se bloquea a los {cuentas.FALLOS_ANTES_DE_BLOQUEAR} fallos')

    temporal = c.restablecer_clave(creada['id'], por='pruebas')
    _, error = c.autenticar(u, temporal)
    revisar(error is None, 'restablecer la clave levanta el bloqueo')
    revisar(c.buscar_id(creada['id'])['intentos_fallidos'] == 0,
            'entrar bien deja el contador de fallos en cero')


def probar_ultimo_admin(c):
    print('\nEl último administrador')
    admins = c.listar(rol='admin', estado='activo')
    if not admins:
        print('  (no hay administradores todavía: se omite)')
        return
    if len(admins) > 1:
        print(f'  (hay {len(admins)} administradores activos: se omite)')
        return
    unico = admins[0]
    revisar_error(lambda: c.cambiar_estado(unico['id'], 'inhabilitado'), 'único',
                  'no se puede inhabilitar al único administrador')
    revisar_error(lambda: c.cambiar_rol(unico['id'], 'cliente'), 'único',
                  'no se puede degradar al único administrador')
    revisar_error(lambda: c.eliminar(unico['id']), 'único',
                  'no se puede eliminar al único administrador')


def probar_ajustes(c):
    print('\nAjustes globales')
    original = c.ajuste('cupo_por_defecto')
    c.poner_ajuste('cupo_por_defecto', 9, por='pruebas')
    revisar(c.ajuste_int('cupo_por_defecto') == 9, 'un ajuste se escribe y se lee')
    c.poner_ajuste('cupo_por_defecto', original if original is not None else 1, por='pruebas')
    revisar(c.ajuste_bool('_no_existe_', True) is True,
            'un ajuste que no existe devuelve el valor por defecto')
    revisar(c.ajuste_int('mensaje_portada', 5) == 5,
            'un ajuste que no es número devuelve el valor por defecto sin reventar')


def probar_registro(c):
    print('\nRegistro público')
    abierto = c.ajuste('registro_abierto')
    aprobacion = c.ajuste('requiere_aprobacion')
    cupo_previo = c.ajuste('cupo_por_defecto')
    u = 'zzprueba' + secrets.token_hex(4)
    try:
        c.poner_ajuste('registro_abierto', '1', por='pruebas')
        c.poner_ajuste('requiere_aprobacion', '0', por='pruebas')
        c.poner_ajuste('cupo_por_defecto', '2', por='pruebas')
        nueva = c.registrar(u, 'Registro De Ensayo', 'ventana abierta 17 mayo',
                            u + '@ejemplo.co')
        revisar(nueva['rol'] == 'cliente', 'quien se registra queda siempre como cliente')
        revisar(nueva['estado'] == 'activo', 'sin aprobación previa, queda activa')
        revisar(nueva['cupo'] == 2, 'recibe el cupo por defecto de los ajustes')
        c.eliminar(nueva['id'], por='pruebas')

        c.poner_ajuste('requiere_aprobacion', '1', por='pruebas')
        nueva = c.registrar(u, 'Registro De Ensayo', 'ventana abierta 17 mayo',
                            u + '@ejemplo.co')
        revisar(nueva['estado'] == 'pendiente',
                'con aprobación exigida, queda pendiente y no puede entrar')
        c.eliminar(nueva['id'], por='pruebas')

        c.poner_ajuste('registro_abierto', '0', por='pruebas')
        revisar_error(lambda: c.registrar(u, 'Registro De Prueba',
                                          'clave de registro larga', u + '@ejemplo.co'),
                      'cerrado', 'con el registro cerrado, nadie se registra')
    finally:
        c.poner_ajuste('registro_abierto', abierto if abierto is not None else '1')
        c.poner_ajuste('requiere_aprobacion', aprobacion if aprobacion is not None else '0')
        c.poner_ajuste('cupo_por_defecto', cupo_previo if cupo_previo is not None else '1')
        for sobrante in c.listar():
            if sobrante['usuario'] == u:
                c.eliminar(sobrante['id'])


def probar_migracion_heredada(c):
    """El momento más frágil del despliegue: pasar de contraseñas en variables
    de entorno a filas, sin dejar a nadie fuera."""
    print('\nMigración de los usuarios heredados')
    marca = c.ajuste('migracion_heredados')
    u = 'zzheredado' + secrets.token_hex(3)
    try:
        c.poner_ajuste('migracion_heredados', '')
        # Una contraseña que hoy NO pasaría las reglas: la que ya está en uso.
        creadas = c.migrar_heredados({u: {'clave': 'Renta26', 'rol': 'cliente',
                                          'nombre': 'Heredado De Ensayo', 'cupo': 5}})
        fila = c.buscar(u)
        revisar(bool(fila), 'una contraseña heredada débil no impide crear la cuenta')
        revisar(bool(fila) and c.autenticar(u, 'Renta26')[0] is not None,
                'su dueño sigue entrando con la contraseña de siempre')
        revisar(bool(fila) and fila['debe_cambiar_clave'] is True,
                'pero se le exige cambiarla al entrar')
        revisar(bool(fila) and fila['cupo'] == 5, 'conserva el cupo que tenía')

        # Y no vuelve a correr: lo que el administrador borre, borrado queda.
        c.eliminar(fila['id'], por='pruebas')
        c.migrar_heredados({u: {'clave': 'Renta26', 'rol': 'cliente',
                                'nombre': 'Heredado De Ensayo', 'cupo': 5}})
        revisar(c.buscar(u) is None,
                'la migración corre una sola vez: una cuenta eliminada no reaparece')

        revisar(len(creadas) == 1, 'informa cuántas cuentas migró')
    finally:
        sobrante = c.buscar(u)
        if sobrante:
            c.eliminar(sobrante['id'], por='pruebas')
        c.poner_ajuste('migracion_heredados', marca or '1')


def probar_bitacora(c, u):
    print('\nBitácora')
    entradas = c.bitacora(limite=200, usuario=u)
    acciones = {e['accion'] for e in entradas}
    revisar('acceso' in acciones, 'los accesos quedan registrados')
    revisar('acceso_fallido' in acciones, 'los intentos fallidos quedan registrados')
    revisar(any(e['exito'] is False for e in entradas),
            'un intento fallido se marca como tal, no como éxito')
    revisar(all('clave' not in str(e.get('detalle') or '').lower()
                or 'contraseña' in str(e.get('detalle') or '').lower()
                for e in entradas),
            'la bitácora no guarda contraseñas')


def probar_contar(s):
    print('\nConteo por cabecera')
    n = s.contar('declaraciones')
    revisar(isinstance(n, int) and n >= 0, f'contar declaraciones devuelve un entero ({n})')
    revisar(s.contar('declaraciones', creada_por='eq._no_existe_nadie_') == 0,
            'contar con un filtro sin resultados devuelve cero')
    revisar(len(s.seleccionar('declaraciones', select='id')) == n,
            'el conteo por cabecera coincide con traer las filas')


def probar_borrado_sin_filtro(s):
    print('\nBorrado sin filtro')
    global hechas
    hechas += 1
    try:
        s.borrar('usuarios')
    except db.ErrorSupabase:
        print('  ok   un borrado sin filtro se niega en vez de vaciar la tabla')
    else:
        print('  FALLA un borrado sin filtro NO se negó')
        fallos.append('borrado sin filtro')


def main():
    inicio = time.time()
    print('═' * 66)
    print('  RENTA IA — regresión del sistema de cuentas')
    print('═' * 66)

    probar_cifrado()
    probar_validaciones()

    try:
        s = db.Supabase.desde_env()
        c = cuentas.Cuentas(s)
    except db.ErrorSupabase as ex:
        print(f'\nSin conexión a Supabase, se omiten las pruebas de base:\n  {ex}')
        return 1 if fallos else 0

    creada = u = None
    try:
        probar_contar(s)
        probar_borrado_sin_filtro(s)
        u, creada, clave = probar_ciclo(c)
        probar_estado(c, u, creada, clave)
        probar_claves(c, u, creada, clave)
        probar_bloqueo(c, u, creada)
        probar_bitacora(c, u)
        probar_ajustes(c)
        probar_migracion_heredada(c)
        probar_registro(c)
        probar_ultimo_admin(c)
    finally:
        if creada:
            try:
                c.eliminar(creada['id'], por='pruebas', con_declaraciones=True)
                print(f'\nCuenta de prueba «{u}» eliminada.')
            except Exception as ex:
                print(f'\nATENCIÓN: no se pudo borrar la cuenta de prueba «{u}»: {ex}')

    print('\n' + '═' * 66)
    if fallos:
        print(f'  {len(fallos)} PRUEBA(S) FALLAN de {hechas}:')
        for f in fallos:
            print(f'    · {f}')
    else:
        print(f'  TODAS LAS PRUEBAS PASAN ({hechas} comprobaciones, '
              f'{time.time() - inicio:.1f} s)')
    print('═' * 66)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(main())
