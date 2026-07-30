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

  -- quién la cargó: sostiene el cupo de cada cuenta e impide que un usuario
  -- restringido sobrescriba el caso de otro. 'contador' es el valor que deja
  -- la sincronización desde el equipo de escritorio.
  creada_por        text not null default 'contador',

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

  rol                text not null default 'cliente'
                     check (rol in ('admin','contador','cliente')),
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

-- ── Storage ─────────────────────────────────────────────────────────────
-- Crear en el panel de Supabase dos buckets PRIVADOS (nunca públicos):
--     exogenas   → los reportes que sube el contribuyente
--     libros     → los .xlsx generados
-- Se sirven con URLs firmadas de vigencia corta, jamás con enlace público.
