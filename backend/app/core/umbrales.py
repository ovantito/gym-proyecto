"""TODOS los umbrales y reglas fijas del sistema, en un solo archivo.

Se cambian aquí (y solo aquí). El semáforo de salud NO usa IA: son estas reglas.
Ver SEGURIDAD.md y README.md para la explicación en lenguaje simple.
"""

# --- Semáforo ROJO (requiere apto médico, no se genera rutina) --------------
ROJO_PRESION_SISTOLICA = 160      # mmHg: sistólica >= 160  ...
ROJO_PRESION_DIASTOLICA = 100     # mmHg: ... o diastólica >= 100
ROJO_PULSO_REPOSO = 100           # lpm: pulso en reposo > 100
# PAR-Q+ (primera página, 7 preguntas, numeradas desde 1). Un "sí" en estas es rojo:
#   1 condición cardíaca / actividad solo supervisada, 2 dolor de pecho al hacer actividad,
#   3 dolor de pecho en reposo el último mes.
PARQ_NUM_PREGUNTAS = 7
PARQ_CRITICAS = (1, 2, 3)

# --- Semáforo AMARILLO (rutina con restricciones + aprobación del coach) -----
AMARILLO_PRESION_SISTOLICA = 140  # mmHg: sistólica >= 140 ...
AMARILLO_PRESION_DIASTOLICA = 90  # mmHg: ... o diastólica >= 90
# Además: cualquier "sí" en el PAR-Q+ o cualquier lesión declarada => amarillo.
# Todo lo demás => verde.

# --- Lesión declarada => máquinas que NUNCA se asignan -----------------------
LESION_MAQUINAS_EXCLUIDAS: dict[str, tuple[str, ...]] = {
    'rodilla': ('M-02', 'M-03'),          # sentadilla en Smith, hack squat
    'hombro': ('M-08', 'M-14'),           # press banca, press militar
    'espalda_baja': ('M-06', 'M-02'),     # peso muerto rumano, sentadilla en Smith
    'cadera': ('M-05', 'M-06'),           # hip thrust, peso muerto rumano
}

# --- Rutina por color de semáforo -------------------------------------------
RUTINA_POR_SEMAFORO = {
    'verde': {'series': 3, 'repeticiones': 12, 'descansoSeg': 60},
    'amarillo': {'series': 2, 'repeticiones': 10, 'descansoSeg': 90},   # carga reducida
}

# --- Riesgo de abandono (probabilidad) ---------------------------------------
RIESGO_ALTO = 0.60
RIESGO_MEDIO = 0.35

# --- Sesión de estación y videos ---------------------------------------------
SESION_VIGENCIA_MIN = 30      # una estación solo opera sobre un socio con sesión abierta
VIDEO_URL_TTL_SEG = 15 * 60   # URL firmada de Cloudflare R2: 15 minutos
