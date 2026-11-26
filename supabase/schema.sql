-- Estación TNT Fit · esquema de Supabase (Postgres)
-- Roles: viajan en el JWT de Supabase Auth, en app_metadata.role = socio | coach | admin
-- (la estación NO usa JWT: usa X-Station-Key y solo habla con el backend).
-- El backend usa la secret key sb_secret_... (salta RLS) y además aplica las mismas reglas en código.
-- RLS protege cualquier acceso directo a la base con un JWT de usuario.

create extension if not exists pgcrypto;

-- ---------- helpers de rol ----------
create or replace function public.rol_actual() returns text
language sql stable as $$ select coalesce(auth.jwt() -> 'app_metadata' ->> 'role', '') $$;

-- ---------- tablas ----------
create table if not exists public.socios (
  id uuid primary key default gen_random_uuid(),
  user_id uuid unique references auth.users(id),          -- si el socio tiene cuenta
  coach_id uuid references auth.users(id),                -- su coach asignado
  dni text unique not null check (dni ~ '^[0-9]{8}$'),
  qr text unique not null,
  nombre text not null,
  edad int, antiguedad_meses numeric, visitas_semana numeric, dias_ultima_visita int,
  hora_preferida numeric, plan text check (plan in ('mensual','trimestral','anual')),
  semaforo text not null default 'verde' check (semaforo in ('verde','amarillo','rojo')),
  racha_semanas numeric, sesiones_estacion numeric, coach_contacto_30d int,
  segmento text, riesgo_abandono numeric, nivel_riesgo text
);
create index if not exists socios_coach_idx on public.socios(coach_id);

create table if not exists public.estaciones (
  id uuid primary key default gen_random_uuid(),
  nombre text not null,
  clave_hash text unique not null,                         -- SHA-256 de la clave; la clave nunca se guarda
  activa boolean not null default true
);

create table if not exists public.sesiones (
  id uuid primary key default gen_random_uuid(),
  estacion_id uuid not null references public.estaciones(id),
  socio_id uuid not null references public.socios(id) on delete cascade,
  inicio timestamptz not null default now()
);

create table if not exists public.mediciones (
  id uuid primary key default gen_random_uuid(),
  socio_id uuid not null references public.socios(id) on delete cascade,
  sesion_id text,
  peso_kg numeric not null, grasa_pct numeric not null,
  presion_sistolica int not null, presion_diastolica int not null, pulso_reposo int not null,
  delta_peso_kg numeric, delta_grasa_pct numeric, duracion_seg numeric,
  atipica boolean not null default false,                  -- Mean-Shift: sensor sospechoso
  usada boolean not null default true,
  fecha timestamptz not null default now()
);
create index if not exists mediciones_socio_idx on public.mediciones(socio_id, fecha desc);

-- Ficha de salud: SEPARADA de socios porque es dato sensible (PAR-Q+, lesiones).
create table if not exists public.fichas_salud (
  id uuid primary key default gen_random_uuid(),
  socio_id uuid unique not null references public.socios(id) on delete cascade,
  parq jsonb not null, lesiones jsonb not null default '[]',
  semaforo text not null check (semaforo in ('verde','amarillo','rojo')),
  motivos jsonb not null default '[]', maquinas_excluidas jsonb not null default '[]',
  requiere_apto_medico boolean not null default false,
  actualizada timestamptz not null default now()
);

create table if not exists public.rutinas (
  id uuid primary key default gen_random_uuid(),
  socio_id uuid not null references public.socios(id) on delete cascade,
  coach_id uuid references auth.users(id),
  semaforo text not null, dias jsonb not null,
  estado text not null check (estado in ('activa','pendiente_aprobacion','rechazada','archivada')),
  algoritmo text, costo_min numeric,
  aprobada_por uuid, aprobada_en timestamptz, motivo_rechazo text,
  creada timestamptz not null default now()
);

create table if not exists public.alertas (
  id uuid primary key default gen_random_uuid(),
  tipo text not null check (tipo in ('abandono','mantenimiento','semaforo_rojo','rutina_pendiente')),
  nivel text not null, mensaje text not null,
  socio_id uuid references public.socios(id) on delete cascade,
  coach_id uuid references auth.users(id),
  rutina_id uuid references public.rutinas(id) on delete set null,
  resuelta boolean not null default false,
  atendida_por uuid, atendida_en timestamptz,
  creada timestamptz not null default now()
);

create table if not exists public.modelos_version (
  id uuid primary key default gen_random_uuid(),
  version text not null, fecha_entrenamiento timestamptz not null,
  metricas jsonb, registrada timestamptz not null default now(),
  unique (version, fecha_entrenamiento)
);

-- ---------- Row Level Security ----------
alter table public.socios enable row level security;
alter table public.estaciones enable row level security;
alter table public.sesiones enable row level security;
alter table public.mediciones enable row level security;
alter table public.fichas_salud enable row level security;
alter table public.rutinas enable row level security;
alter table public.alertas enable row level security;
alter table public.modelos_version enable row level security;

-- socios: el coach ve solo a sus socios; el socio, su propia fila; admin todo.
create policy socios_coach on public.socios for select using (rol_actual() = 'coach' and coach_id = auth.uid());
create policy socios_propio on public.socios for select using (rol_actual() = 'socio' and user_id = auth.uid());
create policy socios_admin on public.socios for all using (rol_actual() = 'admin') with check (rol_actual() = 'admin');

-- Tablas hijas: se accede según el coach del socio dueño del dato.
create policy sesiones_coach on public.sesiones for select using (rol_actual() = 'coach' and exists
  (select 1 from public.socios s where s.id = socio_id and s.coach_id = auth.uid()));
create policy mediciones_coach on public.mediciones for select using (rol_actual() = 'coach' and exists
  (select 1 from public.socios s where s.id = socio_id and s.coach_id = auth.uid()));
create policy mediciones_propia on public.mediciones for select using (rol_actual() = 'socio' and exists
  (select 1 from public.socios s where s.id = socio_id and s.user_id = auth.uid()));
create policy fichas_coach on public.fichas_salud for select using (rol_actual() = 'coach' and exists
  (select 1 from public.socios s where s.id = socio_id and s.coach_id = auth.uid()));
create policy fichas_propia on public.fichas_salud for select using (rol_actual() = 'socio' and exists
  (select 1 from public.socios s where s.id = socio_id and s.user_id = auth.uid()));
create policy rutinas_coach on public.rutinas for select using (rol_actual() = 'coach' and coach_id = auth.uid());
create policy rutinas_coach_aprueba on public.rutinas for update using (rol_actual() = 'coach' and coach_id = auth.uid())
  with check (rol_actual() = 'coach' and coach_id = auth.uid());
create policy rutinas_propia on public.rutinas for select using (rol_actual() = 'socio' and exists
  (select 1 from public.socios s where s.id = socio_id and s.user_id = auth.uid()));
create policy alertas_coach on public.alertas for select using (rol_actual() = 'coach' and coach_id = auth.uid());
create policy alertas_coach_resuelve on public.alertas for update using (rol_actual() = 'coach' and coach_id = auth.uid())
  with check (rol_actual() = 'coach' and coach_id = auth.uid());

-- admin: acceso total a las demás tablas. Estaciones y versiones de modelos: solo admin.
create policy sesiones_admin on public.sesiones for all using (rol_actual() = 'admin') with check (rol_actual() = 'admin');
create policy mediciones_admin on public.mediciones for all using (rol_actual() = 'admin') with check (rol_actual() = 'admin');
create policy fichas_admin on public.fichas_salud for all using (rol_actual() = 'admin') with check (rol_actual() = 'admin');
create policy rutinas_admin on public.rutinas for all using (rol_actual() = 'admin') with check (rol_actual() = 'admin');
create policy alertas_admin on public.alertas for all using (rol_actual() = 'admin') with check (rol_actual() = 'admin');
create policy estaciones_admin on public.estaciones for all using (rol_actual() = 'admin') with check (rol_actual() = 'admin');
create policy modelos_admin on public.modelos_version for all using (rol_actual() = 'admin') with check (rol_actual() = 'admin');
create policy modelos_lectura on public.modelos_version for select using (rol_actual() in ('coach','admin'));
-- Sin política = sin acceso: la clave publishable (rol anon) y la estación nunca leen tablas directamente.
