# Decisiones

Tomadas sin consultar, siempre eligiendo la opción más simple.

## Fuente del Colab
- El notebook oficial es `TNT_Fit_Motor_Inteligente_corregido.ipynb`. **No estaba en el disco** (solo las copias viejas, que aún tienen
  `+0.45*var_grasa_pct` en el logit y dan 13.2 % de abandono), así que `ml/datos.py` se sincronizó aplicando el cambio descrito:
  se quitó ese término del logit del abandono. `var_grasa_pct` se sigue generando igual (no mueve la semilla) pero no influye en el
  abandono ni entra al modelo. Las demás partes del Script 1 no se pudieron comparar línea a línea con el corregido; si cambió algo más,
  las métricas de abajo lo delatarían y no es el caso.

## Métricas (scikit-learn 1.6.1, semilla 42)

| Modelo | Esperado (notebook corregido) | Este repo | ¿Coincide? |
|---|---|---|---|
| Tasa de abandono simulada | 12.5 % | 12.5 % | ✅ |
| Afluencia · Random Forest Regressor | R² 0.941 | R² 0.941 · MAE 2.88 | ✅ |
| Abandono · Random Forest (sin `var_grasa_pct`) | [[590,66],[27,67]] · ROC-AUC ≈ 0.918 | [[590,66],[27,67]] · ROC-AUC 0.918 · F1 0.590 · P 0.504 · R 0.713 | ✅ exacto |
| K-Means k=3 | silueta 0.396 | silueta 0.396 | ✅ |
| Mean-Shift | F1 0.859 | F1 0.859 (P 0.779 · R 0.957) | ✅ |

Referencia: el mismo Random Forest **con** `var_grasa_pct` como variable da ROC-AUC 0.916 (F1 0.587): el dato de salud no aporta nada,
porque ya no influye en el abandono simulado. (Con la versión vieja de los datos el modelo sin grasa daba 0.914.)

## Decisiones de diseño
- **Un día de rutina.** El Colab ordena un ejercicio por cada uno de los 6 patrones de movimiento; la respuesta tiene `dias` con un solo día.
  Extender a varios días es repetir la llamada con otra hora.
- **Mes de referencia = 4** para la predicción de espera (igual que el Colab): el modelo se entrenó con 5 meses simulados.
- **Semáforo rojo ⇒ no se genera rutina** (`estado: requiere_apto_medico`, `rutinaId: null`) y se crea alerta para el coach.
- **Sin ficha de salud ⇒ 409.** No se genera rutina sin PAR-Q+.
- **Presión y pulso** pueden venir en la ficha o tomarse de la última medición válida. Una medición válida nueva recalcula el semáforo.
- **"≥ 160/100"** se implementó como sistólica ≥ 160 **o** diastólica ≥ 100 (criterio clínico habitual); idem 140/90.
- **PAR-Q+:** 7 preguntas (primera página); críticas = 1, 2 y 3 (cardíacas). Configurable en `umbrales.py`.
- **Lesiones → máquinas excluidas**: rodilla (M-02, M-03), hombro (M-08, M-14), espalda baja (M-06, M-02), cadera (M-05, M-06).
  Lesión desconocida ⇒ 422. Configurable en `umbrales.py`.
- **Mean-Shift en producción:** se guardan los centros del modelo entrenado; una lectura nueva se asigna al centro más cercano y es
  atípica si ese grupo es de los diminutos (< 3 % de la muestra), igual que en el Colab. Las variables son Δpeso, Δgrasa, sistólica
  y duración de la medición (la duración es opcional en la API; por defecto 210 s). Δ se calcula contra la última medición **válida**.
- **Nombres de segmento K-Means** (`constante_manana`, `nocturno_nuevo`, `veterano_fin_de_semana`) se asignan por reglas sobre el perfil medio.
- **Un coach ve solo a sus socios** también en el backend (no solo en RLS). La estación solo puede actuar sobre un socio con **sesión abierta**
  en ella en los últimos 30 min.
- **`var_grasa_pct` no se guarda** en la tabla `socios` ni se siembra: es dato de salud y el modelo ya no lo usa.
- **Repositorio genérico** (insert/get/find/update/upsert) con dos implementaciones (memoria y Supabase vía PostgREST/httpx), en vez del SDK de supabase, para
  tener una dependencia menos y poder probar sin internet.
- **JWT HS256** con el JWT Secret de Supabase. Si el proyecto usa claves asimétricas (JWKS), hay que cambiar `decodificar_jwt`.
- **`modelos/*.joblib` no se versionan** (pesan y se regeneran); `metadata.json` sí.
- **Python:** desarrollado en 3.12; CI en 3.11 (mínimo pedido).
- **`GET /salud`** es público y solo expone versiones de modelos, nada sensible.

## App de la estación (`estacion/`)
- **Figma:** se leyó el prototipo con el MCP (estructura de 6 pantallas + paleta/tipografía de una captura). El prototipo es **vertical 600×960**; se
  siguió tu indicación de pantalla **horizontal 1280×800** y se reacomodó la distribución (dos columnas). Colores: fondo azul marino, acento naranja
  `#e8873f`, teal para la espera, tarjetas redondeadas; tipografía Inter (paquete `@fontsource`, funciona sin internet).
- **Textos del prototipo que no se copiaron:** "Tu coach aprobó tu rutina" (en la app la rutina amarilla queda *pendiente de aprobación*, como dice el backend),
  y el bloque "Músculo por segmento" (el backend no recibe esos datos).
- **Músculo:** se muestra en pantalla pero **no se envía** (`MedicionIn` del backend rechaza campos extra).
- **"¿Cómo te sientes hoy?"** no tiene campo en el backend: "Mareado/a" marca la pregunta 4 del PAR-Q+ y "Dolor en el pecho" la 2 (crítica ⇒ semáforo rojo).
- **Báscula simulada:** los valores de cada socio se derivan de su id (estables entre visitas). Si fueran aleatorios, el backend vería saltos de peso y marcaría
  como atípica una lectura normal. "Lectura imposible" = peso +6.5 kg; como el backend compara contra la última lectura válida, si aún no hay una en la sesión
  la app envía antes una lectura normal de base (en la demo equivale a "la medición de ayer").
- **Rojo:** solo se puede provocar con el PAR-Q+ (preguntas 1–3) o presión/pulso altos; la báscula simulada siempre da valores normales.
- **Espera por máquina:** el backend no la incluye en la rutina; se pide aparte a `GET /prediccion/espera` (hora actual). Si falla, la rutina se muestra igual con "espera 0 min".
- **QR del ticket:** apunta a la URL firmada del video del primer ejercicio, que **caduca a los 15 min** (así lo define el backend). Para un QR permanente haría falta
  una página pública de video; queda para otra fase. Si el video falla, el ticket sale sin QR.
- **Ticket 80 mm:** `window.print()` con `@page { size: 80mm auto }`; en pantalla el ticket es una vista previa de una línea por ejercicio, al imprimir se agrega la línea de descanso.
- **Inactividad:** 60 s sin tocar (en cualquier pantalla menos la inicial) ⇒ `reiniciar`, que reemplaza todo el estado por el inicial; las respuestas del backend que lleguen tarde se descartan.
- **Estado:** `useReducer` + contexto (`src/estado/flujo.tsx`), sin zustand. Toda llamada HTTP está en `src/api/cliente.ts`.
- **Backend:** en `ENTORNO=dev` con `CORS_ORIGINS` vacío se permite `http://localhost:5173`; en otro entorno hace falta configurarlo.
- **Dependencias en versiones actuales** (React 19, Vite 8, Tailwind 4, Vitest 5, ESLint 10, TypeScript 6).
