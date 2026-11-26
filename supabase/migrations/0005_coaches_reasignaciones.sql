-- Migración 0005 «coaches_reasignaciones»: tabla de coaches y historial de reasignaciones de socios.
-- YA APLICADA en Supabase: NO volver a aplicar.

create table if not exists public.coaches (
  id uuid primary key references auth.users(id) on delete cascade,
  nombre text not null, email text not null unique,
  activo boolean not null default true, creado timestamptz not null default now());
create table if not exists public.reasignaciones (
  id uuid primary key default gen_random_uuid(),
  socio_id uuid not null references public.socios(id) on delete cascade,
  coach_antes uuid references public.coaches(id),
  coach_despues uuid not null references public.coaches(id),
  motivo text not null check (char_length(motivo) between 3 and 200),
  hecho_por uuid not null references auth.users(id), lote_id uuid,
  fecha timestamptz not null default now());
create index if not exists reasignaciones_socio_idx on public.reasignaciones(socio_id, fecha desc);
create index if not exists reasignaciones_coach_antes_idx on public.reasignaciones(coach_antes);
create index if not exists reasignaciones_coach_despues_idx on public.reasignaciones(coach_despues);
create index if not exists reasignaciones_hecho_por_idx on public.reasignaciones(hecho_por);
create index if not exists socios_coach_idx on public.socios(coach_id);
alter table public.coaches enable row level security;
alter table public.reasignaciones enable row level security;
revoke all on public.coaches, public.reasignaciones from anon;
grant all on public.coaches, public.reasignaciones to service_role;
grant select on public.coaches, public.reasignaciones to authenticated;
create policy coaches_lectura on public.coaches for select to authenticated
  using ((select public.rol_actual()) = 'admin' or id = (select auth.uid()));
create policy reasignaciones_lectura on public.reasignaciones for select to authenticated
  using ((select public.rol_actual()) = 'admin' or coach_antes = (select auth.uid()) or coach_despues = (select auth.uid()));
