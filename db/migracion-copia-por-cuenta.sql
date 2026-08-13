-- ═══════════════════════════════════════════════════════════════════════
--  MIGRACIÓN · una copia del caso por cuenta            (13 de agosto de 2026)
--
--  QUÉ CAMBIA
--  Hasta hoy la base solo admitía UNA declaración por (contribuyente, año) y
--  UN recibo por (contribuyente, año, bimestre), sin importar quién los
--  cargara. Por eso, cuando dos personas trabajaban el mismo caso, la segunda
--  chocaba contra la primera y el programa tenía que decirle que «ya lo cargó
--  otra persona» —un dato que no le incumbe y que crea problemas entre
--  quienes comparten el programa—.
--
--  Con el dueño dentro de la llave, cada cuenta tiene su propia copia: dos,
--  diez o veinte personas pueden trabajar la misma declaración sin pisarse y
--  sin que ninguna se entere de las demás. Reprocesar lo suyo sigue
--  actualizando su fila, como siempre.
--
--  CÓMO SE CORRE
--  Supabase → SQL Editor → pegar todo esto → Run. Se puede correr dos veces
--  sin daño. No borra ni una fila: solo cambia las llaves únicas.
--
--  ORDEN: **primero esto, después el despliegue.** El programa nuevo busca la
--  fila del dueño antes de escribir, así que con la base vieja seguiría
--  funcionando pero sin poder crear la segunda copia (la llave la rechazaría).
-- ═══════════════════════════════════════════════════════════════════════

-- ── 1 · Fuera las llaves únicas que no llevan el dueño dentro ───────────
-- Se buscan por sus columnas y no por su nombre: el nombre lo puso Postgres
-- al crear la tabla y no tiene por qué ser el mismo en todas las bases.
do $$
declare
  t text;
  llave text;
begin
  foreach t in array array['declaraciones', 'recibos_rst'] loop
    if to_regclass(t) is null then
      raise notice 'la tabla % no existe en esta base: se salta', t;
      continue;
    end if;
    for llave in
      select con.conname
        from pg_constraint con
       where con.contype = 'u'
         and con.conrelid = to_regclass(t)
         and not exists (
               select 1
                 from unnest(con.conkey) as k
                 join pg_attribute a
                   on a.attrelid = con.conrelid and a.attnum = k
                where a.attname = 'creada_por')
    loop
      execute format('alter table %I drop constraint %I', t, llave);
      raise notice 'quitada la llave única % de %', llave, t;
    end loop;
  end loop;
end $$;

-- ── 2 · Las nuevas, con el dueño dentro ────────────────────────────────
-- No puede fallar por datos existentes: la llave nueva es más ancha que la
-- vieja, así que todo lo que cumplía la anterior cumple esta.
create unique index if not exists declaraciones_caso_por_cuenta
    on declaraciones (contribuyente_id, ano_gravable, creada_por);

do $$
begin
  if to_regclass('recibos_rst') is not null then
    execute 'create unique index if not exists recibos_rst_caso_por_cuenta
               on recibos_rst (contribuyente_id, ano_gravable, bimestre, creada_por)';
  end if;
end $$;

-- ── 3 · Comprobación ───────────────────────────────────────────────────
-- Debe salir una línea por tabla y las dos deben terminar en `creada_por`.
select tablename, indexname, indexdef
  from pg_indexes
 where tablename in ('declaraciones', 'recibos_rst')
   and indexdef ilike '%unique%'
 order by tablename, indexname;
