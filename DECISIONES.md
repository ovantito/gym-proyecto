# Decisiones

Tomadas sin consultar, siempre eligiendo la opción más simple.

## Fuente del Colab
- El archivo `TNT_Fit_Motor_Inteligente_corregido.ipynb` **no existe** en la carpeta ni en Descargas. Se usó
  `Descargas/TNT_Fit_Motor_Inteligente.ipynb` (el más reciente de los dos encontrados; el otro es `..._APF3_...`).
  Si existe una versión "corregida", conviene compararla con `ml/datos.py` y `ml/entrenar.py`.

## Métricas: obtenidas vs. Colab

| Modelo | Colab | Este repo | ¿Coincide? |
|---|---|---|---|
| Afluencia · Random Forest Regressor | R² 0.941 · MAE 2.88 | R² 0.941 · MAE 2.88 | ✅ exacto |
| K-Means k=3 | silueta 0.396; perfiles medios (visitas 4.2/2.0/2.0) | silueta 0.396; mismos perfiles medios (4.2/2.0/2.0) | ✅ exacto |
| Mean-Shift | 14 grupos, 86 marcadas, P 0.779 · R 0.957 · F1 0.859 | idéntico | ✅ exacto |
| Abandono · Random Forest (con las 9 numéricas del Colab, incl. `var_grasa_pct`) | F1 0.602 · ROC-AUC 0.927 | F1 0.620 · ROC-AUC 0.926 | ≈ (ver abajo) |
| **Abandono · Random Forest de producción (sin `var_grasa_pct`)** | — | F1 0.593 · ROC-AUC **0.914** · matriz **[[591,60],[32,67]]** | ver abajo |

**Diferencia con las cifras del encargo.** El encargo pedía matriz `[[590,66],[27,67]]` y ROC-AUC ≈ 0.918 para el Random Forest de
abandono. **Esas cifras no aparecen en el notebook** (ni en el otro). Además son incompatibles con los datos simulados con semilla 42:
la matriz tiene 94 abandonos en el conjunto de prueba, pero con 13.2 % de abandono en 3,000 socios el conjunto de prueba (25 %,
estratificado) tiene necesariamente 99. Lo más cercano en el Colab es XGBoost (ROC-AUC 0.919). Los datos y el resto de modelos
reproducen el Colab al decimal, así que se concluye que las cifras del encargo salen de otra versión del notebook.

Dos causas explican la diferencia pequeña en abandono: (1) quitar `var_grasa_pct` (obligatorio por privacidad) baja AUC de 0.926 a 0.914;
(2) la pequeña diferencia 0.926 vs 0.927 con las mismas variables se debe, muy probablemente, al orden de columnas (el Random Forest sortea variables por árbol); no se investigó más.
Que el modelo rinda bien **sin** el dato de salud es un buen argumento para el informe.

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
