-- Migración 0002 «historial_ficha»: historial de cambios de la ficha de salud hechos por el coach/admin.
-- NO aplicada todavía: se aplica a mano en Supabase (SQL editor o `supabase db push`). Es idempotente salvo las políticas.
-- Solo agrega una tabla nueva; no toca ninguna existente.

create table if not exists public.fichas_salud_historial (
  id uuid primary key default gen_random_uuid(),
  socio_id uuid not null references public.socios(id) on delete cascade,
  cambio jsonb not null,            -- {"antes": {parq, lesiones, semaforo}, "despues": {parq, lesiones, semaforo}}
  motivo text not null check (length(btrim(motivo)) >= 3),
  hecho_por uuid references auth.users(id),   -- coach o admin que hizo el cambio
  fecha timestamptz not null default now()
);
create index if not exists fichas_historial_socio_idx on public.fichas_salud_historial(socio_id, fecha desc);

-- ---------- Row Level Security (igual que fichas_salud) ----------
alter table public.fichas_salud_historial enable row level security;

create policy fichas_hist_coach on public.fichas_salud_historial for select to authenticated using ((select public.rol_actual()) = 'coach' and exists
  (select 1 from public.socios s where s.id = socio_id and s.coach_id = (select auth.uid())));
create policy fichas_hist_propia on public.fichas_salud_historial for select to authenticated using ((select public.rol_actual()) = 'socio' and exists
  (select 1 from public.socios s where s.id = socio_id and s.user_id = (select auth.uid())));
create policy fichas_hist_admin on public.fichas_salud_historial for all to authenticated using ((select public.rol_actual()) = 'admin') with check ((select public.rol_actual()) = 'admin');

-- ---------- permisos (mismo criterio que 0001) ----------
revoke all on public.fichas_salud_historial from anon, authenticated;
grant all on public.fichas_salud_historial to service_role;
grant select, insert, update, delete on public.fichas_salud_historial to authenticated;   -- limitado por las políticas de arriba
