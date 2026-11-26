import os
import time

# Configuración de prueba ANTES de importar la app (no son claves reales).
os.environ.update({
    'SUPABASE_URL': '', 'SUPABASE_SERVICE_KEY': '',          # => repositorio en memoria
    'SUPABASE_JWT_SECRET': 'secreto-de-prueba-con-32-bytes-minimo!!',
    'DEMO_STATION_KEY': 'clave-de-prueba-estacion',
    'RATE_LIMIT_DEFECTO': '100000/minute', 'RATE_LIMIT_SESIONES': '100000/minute',
    'R2_ACCOUNT_ID': 'cuenta-prueba', 'R2_ACCESS_KEY_ID': 'AKIAPRUEBA', 'R2_SECRET_ACCESS_KEY': 'secreto-prueba',
    'R2_BUCKET': 'tnt-videos',
})

import jwt  # noqa: E402
import pytest  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.semilla import COACHES  # noqa: E402
from app.main import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

CLAVE = 'clave-de-prueba-estacion'


def token(rol: str, sub: str) -> dict:
    t = jwt.encode({'sub': sub, 'aud': 'authenticated', 'exp': int(time.time()) + 600, 'app_metadata': {'role': rol}},
                   get_settings().supabase_jwt_secret, algorithm='HS256')
    return {'Authorization': f'Bearer {t}'}


@pytest.fixture(scope='session')
def app():
    return create_app()


@pytest.fixture(scope='session')
def client(app):
    return TestClient(app)


@pytest.fixture(scope='session')
def est_headers():
    return {'X-Station-Key': CLAVE}


@pytest.fixture(scope='session')
def estacion_id(app):
    return app.state.repo.find('estaciones')[0]['id']


@pytest.fixture
def abrir_sesion(client, est_headers, estacion_id):
    """Abre una sesión por DNI (el socio nº i) y devuelve su id."""
    def _abrir(i: int = 0) -> str:
        r = client.post(f'/v1/estaciones/{estacion_id}/sesiones', json={'dni': str(10000000 + i)}, headers=est_headers)
        assert r.status_code == 201, r.text
        return r.json()['socio']['id']
    return _abrir


@pytest.fixture
def coach0():
    return token('coach', COACHES[0])


@pytest.fixture
def admin():
    return token('admin', 'admin-1')
