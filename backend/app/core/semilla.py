"""Datos de demo: los 3,000 socios simulados (semilla 42) y una estación.

Se usa en el modo en memoria y en supabase/seed.py. var_grasa_pct NO se guarda en el socio
(dato de salud; el modelo de abandono no lo usa).
"""
from __future__ import annotations

import uuid

from app.core.seguridad import generar_clave_estacion, hash_clave
from ml.datos import generar_datos

NS = uuid.UUID('6f1c1b2e-0000-4000-8000-00000000d1a5')
COACHES = [str(uuid.uuid5(NS, f'coach-{i}')) for i in range(5)]
CAMPOS = ['edad', 'antiguedad_meses', 'visitas_semana', 'dias_ultima_visita', 'hora_preferida', 'plan',
          'semaforo', 'racha_semanas', 'sesiones_estacion', 'coach_contacto_30d']


def socios_simulados() -> list[dict]:
    df = generar_datos()['socios']
    filas = []
    for i, r in enumerate(df[CAMPOS].to_dict('records')):
        fila = {k: (v.item() if hasattr(v, 'item') else v) for k, v in r.items()}
        fila.update(dni=str(10000000 + i), qr=f'TNT-{i + 1:05d}', nombre=f'Socio {i + 1:04d}',
                    coach_id=COACHES[i % len(COACHES)], user_id=None, segmento=None, riesgo_abandono=None,
                    nivel_riesgo=None)
        filas.append(fila)
    return filas


def sembrar(repo, clave_estacion: str | None = None) -> tuple[dict, str]:
    """Carga socios + una estación. Devuelve (estación, clave en claro; solo se muestra una vez)."""
    repo.insert_muchos('socios', socios_simulados())
    clave = clave_estacion or generar_clave_estacion()
    est = repo.insert('estaciones', {'nombre': 'Estación piloto', 'clave_hash': hash_clave(clave), 'activa': True})
    return est, clave
