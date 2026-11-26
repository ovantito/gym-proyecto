-- Migración 0004 «bloqueo_rojo»: un socio en semáforo rojo queda bloqueado hasta que un coach/admin lo libere.
-- YA APLICADA en Supabase: NO volver a aplicar (es idempotente, pero no hace falta).
alter table public.fichas_salud
  add column if not exists bloqueado boolean not null default false,
  add column if not exists bloqueado_desde timestamptz;
