-- ═══════════════════════════════════════════════════════════════════════
--  RENTA IA · módulo RST — Régimen Simple de Tributación
--
--  Tablas PROPIAS, no un campo de tipo sobre `declaraciones` (decisión del
--  usuario, 30-jul-2026). La razón es la clave del caso: en renta es
--  (contribuyente, año gravable) y aquí es (contribuyente, año, BIMESTRE).
--  Meterlas en la misma tabla obligaría a un bimestre nulo en todo el módulo
--  de renta y a levantar la restricción de unicidad que hoy protege los casos.
--
--  `contribuyentes` SÍ se comparte: un mismo cliente puede estar en los dos
--  regímenes a la vez y debe verse como una sola ficha en la cartera.
--
--  Alcance: solo los anticipos bimestrales (Formulario 2593). La declaración
--  anual del SIMPLE (Formulario 260) queda fuera por ahora — de ahí el nombre
--  `recibos_rst` y no `declaraciones_rst`.
--
--  Pegar en el SQL Editor de Supabase y ejecutar. Es aditivo: no toca nada
--  de lo que ya existe.
-- ═══════════════════════════════════════════════════════════════════════

-- ── Recibos del SIMPLE: un caso = contribuyente + año + bimestre ────────
create table if not exists recibos_rst (
  id                uuid primary key default gen_random_uuid(),
  contribuyente_id  uuid not null references contribuyentes(id) on delete cascade,
  ano_gravable      text not null,
  bimestre          smallint not null check (bimestre between 1 and 6),

  -- flujo de revisión: idéntico al de renta, para que la bandeja sea una sola
  estado            text not null default 'borrador'
                    check (estado in ('borrador','en_revision','liberada')),
  semaforo          text check (semaforo in ('VERDE','AMARILLO','ROJO')),
  liberada_en       timestamptz,
  liberada_por      text,

  -- contexto de la liquidación
  uvt               integer,
  grupo             smallint check (grupo between 1 and 4),
  tarifa            numeric(6,4),          -- tarifa SIMPLE consolidada aplicada
  municipio         text,
  cod_dane          text,
  tarifa_ica        numeric(8,6),
  n_facturas        integer,
  n_compras         integer,

  -- cifras clave, para pintar la bandeja sin recalcular
  ingresos_gravados     bigint,
  ingresos_no_gravados  bigint,
  base                  bigint,
  base_uvt              numeric(12,2),
  anticipo_consolidado  bigint,
  ica                   bigint,
  descuento_pension     bigint,
  anticipo_neto         bigint,
  iva_generado          numeric(16,2),
  iva_descontable       numeric(16,2),
  reteiva               numeric(16,2),
  iva_pagar             numeric(16,2),
  total_pagar           bigint,            -- ya aproximado al múltiplo de mil

  -- el caso completo: la ficha del contribuyente y la liquidación que produjo
  -- el motor, más las comprobaciones que dan el semáforo
  ficha             jsonb not null,
  liquidacion       jsonb not null,
  validaciones      jsonb,

  -- archivos en Supabase Storage
  libro_path        text,
  consolidado_path  text,

  -- Quién lo cargó: sostiene el cupo, cuál es su copia del recibo y, desde
  -- agosto de 2026, quién puede verlo. Nadie ve un recibo que no cargó sin
  -- permiso de su dueño.
  creada_por        text not null default 'admin',

  creado_en         timestamptz not null default now(),
  actualizado_en    timestamptz not null default now(),

  -- Con el dueño dentro, igual que en `declaraciones`: cada cuenta tiene su
  -- propia copia del recibo y dos personas pueden liquidar el mismo bimestre
  -- del mismo contribuyente sin pisarse ni enterarse la una de la otra.
  unique (contribuyente_id, ano_gravable, bimestre, creada_por)
);

create index if not exists idx_rst_contribuyente on recibos_rst(contribuyente_id);
create index if not exists idx_rst_estado        on recibos_rst(estado);
create index if not exists idx_rst_semaforo      on recibos_rst(semaforo);
create index if not exists idx_rst_periodo       on recibos_rst(ano_gravable, bimestre);

-- ── Alertas del recibo ──────────────────────────────────────────────────
-- Son un derivado del motor, no notas del contador: se reemplazan enteras en
-- cada reproceso. Lo que sí sobrevive es `resuelta` / `nota_contador`, que se
-- vuelven a aplicar por (recibo, tema).
create table if not exists alertas_rst (
  id             bigserial primary key,
  recibo_id      uuid not null references recibos_rst(id) on delete cascade,
  orden          integer,
  prioridad      text check (prioridad in ('ALTA','MEDIA','BAJA')),
  tema           text,
  texto          text,
  resuelta       boolean not null default false,
  nota_contador  text,
  resuelta_en    timestamptz
);

create index if not exists idx_alertas_rst_recibo on alertas_rst(recibo_id);

-- ── actualizado_en automático ───────────────────────────────────────────
-- Reutiliza la función que ya creó db/esquema.sql.
drop trigger if exists trg_rst_actualizado on recibos_rst;
create trigger trg_rst_actualizado
  before update on recibos_rst
  for each row execute function tocar_actualizado_en();

-- ── Seguridad ───────────────────────────────────────────────────────────
-- RLS activa y SIN políticas, igual que el resto: solo el service_role entra.
alter table recibos_rst enable row level security;
alter table alertas_rst enable row level security;

-- ── Storage ─────────────────────────────────────────────────────────────
-- Bucket PRIVADO adicional:
--     consolidados  → las exportaciones de facturación electrónica de la DIAN
-- Los libros del SIMPLE van al bucket `libros` que ya existe, bajo la carpeta
-- <contribuyente_id>/RST-<año>-B<bimestre>/.
