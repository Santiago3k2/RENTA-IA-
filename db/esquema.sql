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

-- ── Seguridad ───────────────────────────────────────────────────────────
-- RLS activa y SIN políticas públicas: solo el service_role (backend) entra.
-- Cuando se agregue login de contadores, aquí van las políticas por usuario.
alter table contribuyentes enable row level security;
alter table declaraciones  enable row level security;
alter table alertas        enable row level security;

-- ── Storage ─────────────────────────────────────────────────────────────
-- Crear en el panel de Supabase dos buckets PRIVADOS (nunca públicos):
--     exogenas   → los reportes que sube el contribuyente
--     libros     → los .xlsx generados
-- Se sirven con URLs firmadas de vigencia corta, jamás con enlace público.
