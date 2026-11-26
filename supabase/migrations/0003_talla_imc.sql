-- Talla (tallímetro de la estación) e IMC calculado por el backend. Nullable: lecturas antiguas no lo tienen.
alter table public.mediciones
  add column if not exists talla_cm numeric check (talla_cm between 120 and 220),
  add column if not exists imc numeric;
