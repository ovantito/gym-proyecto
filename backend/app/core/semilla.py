"""Datos de demo: los 3,000 socios simulados (semilla 42) y una estación.

Se usa en el modo en memoria y en supabase/seed.py. var_grasa_pct NO se guarda en el socio
(dato de salud; el modelo de abandono no lo usa).
"""
from __future__ import annotations

import secrets
import uuid

from app.core.seguridad import generar_clave_estacion, hash_clave
from ml.datos import generar_datos

NS = uuid.UUID('6f1c1b2e-0000-4000-8000-00000000d1a5')
COACHES = [str(uuid.uuid5(NS, f'coach-{i}')) for i in range(5)]
CAMPOS = ['edad', 'antiguedad_meses', 'visitas_semana', 'dias_ultima_visita', 'hora_preferida', 'plan',
          'semaforo', 'racha_semanas', 'sesiones_estacion', 'coach_contacto_30d']


def socios_simulados(coaches: list[str] | None = None) -> list[dict]:
    coaches = coaches or COACHES
    df = generar_datos()['socios']
    filas = []
    for i, r in enumerate(df[CAMPOS].to_dict('records')):
        fila = {k: (v.item() if hasattr(v, 'item') else v) for k, v in r.items()}
        fila.update(dni=str(10000000 + i), qr=f'TNT-{i + 1:05d}', nombre=f'Socio {i + 1:04d}',
                    coach_id=coaches[i % len(coaches)], user_id=None, segmento=None, riesgo_abandono=None,
                    nivel_riesgo=None)
        filas.append(fila)
    return filas


def sembrar(repo, clave_estacion: str | None = None, coaches: list[str] | None = None) -> tuple[dict, str]:
    """Carga socios + una estación. Devuelve (estación, clave en claro; solo se muestra una vez)."""
    repo.insert_muchos('socios', socios_simulados(coaches))
    clave = clave_estacion or generar_clave_estacion()
    est = repo.insert('estaciones', {'nombre': 'Estación piloto', 'clave_hash': hash_clave(clave), 'activa': True})
    return est, clave


def sembrar_usuarios(repo, pass_coach: str | None = None, pass_admin: str | None = None) -> list[dict]:
    """Usuarios de prueba del panel (solo modo demo en memoria). Devuelve email/contraseña/rol para imprimirlos."""
    from app.modulos.auth import hash_password
    demo = [
        ('coach@tnt.demo', pass_coach or secrets.token_urlsafe(9), 'coach', 'Coach Demo', COACHES[0]),
        ('coach2@tnt.demo', secrets.token_urlsafe(9), 'coach', 'Coach Demo 2', COACHES[1]),
        ('admin@tnt.demo', pass_admin or secrets.token_urlsafe(9), 'admin', 'Admin Demo', str(uuid.uuid5(NS, 'admin'))),
    ]
    salida = []
    for email, pw, rol, nombre, uid in demo:
        sal, h = hash_password(pw)
        repo.insert('usuarios', {'email': email, 'sal': sal, 'password_hash': h, 'rol': rol, 'nombre': nombre, 'user_id': uid})
        salida.append({'email': email, 'password': pw, 'rol': rol})
    return salida
