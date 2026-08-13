-- ═══════════════════════════════════════════════════════════════════════
--  RENTA IA — esquema de la base de datos (Supabase / Postgres)
--
--  Pegar en el SQL Editor de Supabase y ejecutar.
--  Contiene datos tributarios de personas reales: la RLS queda activada y
--  el acceso pasa por el rol de servicio, nunca por la clave pública.
-- ═══════════════════════════════════════════════════════════════════════

-- ── Contribuyentes ──────────────────────────────────────────────────────
create table if not exists contribuyentes (
  id              uuid primary key default gen_random_uuid(),
  identificacion  text not null unique,          -- '91521021' sin puntos
  tipo_documento  text not null default 'C.C.',
  nombre          text not null,                 -- como lo reporta la DIAN
  nombre_titulo   text not null,                 -- para mostrar
  creado_en       timestamptz not null default now()
);

-- ── Declaraciones: un caso = contribuyente + año gravable ───────────────
create table if not exists declaraciones (
  id                uuid primary key default gen_random_uuid(),
  contribuyente_id  uuid not null references contribuyentes(id) on delete cascade,
  ano_gravable      text not null,

  -- flujo de revisión
  estado            text not null default 'borrador'
                    check (estado in ('borrador','en_revision','liberada')),
  semaforo          text check (semaforo in ('VERDE','AMARILLO','ROJO')),
  liberada_en       timestamptz,
  liberada_por      text,

  -- contexto del reporte
  uvt               integer,
  fuente            text,                        -- 'Exógena DIAN · corte …'
  n_registros       integer,

  -- cifras clave, para pintar la bandeja sin recalcular
  ingresos          bigint,
  impuesto          bigint,
  saldo             bigint,                      -- negativo = saldo a favor
  patrimonio_bruto  bigint,
  patrimonio_liquido bigint,
  retenciones       bigint,

  -- el caso completo tal como lo produjo el clasificador
  datos             jsonb not null,
  topes_dian        jsonb,
  difs_topes        jsonb,

  -- archivos en Supabase Storage
  libro_path        text,
  exogena_path      text,

  -- Quién la cargó. Sostiene tres cosas a la vez: el cupo de esa cuenta, que
  -- un usuario no sobrescriba el caso de otro, y —desde agosto de 2026— QUIÉN
  -- PUEDE VERLA. Nadie ve una declaración que no cargó, salvo con permiso
  -- concedido por su dueño (ver tabla permisos).
  -- 'admin' es el valor por defecto: lo dejan los casos que se suben desde el
  -- equipo de escritorio con sincronizar.py, que son del dueño del sistema.
  creada_por        text not null default 'admin',

  creado_en         timestamptz not null default now(),
  actualizado_en    timestamptz not null default now(),

  unique (contribuyente_id, ano_gravable)
);

create index if not exists idx_decl_contribuyente on declaraciones(contribuyente_id);
create index if not exists idx_decl_estado        on declaraciones(estado);
create index if not exists idx_decl_semaforo      on declaraciones(semaforo);
create index if not exists idx_decl_ano           on declaraciones(ano_gravable);

-- ── Alertas: hallazgos por resolver antes de liberar ────────────────────
create table if not exists alertas (
  id              bigserial primary key,
  declaracion_id  uuid not null references declaraciones(id) on delete cascade,
  codigo          text,                          -- A1, A2, …
  severidad       text check (severidad in
                    ('ALTA','MEDIA','VERIFICADO','NORMATIVO','INFORMATIVO')),
  hallazgo        text,
  detalle         text,
  accion          text,
  resuelta        boolean not null default false,
  nota_contador   text,
  resuelta_en     timestamptz
);

create index if not exists idx_alertas_decl on alertas(declaracion_id);

-- ── Usuarios ────────────────────────────────────────────────────────────
-- Antes eran dos constantes en variables de entorno. Como filas se pueden
-- registrar, inhabilitar, eliminar y darles cupos distintos sin desplegar.
create table if not exists usuarios (
  id                 uuid primary key default gen_random_uuid(),
  usuario            text not null unique,     -- normalizado: minúsculas, sin espacios
  nombre             text not null,
  correo             text unique,              -- siempre en minúsculas
  telefono           text,

  -- pbkdf2_sha256$<iteraciones>$<sal>$<hash>; jamás la contraseña en claro
  clave_hash         text not null,

  -- Dos roles y no tres. «contador» existía cuando se pensaba que el contador
  -- era quien atendía a los usuarios; hoy el usuario ES el contador. El admin
  -- administra la plataforma y NO ve declaraciones ajenas (ver tabla permisos).
  rol                text not null default 'cliente'
                     check (rol in ('admin','cliente')),
  estado             text not null default 'activo'
                     check (estado in ('activo','pendiente','inhabilitado')),

  -- null = sin límite. Declaraciones que la cuenta puede cargar.
  cupo               integer check (cupo is null or cupo >= 0),

  debe_cambiar_clave boolean not null default false,

  -- Toda sesión emitida antes de esta marca deja de valer. Subirla a now()
  -- es «cerrar todas las sesiones» de esa cuenta, sin tabla de sesiones.
  sesiones_desde     timestamptz not null default now(),

  -- freno a la fuerza bruta, persistido porque las funciones no tienen memoria
  intentos_fallidos  integer not null default 0,
  bloqueado_hasta    timestamptz,

  ultimo_acceso      timestamptz,
  creado_en          timestamptz not null default now(),
  creado_por         text,
  notas              text
);

create index if not exists idx_usuarios_estado on usuarios(estado);
create index if not exists idx_usuarios_rol    on usuarios(rol);

-- ── Bitácora ────────────────────────────────────────────────────────────
-- La pantalla de acceso promete que «el acceso queda registrado». Aquí es
-- donde queda. Con datos sujetos a la reserva del art. 583 E.T., saber quién
-- vio o borró qué no es un lujo.
create table if not exists bitacora (
  id           bigserial primary key,
  ocurrido_en  timestamptz not null default now(),
  usuario      text,
  rol          text,
  accion       text not null,       -- 'acceso', 'acceso_fallido', 'cuenta_eliminada', …
  objeto       text,                -- sobre qué recayó
  detalle      text,
  ip           text,
  exito        boolean not null default true
);

create index if not exists idx_bitacora_fecha   on bitacora(ocurrido_en desc);
create index if not exists idx_bitacora_usuario on bitacora(usuario);
create index if not exists idx_bitacora_accion  on bitacora(accion);

-- ── Ajustes globales ────────────────────────────────────────────────────
-- Lo que el administrador cambia sin volver a desplegar.
create table if not exists ajustes (
  clave            text primary key,
  valor            text,
  descripcion      text,
  actualizado_en   timestamptz not null default now(),
  actualizado_por  text
);

insert into ajustes (clave, valor, descripcion) values
  ('registro_abierto',    '1', 'Permite que cualquiera cree una cuenta desde la pantalla de acceso.'),
  ('requiere_aprobacion', '0', 'Las cuentas nuevas quedan pendientes hasta que el administrador las active.'),
  ('cupo_por_defecto',    '1', 'Declaraciones que puede cargar una cuenta recién registrada.'),
  ('mensaje_portada',     '',  'Aviso que se muestra en la bandeja a todos los usuarios.')
on conflict (clave) do nothing;

-- ── actualizado_en automático ───────────────────────────────────────────
create or replace function tocar_actualizado_en()
returns trigger language plpgsql as $$
begin
  new.actualizado_en = now();
  return new;
end $$;

drop trigger if exists trg_decl_actualizado on declaraciones;
create trigger trg_decl_actualizado
  before update on declaraciones
  for each row execute function tocar_actualizado_en();

drop trigger if exists trg_ajustes_actualizado on ajustes;
create trigger trg_ajustes_actualizado
  before update on ajustes
  for each row execute function tocar_actualizado_en();

-- ── Permisos de acceso a la cartera ajena ───────────────────────────────
-- El administrador NO ve las declaraciones de nadie. Para entrar a las de una
-- cuenta tiene que pedírselo a su dueño, y el dueño concede por un tiempo
-- limitado. Es la regla de privacidad del producto, no una comodidad: son
-- datos tributarios de terceros, sujetos a la reserva del art. 583 E.T.
create table if not exists permisos (
  id            bigserial primary key,
  usuario       text not null,     -- dueño de las declaraciones
  solicitante   text not null,     -- quien pide entrar (el administrador)
  estado        text not null default 'pendiente'
                check (estado in ('pendiente','concedido','denegado','revocado')),
  motivo        text,              -- por qué lo pide; lo lee el dueño al decidir
  solicitado_en timestamptz not null default now(),
  respondido_en timestamptz,
  -- Null mientras está pendiente. Un permiso vale solo si está concedido Y
  -- esta fecha no ha pasado: la caducidad se comprueba al leer, sin tarea
  -- programada que mantener.
  expira_en     timestamptz,
  unique (usuario, solicitante)
);

create index if not exists idx_permisos_solicitante on permisos(solicitante);
create index if not exists idx_permisos_usuario     on permisos(usuario);

-- ── Borradores: la carga en dos pasos ───────────────────────────────────
-- La exógena se procesa al subirla, pero la declaración NO se crea hasta que
-- el usuario ve lo que salió, responde lo que el archivo no trae y acepta el
-- descargo. Así un archivo equivocado no consume cupo — y el cupo sigue sin
-- devolverse nunca, que es lo que impide reciclarlo.
create table if not exists borradores (
  id             uuid primary key default gen_random_uuid(),
  usuario        text not null,
  cliente        jsonb not null,    -- el CLIENTE ya clasificado
  textos         jsonb not null,    -- los TEXTOS del libro
  exogena_path   text,              -- borradores/<id>/<archivo> en el bucket
  nombre_exogena text,
  creado_en      timestamptz not null default now(),
  expira_en      timestamptz not null default now() + interval '2 hours'
);

create index if not exists idx_borradores_usuario on borradores(usuario);
create index if not exists idx_borradores_expira  on borradores(expira_en);

-- ── Seguridad ───────────────────────────────────────────────────────────
-- RLS activa y SIN políticas públicas: solo el service_role (backend) entra.
-- El navegador nunca habla con Supabase, así que no hacen falta políticas por
-- usuario: quien decide qué ve cada cuenta es api\index.py con su rol.
-- Sin políticas, la clave publicable no ve ni una fila — ni un hash de clave.
alter table contribuyentes enable row level security;
alter table declaraciones  enable row level security;
alter table alertas        enable row level security;
alter table usuarios       enable row level security;
alter table bitacora       enable row level security;
alter table ajustes        enable row level security;
alter table permisos       enable row level security;
alter table borradores     enable row level security;

-- ── Storage ─────────────────────────────────────────────────────────────
-- Crear en el panel de Supabase dos buckets PRIVADOS (nunca públicos):
--     exogenas   → los reportes que sube el contribuyente
--     libros     → los .xlsx generados
-- Se sirven con URLs firmadas de vigencia corta, jamás con enlace público.
-- Los borradores viven bajo el prefijo `borradores/` del bucket `exogenas` y
-- se borran al confirmar o al vencer.

-- ═══════════════════════════════════════════════════════════════════════
--  MIGRACIÓN — bases que ya existían antes de agosto de 2026
--
--  Correr este bloque UNA vez sobre una base ya creada. En una base nueva no
--  hace falta: lo de arriba ya lo deja así.
--
--  El orden importa: primero se mueven las filas, después se estrecha la
--  restricción. Al revés, el ALTER fallaría por las filas que aún dicen
--  'contador'.
-- ═══════════════════════════════════════════════════════════════════════

-- update usuarios set rol = 'cliente' where rol = 'contador';
--
-- alter table usuarios drop constraint if exists usuarios_rol_check;
-- alter table usuarios add  constraint usuarios_rol_check
--   check (rol in ('admin','cliente'));
--
-- -- Los casos que subió el equipo de escritorio quedaron a nombre de una
-- -- cuenta técnica llamada 'contador'. Ahora que nadie ve lo que no cargó,
-- -- esa cuenta inhabilitada los dejaría invisibles para todo el mundo: pasan
-- -- a nombre del administrador, que es de quien son.
-- update declaraciones set creada_por = 'admin' where creada_por = 'contador';
-- update recibos_rst   set creada_por = 'admin' where creada_por = 'contador';
--
-- alter table declaraciones alter column creada_por set default 'admin';
-- alter table recibos_rst   alter column creada_por set default 'admin';
--
-- -- Y la cuenta técnica ya no hace falta.
-- delete from usuarios where usuario = 'contador';
