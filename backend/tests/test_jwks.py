"""Validación de JWT con claves asimétricas (JWKS de Supabase), sin red: se simula el cliente JWKS."""
import time
from types import SimpleNamespace

import jwt
import pytest
from app.core import seguridad
from cryptography.hazmat.primitives.asymmetric import ec


def _token(clave_privada, rol='admin', alg='ES256'):
    return jwt.encode({'sub': 'u-1', 'aud': 'authenticated', 'exp': int(time.time()) + 600, 'app_metadata': {'role': rol}},
                      clave_privada, algorithm=alg, headers={'kid': 'k1'})


@pytest.fixture
def jwks(app, monkeypatch):
    buena = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(app.state.settings, 'supabase_jwks_url', 'https://proyecto.example/auth/v1/.well-known/jwks.json')
    monkeypatch.setattr(seguridad, '_cliente_jwks',
                        lambda url: SimpleNamespace(get_signing_key_from_jwt=lambda t: SimpleNamespace(key=buena.public_key())))
    return buena


def test_jwt_es256_firmado_por_supabase_es_aceptado(client, jwks):
    r = client.get('/v1/coach/alertas', headers={'Authorization': f'Bearer {_token(jwks)}'})
    assert r.status_code == 200


def test_jwt_es256_firmado_con_otra_clave_da_401(client, jwks):
    falsa = ec.generate_private_key(ec.SECP256R1())
    assert client.get('/v1/coach/alertas', headers={'Authorization': f'Bearer {_token(falsa)}'}).status_code == 401


def test_rol_incorrecto_en_jwt_asimetrico_da_403(client, jwks):
    r = client.get('/v1/coach/alertas', headers={'Authorization': f"Bearer {_token(jwks, rol='socio')}"})
    assert r.status_code == 403


def test_es256_sin_jwks_configurado_da_401(client):
    clave = ec.generate_private_key(ec.SECP256R1())
    assert client.get('/v1/coach/alertas', headers={'Authorization': f'Bearer {_token(clave)}'}).status_code == 401


def test_token_alg_none_es_rechazado(client):
    falso = jwt.encode({'sub': 'x', 'aud': 'authenticated', 'exp': int(time.time()) + 60, 'app_metadata': {'role': 'admin'}}, None,
                       algorithm='none')
    assert client.get('/v1/coach/alertas', headers={'Authorization': f'Bearer {falso}'}).status_code == 401
