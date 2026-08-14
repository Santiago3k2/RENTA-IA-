# -*- coding: utf-8 -*-
r"""Permisos de acceso a la cartera ajena — la regla de privacidad del sistema.

Solo librería estándar, como el resto.

**Nadie ve una declaración que no cargó.** Ni el administrador: él maneja las
cuentas, los cupos y los ajustes, pero las declaraciones de sus usuarios son
datos tributarios de terceros —reserva del art. 583 E.T.— y no los ve por el
hecho de ser dueño de la plataforma.

Para entrar a la cartera de alguien tiene que pedírselo, y ese alguien concede
por un tiempo limitado:

    import db, permisos
    p = permisos.Permisos(db.Supabase.desde_env())
    p.pedir('luisa', 'admin', motivo='revisar el caso que reportó por correo')
    p.conceder('luisa', 'admin', dias=7)     # lo hace luisa desde su cuenta
    p.vigentes_para('admin')                 # ['luisa']

Tres decisiones que conviene no deshacer sin pensarlo:

  · **La caducidad se comprueba al leer**, no con una tarea programada. En
    funciones sin estado no hay quién corra la tarea, y un permiso que caduca
    «cuando alguien se acuerde» no es un permiso temporal.

  · **Una fila por pareja (usuario, solicitante).** Pedir otra vez sobre una
    denegada la revive como pendiente; eso es a propósito, porque negarse hoy
    no debería impedir que se lo vuelvan a pedir mañana con otro motivo.

  · **Revocar es inmediato.** No hay caché: cada petición del sitio recalcula
    a quién ve el usuario que la hizo, igual que ya se relee su cuenta.

Desde la consola, que es la puerta de atrás para cuando haga falta habilitarlo
sin que el dueño esté delante:

    python permisos.py --ver
    python permisos.py --conceder luisa --a admin --dias 7
    python permisos.py --revocar  luisa --a admin
"""
import datetime
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import cuentas
import db

TABLA = 'permisos'
CAMPOS = ('id,usuario,solicitante,estado,motivo,solicitado_en,respondido_en,'
          'expira_en')

# Lo que el dueño puede conceder desde la franja de su bandeja. Deliberadamente
# corto: un permiso de acceso a declaraciones de terceros no debería ser algo
# que se concede «para siempre» y se olvida.
DURACIONES = ((1, '24 horas'), (7, '7 días'), (30, '30 días'))
MAX_DIAS = 90


class ErrorPermiso(Exception):
    """Algo que el usuario hizo mal y puede corregir."""


class Permisos:
    """Los permisos, sobre una conexión a Supabase."""

    def __init__(self, supabase=None):
        self.s = supabase or db.Supabase.desde_env()

    # ── consulta ────────────────────────────────────────────────────
    def entre(self, usuario, solicitante):
        """La fila entre esos dos, o None."""
        filas = self.s.seleccionar(
            TABLA, select=CAMPOS,
            usuario='eq.' + cuentas.normalizar(usuario),
            solicitante='eq.' + cuentas.normalizar(solicitante))
        return filas[0] if filas else None

    @staticmethod
    def vigente(fila):
        """¿Ese permiso sirve ahora mismo?

        Concedido y sin vencer. Un `expira_en` vacío en una fila concedida se
        trata como vencido, no como eterno: si el dato se perdió, lo prudente
        es cerrar la puerta, no dejarla abierta para siempre.
        """
        if not fila or fila.get('estado') != 'concedido':
            return False
        hasta = cuentas.desde_iso(fila.get('expira_en'))
        return bool(hasta and hasta > cuentas.ahora())

    def puede_ver(self, solicitante, usuario):
        """¿`solicitante` puede ver hoy las declaraciones de `usuario`?"""
        if cuentas.normalizar(solicitante) == cuentas.normalizar(usuario):
            return True                       # lo suyo, siempre
        return self.vigente(self.entre(usuario, solicitante))

    def vigentes_para(self, solicitante):
        """Usuarios cuya cartera puede ver hoy `solicitante`. Sin incluirse él."""
        filas = self.s.seleccionar(
            TABLA, select=CAMPOS,
            solicitante='eq.' + cuentas.normalizar(solicitante),
            estado='eq.concedido')
        return sorted(f['usuario'] for f in filas if self.vigente(f))

    def pendientes_de(self, usuario):
        """Solicitudes que ese usuario tiene por responder."""
        return self.s.seleccionar(
            TABLA, select=CAMPOS, usuario='eq.' + cuentas.normalizar(usuario),
            estado='eq.pendiente', order='solicitado_en.desc')

    def concedidos_de(self, usuario):
        """Accesos que ese usuario tiene dados, para que pueda revocarlos.

        Devuelve también los vencidos: que el dueño vea que caducaron es parte
        de saber quién ha entrado a lo suyo.
        """
        filas = self.s.seleccionar(
            TABLA, select=CAMPOS, usuario='eq.' + cuentas.normalizar(usuario),
            estado='eq.concedido', order='expira_en.desc')
        for f in filas:
            f['vigente'] = self.vigente(f)
        return filas

    def todos(self):
        return self.s.seleccionar(TABLA, select=CAMPOS, order='solicitado_en.desc')

    # ── movimientos ─────────────────────────────────────────────────
    def _guardar(self, usuario, solicitante, cambios):
        u, so = cuentas.normalizar(usuario), cuentas.normalizar(solicitante)
        fila = self.entre(u, so)
        if fila:
            devueltas = self.s.actualizar(TABLA, cambios, id='eq.' + str(fila['id']))
            return devueltas[0] if devueltas else fila
        base = {'usuario': u, 'solicitante': so}
        base.update(cambios)
        return self.s.insertar(TABLA, base)[0]

    def pedir(self, usuario, solicitante, motivo=None, por=None, ip=None):
        """El administrador pide acceso a la cartera de `usuario`.

        Si ya hay un permiso vigente no se toca: pedir lo que ya se tiene sería
        reiniciarle el reloj al dueño sin que él lo decida.
        """
        u, so = cuentas.normalizar(usuario), cuentas.normalizar(solicitante)
        if u == so:
            raise ErrorPermiso('No hace falta pedirse permiso a uno mismo.')
        fila = self.entre(u, so)
        if self.vigente(fila):
            raise ErrorPermiso('Ya hay un acceso vigente a esa cartera.')
        fila = self._guardar(u, so, {
            'estado': 'pendiente',
            'motivo': (motivo or '').strip()[:400] or None,
            'solicitado_en': cuentas.iso(),
            'respondido_en': None,
            'expira_en': None,
        })
        self._anotar('permiso_pedido', por or so, objeto=u, ip=ip,
                     detalle=(motivo or '').strip()[:200] or 'sin motivo escrito')
        return fila

    def conceder(self, usuario, solicitante, dias=7, por=None, ip=None):
        """El dueño abre su cartera por un tiempo. Solo él, o la consola."""
        dias = int(dias or 0)
        if dias < 1 or dias > MAX_DIAS:
            raise ErrorPermiso(f'El acceso se concede entre 1 y {MAX_DIAS} días.')
        u, so = cuentas.normalizar(usuario), cuentas.normalizar(solicitante)
        hasta = cuentas.ahora() + datetime.timedelta(days=dias)
        fila = self._guardar(u, so, {
            'estado': 'concedido',
            'respondido_en': cuentas.iso(),
            'expira_en': cuentas.iso(hasta),
        })
        self._anotar('permiso_concedido', por or u, objeto=so, ip=ip,
                     detalle=f'acceso a la cartera de {u} por {dias} día(s), '
                             f'hasta {cuentas.fecha_corta(fila.get("expira_en"))}')
        return fila

    def denegar(self, usuario, solicitante, por=None, ip=None):
        u, so = cuentas.normalizar(usuario), cuentas.normalizar(solicitante)
        fila = self._guardar(u, so, {'estado': 'denegado',
                                     'respondido_en': cuentas.iso(),
                                     'expira_en': None})
        self._anotar('permiso_denegado', por or u, objeto=so, ip=ip,
                     detalle=f'no le abre la cartera de {u}')
        return fila

    def revocar(self, usuario, solicitante, por=None, ip=None):
        u, so = cuentas.normalizar(usuario), cuentas.normalizar(solicitante)
        fila = self.entre(u, so)
        if not fila:
            raise ErrorPermiso('Ese acceso no existe.')
        fila = self._guardar(u, so, {'estado': 'revocado',
                                     'respondido_en': cuentas.iso(),
                                     'expira_en': None})
        self._anotar('permiso_revocado', por or u, objeto=so, ip=ip,
                     detalle=f'se le cierra la cartera de {u}')
        return fila

    def _anotar(self, accion, quien, objeto=None, detalle=None, ip=None):
        """Deja constancia en la bitácora. Nunca lanza."""
        try:
            cuentas.Cuentas(self.s).anotar(accion, quien, objeto=objeto,
                                           detalle=detalle, ip=ip)
        except Exception:
            pass


# ── desde la consola ────────────────────────────────────────────────────
def _imprimir(p):
    filas = p.todos()
    if not filas:
        print('No hay ningún permiso registrado.')
        return
    print(f'{"DUEÑO":20} {"PIDE":20} {"ESTADO":11} VENCE')
    for f in filas:
        marca = '' if f['estado'] != 'concedido' else (
            '  ← vigente' if Permisos.vigente(f) else '  (vencido)')
        print(f'{f["usuario"]:20} {f["solicitante"]:20} {f["estado"]:11} '
              f'{cuentas.fecha_corta(f.get("expira_en"))}{marca}')


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(
        description='Permisos de acceso a la cartera ajena en RENTA IA.')
    ap.add_argument('--ver', action='store_true', help='lista todos los permisos')
    ap.add_argument('--conceder', metavar='USUARIO', help='dueño de la cartera')
    ap.add_argument('--revocar', metavar='USUARIO', help='dueño de la cartera')
    ap.add_argument('--a', metavar='QUIEN', default='admin',
                    help='a quién se le concede o se le revoca (por defecto: admin)')
    ap.add_argument('--dias', type=int, default=7, help='cuántos días dura (por defecto: 7)')
    args = ap.parse_args(argv)

    try:
        p = Permisos()
    except db.ErrorSupabase as ex:
        print('Sin conexión a Supabase: ' + str(ex)[:160])
        return 1

    try:
        if args.conceder:
            f = p.conceder(args.conceder, args.a, args.dias, por='(consola)')
            print(f'Concedido: {args.a} ve la cartera de {args.conceder} '
                  f'hasta {cuentas.fecha_corta(f["expira_en"])}.')
        elif args.revocar:
            p.revocar(args.revocar, args.a, por='(consola)')
            print(f'Revocado: {args.a} ya no ve la cartera de {args.revocar}.')
        else:
            _imprimir(p)
    except (ErrorPermiso, db.ErrorSupabase) as ex:
        print('No se pudo: ' + str(ex))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
