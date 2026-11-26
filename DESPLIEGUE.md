# Despliegue

Backend en **Render** (plan gratis) y las dos apps web en **Vercel**. Base de datos en Supabase y videos en Cloudflare R2.
Los valores de las variables **solo se escriben en los paneles** (Render / Vercel); nunca en el repositorio.

## 1. Backend en Render

`render.yaml` (en la raíz) ya define el servicio. Pasos:

1. Entra a <https://dashboard.render.com> → **New +** → **Blueprint**.
2. Conecta tu cuenta de GitHub y elige el repo `ovantito/gym-proyecto`. Render leerá `render.yaml` (rama `main`).
3. Render te pedirá las variables marcadas `sync: false`. Rellénalas (lista abajo) y pulsa **Apply**.
4. Espera el primer deploy (~5–8 min: instala dependencias y **entrena los 4 modelos**). Verifica con `https://<tu-servicio>.onrender.com/v1/salud`
   (debe decir `"repositorio":"supabase"`).
5. Copia la URL del servicio: la necesitas como `VITE_API_URL` en Vercel y para `CORS_ORIGINS`.

Alternativa sin Blueprint: **New + → Web Service** → mismo repo → Runtime *Python*, Plan *Free*, Branch `main`,
Build Command `pip install -r backend/requirements.txt && python ml/entrenar.py`,
Start Command `cd backend && uvicorn app.main:create_app --factory --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`,
Health Check Path `/v1/salud`.

### Variables de entorno (Render → Environment)

| Nombre | Obligatoria | Qué es |
|---|---|---|
| `PYTHON_VERSION` | sí (ya viene en `render.yaml`) | versión de Python con la que se probó |
| `ENTORNO` | **sí** | pon `prod` (con `prod` el backend se **niega a arrancar** si faltan las de Supabase, en vez de caer en modo demo) |
| `SUPABASE_URL` | sí | `https://<proyecto>.supabase.co` |
| `SUPABASE_PUBLISHABLE_KEY` | sí | clave `sb_publishable_...` (login del panel) |
| `SUPABASE_SECRET_KEY` | sí | clave `sb_secret_...` (**secreta**, solo aquí y en `backend/.env`) |
| `CORS_ORIGINS` | sí | dominios de Vercel separados por coma: `https://<estacion>.vercel.app,https://<panel>.vercel.app` |
| `R2_ACCOUNT_ID` | sí | Account ID de Cloudflare (32 caracteres) |
| `R2_ACCESS_KEY_ID` | sí | Access Key ID del token de R2 (solo lectura) |
| `R2_SECRET_ACCESS_KEY` | sí | Secret Access Key del token de R2 |
| `R2_BUCKET` | sí | nombre del bucket de videos |
| `R2_PREFIJO` | no | déjala sin crear (los videos se asignan en `backend/app/core/videos.py`) |
| `SUPABASE_JWKS_URL` | no | solo si no es `<SUPABASE_URL>/auth/v1/.well-known/jwks.json` |
| `RATE_LIMIT_DEFECTO`, `RATE_LIMIT_SESIONES`, `RATE_LIMIT_LOGIN`, `RATE_LIMIT_VER`, `ZONA_HORARIA`, `MODO_OFFLINE` | no | afinan límites y comportamiento (ver `.env.example`) |

**Notas del plan gratis:** el servicio se duerme tras ~15 min sin tráfico y la primera petición tarda ~30–60 s en despertar (la estación mostrará
"Sin conexión, intenta de nuevo"; reintentar funciona). Conviene abrir `/v1/salud` unos minutos antes de una demo.

## 2. Estación y panel en Vercel

Crea **dos proyectos** (Add New → Project → mismo repo `ovantito/gym-proyecto`):

| | Estación | Panel del coach |
|---|---|---|
| Root Directory | `estacion` | `panel-coach` |
| Framework Preset | Vite | Vite |
| Install Command | `npm ci` (o el default) | `npm ci` (o el default) |
| Build Command | `npm run build` | `npm run build` |
| Output Directory | `dist` | `dist` |
| Variables (Environment Variables) | `VITE_API_URL`, `VITE_STATION_ID`, `VITE_STATION_KEY` | `VITE_API_URL` |

- `VITE_API_URL` = URL del servicio de Render (`https://<servicio>.onrender.com`, sin `/` final).
- `VITE_STATION_ID` y `VITE_STATION_KEY` = id y clave de la estación creada con `supabase/seed.py`.
- Ninguna app necesita rutas especiales (`vercel.json`): es una sola página.
- Después de tener las URLs de Vercel, vuelve a Render y completa `CORS_ORIGINS`.

> ⚠️ **`VITE_STATION_KEY` queda dentro del JavaScript que descarga el navegador**: cualquiera que abra la estación desplegada puede leerla.
> Activa **Deployment Protection / Vercel Authentication** (o contraseña) en el proyecto de la estación, o sirve la estación solo desde el equipo del quiosco,
> y rota la clave (nueva estación en Supabase) si sospechas que se filtró. Ver `SEGURIDAD.md`.

## 3. Orden recomendado
1. Render (backend) → 2. Vercel estación y panel → 3. `CORS_ORIGINS` en Render con los dominios de Vercel → 4. probar el flujo completo.
