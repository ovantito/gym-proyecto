# Estación TNT Fit · backend y modelos

Proyecto universitario para **TNT GYM**: una estación (quiosco) en la sala identifica al socio por DNI/QR, lo mide
(peso, grasa, presión, pulso), calcula un **semáforo de salud con reglas fijas (sin IA)** y le genera una rutina ordenada
para perder el menor tiempo posible. Un panel web del coach recibe alertas.

Este repositorio contiene **solo el backend con los modelos funcionando**. La estación y el panel se hacen después.

```
tnt-fit/
  ml/          código del Colab pasado a scripts (datos, entrenamiento, búsqueda A*/Hill Climbing)
  backend/     API FastAPI (módulos estacion, salud, rutinas, prediccion, coach) + pruebas
  supabase/    schema.sql (tablas + RLS) y seed.py (3,000 socios simulados)
  .github/     CI (pytest + ruff) y reentrenamiento mensual
```

## Instalar

Requiere Python 3.11+ (probado en 3.12).

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements-dev.txt # runtime + pytest y ruff (en producción solo requirements.txt)
cp .env.example .env                        # y completa lo que uses (todo es opcional para la demo)
```

`scikit-learn` está fijado en **1.6.1** (la de Colab) para que las cifras coincidan con las del informe.

## Entrenar los modelos

```bash
python ml/entrenar.py
```

Genera los datos simulados (semilla 42), entrena los 4 modelos y escribe en `ml/modelos/`:
`afluencia.joblib`, `abandono.joblib`, `kmeans.joblib` + `kmeans_scaler.joblib`, `meanshift.joblib` + `meanshift_scaler.joblib`
y `metadata.json` (fecha, versión, métricas y variables de cada modelo). Los `.joblib` no se suben a git: se regeneran
(CI y `reentrenar.yml` lo hacen).

## Levantar el backend

```bash
cd backend
uvicorn app.main:create_app --factory --reload
# docs interactivas: http://127.0.0.1:8000/docs
```

- **Sin variables de Supabase** el backend usa un repositorio **en memoria** con los 3,000 socios simulados y una
  estación piloto; al arrancar imprime su `id` y (si no definiste `DEMO_STATION_KEY`) su `X-Station-Key`.
- **Con Supabase**: ejecuta `supabase/schema.sql` en el SQL editor, completa `SUPABASE_*` en `.env` y corre
  `python supabase/seed.py` (imprime la clave de la estación una sola vez).
- Prueba de humo del flujo completo (sesión → medición → ficha → rutina):
  `DEMO_STATION_KEY=... ESTACION_ID=... python backend/scripts/demo_flujo.py`

## Pruebas y lint

```bash
python ml/entrenar.py      # las pruebas necesitan los modelos
cd backend && pytest -q
cd .. && ruff check .
```

## Endpoints (prefijo `/v1`)

| Método y ruta | Quién | Qué hace |
|---|---|---|
| `POST /estaciones/{id}/sesiones` | estación | identifica al socio por DNI o QR y abre sesión |
| `POST /socios/{id}/mediciones` | estación/coach/admin | guarda la medición; Mean-Shift la marca atípica y avisa a mantenimiento |
| `PUT /socios/{id}/ficha-salud` | estación/coach/admin | PAR-Q+ + semáforo con reglas fijas |
| `POST /socios/{id}/rutinas/generar` | estación/coach/admin | Random Forest (espera) + A* (orden) respetando el semáforo |
| `GET /prediccion/espera?hora=&dia=` | estación/coach/admin | espera estimada por máquina |
| `POST /prediccion/abandono/lote` | admin (cron nocturno) | abandono + K-Means para todos los socios; crea alertas |
| `GET /coach/alertas`, `GET /coach/rutinas-pendientes`, `POST /coach/rutinas/{id}/aprobar` | coach/admin | panel del coach (cada coach ve solo sus socios) |
| `GET /ejercicios/{id}/video` | estación/coach/admin/socio | URL firmada de Cloudflare R2, válida 15 min |
| `GET /salud` | público | health check con la versión de los modelos |

### Semáforo (reglas fijas — `backend/app/core/umbrales.py`)

| Color | Condición | Consecuencia |
|---|---|---|
| 🔴 rojo | sistólica ≥ 160 **o** diastólica ≥ 100 **o** pulso en reposo > 100 **o** PAR-Q+ con respuesta crítica (preguntas 1–3) | requiere apto médico; no se genera rutina |
| 🟡 amarillo | sistólica ≥ 140 **o** diastólica ≥ 90 **o** algún "sí" en PAR-Q+ **o** lesión declarada | rutina con restricciones, queda `pendiente_aprobacion` del coach |
| 🟢 verde | todo lo demás | rutina activa |

## Qué del Colab entra al sistema y por qué

| Del Colab | ¿Entra? | Dónde | Por qué |
|---|---|---|---|
| Script 1 · generación de datos (semilla 42) | solo para entrenar y sembrar la demo | `ml/datos.py` | no hay datos reales todavía; la semilla fija hace reproducibles las cifras |
| Script 2 · **Random Forest Regressor** de afluencia | **sí** | `ml/entrenar.py`, `prediccion.py`, `rutinas.py` | predice socios en sala por hora → espera por máquina, que es el costo de A* (R² 0.941 vs 0.892 de la regresión lineal) |
| Script 3 · **A\*** | **sí** | `ml/busqueda.py`, `rutinas.py` | ordena la rutina con el menor tiempo perdido, es óptimo (heurística admisible) y respeta las máquinas excluidas |
| Script 3 · **Hill Climbing** | solo respaldo | `ml/busqueda.py` | modo offline (`MODO_OFFLINE=true`) o si A* fallara: rápido, casi óptimo |
| Script 3 · BFS, DFS, costo uniforme | no | — | solo servían para comparar en el informe |
| Script 4 · **Random Forest Classifier** de abandono | **sí** | `prediccion.py` | riesgo de abandono a 30 días para que el coach llame a tiempo. **Sin `var_grasa_pct`** (dato de salud) |
| Script 4 · regresión logística, KNN, SVM, árbol, XGBoost | no | — | comparativa del informe; un solo modelo en producción |
| Script 5.1 · **K-Means k=3** | **sí** | `prediccion.py` | segmenta socios para personalizar mensajes del coach |
| Script 5.2 · **Mean-Shift** | **sí** | `salud.py` | detecta mediciones atípicas (báscula descalibrada, electrodos sucios) y no las usa |
| Script 5.2 · DBSCAN | no | — | Mean-Shift lo superó (F1 0.859 vs 0.742) |
| Regresión lineal, ROI, aprendizaje por refuerzo | no | — | comparativas / fuera de alcance |

### Métricas de los modelos (`ml/modelos/metadata.json`)

| Modelo | Métrica |
|---|---|
| Afluencia · Random Forest Regressor | R² 0.941 · MAE 2.88 socios |
| Abandono · Random Forest Classifier (12.5 % de abandono simulado) | ROC-AUC 0.918 · F1 0.590 · matriz [[590,66],[27,67]] |
| Segmentos · K-Means k=3 | silueta 0.396 |
| Lecturas atípicas · Mean-Shift | F1 0.859 (precisión 0.779, recall 0.957) |

Coinciden con el notebook corregido; detalle en `DECISIONES.md`.

## Documentos

- `DECISIONES.md` — decisiones tomadas sin consultar y diferencias con el Colab.
- `SEGURIDAD.md` — cada medida de seguridad explicada en lenguaje simple.

## App de la estación (`estacion/`)

React + Vite + TypeScript + Tailwind v4, pensada para pantalla táctil horizontal de 1280×800.

```bash
cd estacion
cp .env.example .env     # VITE_API_URL, VITE_STATION_ID, VITE_STATION_KEY (el backend en modo demo imprime el id y la clave al arrancar)
npm install
npm run dev              # http://localhost:5173  (el backend debe estar en VITE_API_URL)
npm test                 # Vitest + Testing Library
npm run lint && npm run build
```

Flujo: Identificación (DNI en teclado en pantalla) → Medición (báscula simulada; "lectura imposible" demuestra Mean-Shift) → Ficha de salud (PAR-Q+) →
Semáforo (rojo termina aquí) → Rutina (A*, video por ejercicio) → Ticket de 80 mm con QR. A los 60 s sin tocar vuelve al inicio y borra los datos del socio.
Todas las llamadas al backend están en `src/api/cliente.ts`.

## Panel del coach (`panel-coach/`)

React + Vite + TypeScript + Tailwind v4 + Recharts, para escritorio. Login con el JWT del backend; el coach ve solo a sus socios y el admin todo
(y puede correr el análisis nocturno a mano).

```bash
cd panel-coach
cp .env.example .env     # VITE_API_URL
npm install
npm run dev              # http://localhost:5174
npm test && npm run lint && npm run build
```

Secciones: Rutinas por aprobar (aprobar / rechazar con motivo) · Riesgo de abandono (Random Forest, con los 3 datos que más pesan y "Registrar contacto") ·
Perfiles de socio (K-Means) · Estaciones y mantenimiento (lecturas atípicas de Mean-Shift) · Modelo de IA (versión y métricas en palabras simples).

**Usuarios de prueba:** en modo demo (sin Supabase) el backend crea `coach@tnt.demo`, `coach2@tnt.demo` y `admin@tnt.demo` y **imprime sus contraseñas al
arrancar** (o define `DEMO_COACH_PASSWORD` / `DEMO_ADMIN_PASSWORD`). Con Supabase, el login usa Supabase Auth (requiere `SUPABASE_PUBLISHABLE_KEY`) y el rol va en
`app_metadata.role`.

Endpoints nuevos (prefijo `/v1`): `POST /auth/login`, `GET /coach/socios`, `GET /coach/perfiles`, `GET /coach/mantenimiento`, `GET /coach/modelo`,
`POST /coach/alertas/{id}/atender`, `POST /coach/rutinas/{id}/rechazar`, `GET /rutinas/{id}` (la estación consulta si el coach aprobó) y
`GET /ejercicios/{id}/ver` (público, redirige 302 a una URL firmada nueva: es lo que lleva el QR del ticket).

## Despliegue

Ver `DESPLIEGUE.md` (Render para el backend con `render.yaml`, Vercel para la estación y el panel, y la lista de variables de entorno).
