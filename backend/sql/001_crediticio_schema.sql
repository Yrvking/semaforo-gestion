create extension if not exists pgcrypto;
create schema if not exists crediticio;

revoke all on schema crediticio from public, anon, authenticated;

create table if not exists crediticio.procesos (
  id uuid primary key default gen_random_uuid(),
  origen text not null check (origen in ('manual', 'automatico')),
  fecha_inicio date not null,
  fecha_fin date not null,
  estado text not null default 'queued' check (estado in ('queued', 'running', 'completed', 'failed')),
  etapa text not null default 'queued',
  progreso integer not null default 0 check (progreso between 0 and 100),
  procesados integer not null default 0,
  total integer not null default 0,
  mensaje text not null default 'Análisis en cola',
  error text,
  resumen jsonb,
  resultado jsonb,
  creado_en timestamptz not null default now(),
  iniciado_en timestamptz,
  completado_en timestamptz
);

create index if not exists procesos_crediticios_estado_idx
  on crediticio.procesos (estado, creado_en desc);
create index if not exists procesos_crediticios_fechas_idx
  on crediticio.procesos (fecha_inicio, fecha_fin, origen);

create table if not exists crediticio.prospectos (
  dni text not null,
  proyecto text not null,
  nombre text,
  responsable text,
  fecha_registro text,
  fecha_registro_date date,
  ultimo_perfil jsonb not null default '{}'::jsonb,
  primera_aparicion timestamptz not null default now(),
  ultima_aparicion timestamptz not null default now(),
  primary key (dni, proyecto)
);

alter table crediticio.prospectos
  add column if not exists fecha_registro_date date;

create table if not exists crediticio.evaluaciones (
  id bigint generated always as identity primary key,
  proceso_id uuid not null references crediticio.procesos(id) on delete cascade,
  dni text not null,
  proyecto text not null,
  huella text not null,
  perfil jsonb not null,
  evaluada_en timestamptz not null default now()
);

create index if not exists evaluaciones_crediticias_persona_idx
  on crediticio.evaluaciones (dni, proyecto, evaluada_en desc);

create or replace function public.crediticio_crear_proceso(
  p_fecha_inicio date,
  p_fecha_fin date,
  p_origen text
) returns jsonb
language plpgsql
security definer
set search_path = public, crediticio
as $$
declare
  v_proceso crediticio.procesos%rowtype;
begin
  perform pg_advisory_xact_lock(hashtext('crediticio.proceso.activo'));

  select * into v_proceso
  from crediticio.procesos
  where estado in ('queued', 'running')
  order by creado_en desc
  limit 1;

  if found then
    return to_jsonb(v_proceso) || jsonb_build_object('already_running', true, 'already_completed', false);
  end if;

  if p_origen = 'automatico' then
    select * into v_proceso
    from crediticio.procesos
    where origen = 'automatico'
      and fecha_inicio = p_fecha_inicio
      and fecha_fin = p_fecha_fin
      and estado = 'completed'
    order by completado_en desc
    limit 1;

    if found then
      return to_jsonb(v_proceso) || jsonb_build_object('already_running', false, 'already_completed', true);
    end if;
  end if;

  insert into crediticio.procesos (origen, fecha_inicio, fecha_fin)
  values (p_origen, p_fecha_inicio, p_fecha_fin)
  returning * into v_proceso;

  return to_jsonb(v_proceso) || jsonb_build_object('already_running', false, 'already_completed', false);
end;
$$;

create or replace function public.crediticio_actualizar_progreso(
  p_id uuid,
  p_etapa text,
  p_progreso integer,
  p_procesados integer,
  p_total integer,
  p_mensaje text
) returns void
language sql
security definer
set search_path = public, crediticio
as $$
  update crediticio.procesos
  set estado = 'running',
      etapa = p_etapa,
      progreso = greatest(0, least(100, p_progreso)),
      procesados = p_procesados,
      total = p_total,
      mensaje = p_mensaje,
      iniciado_en = coalesce(iniciado_en, now())
  where id = p_id;
$$;

create or replace function public.crediticio_completar_proceso(
  p_id uuid,
  p_resumen jsonb,
  p_prospectos jsonb
) returns void
language plpgsql
security definer
set search_path = public, crediticio
as $$
declare
  v_row jsonb;
  v_dni text;
  v_proyecto text;
  v_huella text;
  v_anterior text;
begin
  for v_row in select value from jsonb_array_elements(coalesce(p_prospectos, '[]'::jsonb)) loop
    v_dni := nullif(trim(v_row ->> 'dni'), '');
    v_proyecto := coalesce(nullif(trim(v_row ->> 'proyecto'), ''), 'SIN PROYECTO');
    if v_dni is null then
      continue;
    end if;

    insert into crediticio.prospectos (
      dni, proyecto, nombre, responsable, fecha_registro, fecha_registro_date, ultimo_perfil
    ) values (
      v_dni,
      v_proyecto,
      coalesce(v_row ->> 'nombre_completo', v_row ->> 'nombre'),
      v_row ->> 'responsable',
      v_row ->> 'fecha_registro',
      case
        when coalesce(v_row ->> 'fecha_registro', '') ~ '^\d{2}/\d{2}/\d{4}'
        then to_date(substring(v_row ->> 'fecha_registro' from 1 for 10), 'DD/MM/YYYY')
        else null
      end,
      v_row
    )
    on conflict (dni, proyecto) do update set
      nombre = excluded.nombre,
      responsable = excluded.responsable,
      fecha_registro = excluded.fecha_registro,
      fecha_registro_date = excluded.fecha_registro_date,
      ultimo_perfil = excluded.ultimo_perfil,
      ultima_aparicion = now();

    v_huella := md5(concat_ws('|',
      v_row ->> 'tiene_score', v_row ->> 'score', v_row ->> 'resultado',
      v_row ->> 'capacidad_pago', v_row ->> 'deuda_total',
      v_row ->> 'calificativo', v_row ->> 'semaforo_actual'
    ));

    select huella into v_anterior
    from crediticio.evaluaciones
    where dni = v_dni and proyecto = v_proyecto
    order by evaluada_en desc
    limit 1;

    if v_anterior is distinct from v_huella then
      insert into crediticio.evaluaciones (proceso_id, dni, proyecto, huella, perfil)
      values (p_id, v_dni, v_proyecto, v_huella, v_row);
    end if;
  end loop;

  update crediticio.procesos
  set estado = 'completed',
      etapa = 'completed',
      progreso = 100,
      procesados = jsonb_array_length(coalesce(p_prospectos, '[]'::jsonb)),
      total = jsonb_array_length(coalesce(p_prospectos, '[]'::jsonb)),
      mensaje = 'Análisis crediticio completado',
      resumen = p_resumen,
      resultado = p_prospectos,
      completado_en = now()
  where id = p_id;
end;
$$;

create or replace function public.crediticio_fallar_proceso(p_id uuid, p_error text)
returns void
language sql
security definer
set search_path = public, crediticio
as $$
  update crediticio.procesos
  set estado = 'failed', etapa = 'failed',
      mensaje = 'El análisis crediticio no pudo completarse',
      error = p_error, completado_en = now()
  where id = p_id;
$$;

create or replace function public.crediticio_obtener_proceso(p_id uuid)
returns jsonb
language sql
security definer
stable
set search_path = public, crediticio
as $$
  select to_jsonb(p) - 'resultado' - 'resumen'
  from crediticio.procesos p
  where id = p_id;
$$;

create or replace function public.crediticio_obtener_activo()
returns jsonb
language sql
security definer
stable
set search_path = public, crediticio
as $$
  select to_jsonb(p) - 'resultado' - 'resumen'
  from crediticio.procesos p
  where estado in ('queued', 'running')
  order by creado_en desc
  limit 1;
$$;

create or replace function public.crediticio_obtener_resultado(p_id uuid)
returns jsonb
language sql
security definer
stable
set search_path = public, crediticio
as $$
  select coalesce(resumen, '{}'::jsonb) || jsonb_build_object('prospectos', coalesce(resultado, '[]'::jsonb))
  from crediticio.procesos
  where id = p_id and estado = 'completed';
$$;

create or replace function public.crediticio_interrumpir_procesos()
returns void
language sql
security definer
set search_path = public, crediticio
as $$
  update crediticio.procesos
  set estado = 'failed', etapa = 'failed',
      mensaje = 'Proceso interrumpido por reinicio del servidor',
      error = 'Proceso interrumpido por reinicio del servidor',
      completado_en = now()
  where estado in ('queued', 'running');
$$;

create or replace function public.crediticio_consultar_acumulado(
  p_fecha_inicio date,
  p_fecha_fin date
) returns jsonb
language sql
security definer
stable
set search_path = public, crediticio
as $$
  select coalesce(jsonb_agg(ultimo_perfil order by proyecto, nombre), '[]'::jsonb)
  from crediticio.prospectos
  where fecha_registro_date between p_fecha_inicio and p_fecha_fin;
$$;

revoke all on function public.crediticio_crear_proceso(date, date, text) from public, anon, authenticated;
revoke all on function public.crediticio_actualizar_progreso(uuid, text, integer, integer, integer, text) from public, anon, authenticated;
revoke all on function public.crediticio_completar_proceso(uuid, jsonb, jsonb) from public, anon, authenticated;
revoke all on function public.crediticio_fallar_proceso(uuid, text) from public, anon, authenticated;
revoke all on function public.crediticio_obtener_proceso(uuid) from public, anon, authenticated;
revoke all on function public.crediticio_obtener_activo() from public, anon, authenticated;
revoke all on function public.crediticio_obtener_resultado(uuid) from public, anon, authenticated;
revoke all on function public.crediticio_interrumpir_procesos() from public, anon, authenticated;
revoke all on function public.crediticio_consultar_acumulado(date, date) from public, anon, authenticated;

grant execute on function public.crediticio_crear_proceso(date, date, text) to service_role;
grant execute on function public.crediticio_actualizar_progreso(uuid, text, integer, integer, integer, text) to service_role;
grant execute on function public.crediticio_completar_proceso(uuid, jsonb, jsonb) to service_role;
grant execute on function public.crediticio_fallar_proceso(uuid, text) to service_role;
grant execute on function public.crediticio_obtener_proceso(uuid) to service_role;
grant execute on function public.crediticio_obtener_activo() to service_role;
grant execute on function public.crediticio_obtener_resultado(uuid) to service_role;
grant execute on function public.crediticio_interrumpir_procesos() to service_role;
grant execute on function public.crediticio_consultar_acumulado(date, date) to service_role;
