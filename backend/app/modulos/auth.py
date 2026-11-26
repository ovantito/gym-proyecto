"""Login del panel. Devuelve un JWT que el resto del backend ya sabe validar.

- Modo demo (sin Supabase): usuarios de prueba en memoria; el backend firma el JWT con su propio secreto.
- Con Supabase: se delega en Supabase Auth (contraseña) y se devuelve su access_token tras validarlo.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.core.limites import limiter
from app.core.seguridad import decodificar_jwt

router = APIRouter(tags=['auth'])
DURACION_TOKEN_SEG = 8 * 3600
MSG_MALO = 'Correo o contraseña incorrectos'


class LoginIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    email: str = Field(min_length=5, max_length=120, pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    password: str = Field(min_length=1, max_length=200)


def hash_password(password: str, sal: bytes | None = None) -> tuple[str, str]:
    sal = sal or secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode(), salt=sal, n=2**14, r=8, p=1)
    return sal.hex(), h.hex()


def verificar_password(password: str, sal_hex: str, hash_hex: str) -> bool:
    _, h = hash_password(password, bytes.fromhex(sal_hex))
    return hmac.compare_digest(h, hash_hex)


@router.post('/auth/login')
@limiter.limit(lambda: get_settings().rate_limit_login)
def login(request: Request, datos: LoginIn):
    cfg, repo = request.app.state.settings, request.app.state.repo
    if cfg.usa_supabase:
        return _login_supabase(cfg, datos)
    usuarios = repo.find('usuarios', email=datos.email.lower())
    u = usuarios[0] if usuarios else None
    if u is None:   # se hace el mismo trabajo con y sin usuario para no revelar cuál existe
        verificar_password(datos.password, '00' * 16, '00' * 64)
        raise HTTPException(401, MSG_MALO)
    if not verificar_password(datos.password, u['sal'], u['password_hash']):
        raise HTTPException(401, MSG_MALO)
    token = jwt.encode({'sub': u['user_id'], 'aud': cfg.jwt_audience, 'exp': int(time.time()) + DURACION_TOKEN_SEG,
                        'app_metadata': {'role': u['rol']}, 'email': u['email']}, cfg.supabase_jwt_secret, algorithm='HS256')
    return {'token': token, 'rol': u['rol'], 'nombre': u['nombre'], 'expiraEnSeg': DURACION_TOKEN_SEG}


def _login_supabase(cfg, datos: LoginIn):
    if not cfg.supabase_publishable_key:
        raise HTTPException(503, 'Falta SUPABASE_PUBLISHABLE_KEY en el servidor')
    try:
        r = httpx.post(f'{cfg.supabase_url.rstrip("/")}/auth/v1/token', params={'grant_type': 'password'},
                       headers={'apikey': cfg.supabase_publishable_key}, json={'email': datos.email, 'password': datos.password}, timeout=15)
    except httpx.HTTPError as e:
        raise HTTPException(503, 'No se pudo contactar a Supabase Auth') from e
    if r.status_code != 200:
        raise HTTPException(401, MSG_MALO)
    token = r.json()['access_token']
    actor = decodificar_jwt(token, cfg.supabase_jwt_secret, cfg.jwt_audience)   # valida firma y rol
    if actor.rol not in ('coach', 'admin'):
        raise HTTPException(403, 'Este panel es solo para coach y admin')
    return {'token': token, 'rol': actor.rol, 'nombre': datos.email, 'expiraEnSeg': r.json().get('expires_in', DURACION_TOKEN_SEG)}
