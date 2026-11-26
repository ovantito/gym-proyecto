"""Generación del escenario simulado (Script 1 del Colab), idéntica y con semilla 42.

IMPORTANTE: el orden de las llamadas a `rng` es el del Colab. No reordenar ni
agregar llamadas intermedias, o los datos (y las métricas) cambian.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SEED = 42

# --- 1.1 Sala: máquinas, patrón de movimiento, posición (m) y popularidad relativa
MAQUINAS = pd.DataFrame([
    ('M-01', 'Prensa 45°', 'Rodilla dominante', 4, 3, 1.2), ('M-02', 'Sentadilla en Smith', 'Rodilla dominante', 8, 3, 1.4),
    ('M-03', 'Hack squat', 'Rodilla dominante', 12, 3, 0.9),
    ('M-04', 'Curl femoral', 'Cadera dominante', 4, 8, 0.8), ('M-05', 'Hip thrust', 'Cadera dominante', 8, 8, 1.3),
    ('M-06', 'Peso muerto rumano', 'Cadera dominante', 12, 8, 0.9),
    ('M-07', 'Press de pecho', 'Empuje horizontal', 18, 3, 1.3), ('M-08', 'Press banca', 'Empuje horizontal', 22, 3, 1.5),
    ('M-09', 'Aperturas en máquina', 'Empuje horizontal', 26, 3, 0.7),
    ('M-10', 'Jalón al pecho', 'Tirón vertical', 18, 9, 1.2), ('M-11', 'Dominadas asistidas', 'Tirón vertical', 22, 9, 0.6),
    ('M-12', 'Remo en polea', 'Tirón vertical', 26, 9, 1.0),
    ('M-13', 'Press de hombro', 'Empuje vertical', 18, 15, 1.0), ('M-14', 'Press militar', 'Empuje vertical', 22, 15, 0.9),
    ('M-15', 'Elevaciones laterales', 'Empuje vertical', 26, 15, 0.8),
    ('M-16', 'Crunch en máquina', 'Core', 6, 15, 0.6), ('M-17', 'Plancha en banco', 'Core', 9, 15, 0.4),
    ('M-18', 'Rueda abdominal', 'Core', 12, 15, 0.5),
], columns=['codigo', 'nombre', 'patron', 'x', 'y', 'popularidad']).set_index('codigo')
PATRONES = list(MAQUINAS['patron'].unique())
ESTACION = (2.0, 18.0)   # ubicación de la Estación TNT Fit (entrada de la sala)
VEL_M_MIN = 50.0         # metros por minuto caminando dentro de la sala
CAMBIO_MIN = 0.5         # minutos para acomodarse en una máquina

HORAS = list(range(6, 22))
BASE_HORA = {6: 28, 7: 42, 8: 30, 9: 18, 10: 12, 11: 10, 12: 14, 13: 16, 14: 10, 15: 12, 16: 18, 17: 30, 18: 46, 19: 52, 20: 40, 21: 22}
FACTOR_DIA = {0: 1.15, 1: 1.10, 2: 1.05, 3: 1.00, 4: 0.90, 5: 0.70, 6: 0.45}   # lunes=0 ... domingo=6

PERFILES = {
    'constante_manana':  dict(p=0.30, visitas=(4.2, 0.8), dias=(1.5, 1.2), antig=(18, 8),  hora=(7, 1.0),    edad=(34, 8)),
    'nocturno_intermit': dict(p=0.30, visitas=(2.4, 0.8), dias=(5, 3),     antig=(8, 5),   hora=(19.5, 1.0), edad=(27, 6)),
    'principiante':      dict(p=0.25, visitas=(1.6, 0.7), dias=(9, 5),     antig=(1.5, 1), hora=(18, 2.5),   edad=(24, 6)),
    'fin_de_semana':     dict(p=0.15, visitas=(1.8, 0.5), dias=(4, 2),     antig=(24, 10), hora=(10, 1.5),   edad=(41, 9)),
}
N_SOCIOS = 3000
N_SESIONES = 12000


def generar_datos(seed: int = SEED) -> dict[str, pd.DataFrame]:
    """Devuelve {'afluencia', 'socios', 'sesiones'} (mismo orden de RNG que el Colab)."""
    rng = np.random.default_rng(seed)

    # --- 1.2 Afluencia por franja (socios en sala)
    fechas = pd.date_range('2026-01-05', periods=150, freq='D')
    filas = []
    for f in fechas:
        feriado = int(rng.random() < 0.03)
        for h in HORAS:
            mes_factor = 1.20 if f.month == 1 else (1.08 if f.month in (2, 3) else 1.0)
            ocup = BASE_HORA[h] * FACTOR_DIA[f.dayofweek] * mes_factor * (0.6 if feriado else 1) + rng.normal(0, 3)
            filas.append((f.date(), f.dayofweek, f.month, h, feriado, max(0, round(ocup))))
    afluencia = pd.DataFrame(filas, columns=['fecha', 'dia_semana', 'mes', 'hora', 'feriado', 'ocupacion'])

    # --- 1.3 Socios: 4 perfiles latentes de comportamiento
    n = N_SOCIOS
    nombres = list(PERFILES)
    probs = [PERFILES[k]['p'] for k in nombres]
    perf = rng.choice(nombres, size=n, p=probs)

    def g(k, campo, lo=0):
        m, s = PERFILES[k][campo]
        return max(lo, rng.normal(m, s))

    socios = pd.DataFrame({
        'perfil_real': perf,
        'edad': [round(g(k, 'edad', 16)) for k in perf],
        'antiguedad_meses': [round(g(k, 'antig', 0.5), 1) for k in perf],
        'visitas_semana': [round(g(k, 'visitas', 0.2), 1) for k in perf],
        'dias_ultima_visita': [round(g(k, 'dias', 0)) for k in perf],
        'hora_preferida': [round(min(21, max(6, g(k, 'hora'))), 1) for k in perf],
    })
    socios['plan'] = rng.choice(['mensual', 'trimestral', 'anual'], size=n, p=[0.55, 0.25, 0.20])
    socios['semaforo'] = rng.choice(['verde', 'amarillo', 'rojo'], size=n, p=[0.78, 0.19, 0.03])
    socios['racha_semanas'] = np.clip((socios['visitas_semana'] * 1.6 + rng.normal(0, 1.5, n)).round(), 0, None)
    socios['var_grasa_pct'] = np.round(-0.35 * socios['visitas_semana'] + rng.normal(0.6, 1.0, n), 2)   # negativo = progreso
    socios['sesiones_estacion'] = np.clip((socios['visitas_semana'] * 4 * 0.6 + rng.normal(0, 2, n)).round(), 0, None)
    socios['coach_contacto_30d'] = (rng.random(n) < 0.35).astype(int)
    logit = (-1.0 + 0.16 * socios['dias_ultima_visita'] - 0.55 * socios['visitas_semana'] - 0.035 * socios['antiguedad_meses']
             + 0.55 * (socios['plan'] == 'mensual') - 0.25 * (socios['plan'] == 'anual') + 0.45 * socios['var_grasa_pct']
             - 0.12 * socios['racha_semanas'] - 0.45 * socios['coach_contacto_30d'] + 0.35 * (socios['semaforo'] != 'verde')
             + rng.normal(0, 0.3, n))
    socios['abandono_30d'] = (rng.random(n) < 1 / (1 + np.exp(-1.4 * logit))).astype(int)

    # --- 1.4 Sesiones de la estación (lecturas de sensores) con 2 % de lecturas defectuosas
    m_ = N_SESIONES
    ses = pd.DataFrame({
        'delta_peso_kg': rng.normal(0, 0.8, m_),
        'delta_grasa_pct': rng.normal(-0.1, 0.5, m_),
        'presion_sistolica': rng.normal(122, 11, m_),
        'duracion_seg': rng.normal(210, 45, m_),
    })
    ses['defectuosa'] = 0
    idx = rng.choice(m_, size=int(m_ * 0.02), replace=False)
    tipo = rng.integers(0, 3, len(idx))
    for t, col, lo, hi in [(0, 'delta_peso_kg', 3, 8), (1, 'delta_grasa_pct', 3, 7), (2, 'duracion_seg', 150, 500)]:
        sel = idx[tipo == t]
        signo = rng.choice([-1, 1], len(sel)) if t < 2 else 1
        ses.loc[sel, col] += signo * rng.uniform(lo, hi, len(sel))
    ses.loc[idx, 'defectuosa'] = 1

    return {'afluencia': afluencia, 'socios': socios, 'sesiones': ses}


if __name__ == '__main__':
    d = generar_datos()
    print({k: len(v) for k, v in d.items()}, f"abandono={d['socios'].abandono_30d.mean():.1%}")
