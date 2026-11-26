"""Autenticación y autorización.

- Estación: cabecera X-Station-Key (una clave por dispositivo, guardada solo como hash SHA-256).
- Coach/admin/socio: JWT de Supabase Auth (HS256) validado aquí; el rol viene en app_metadata.role.
- Un coach solo accede a SUS socios; una estación solo a un socio con sesión abierta en ella.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException, Request

from app.core.umbrales import SESION_VIGENCIA_MIN

ROLES = ('socio', 'coach', 'admin', 'estacion')


def generar_clave_estacion() -> str:
    return 'tnt_' + secrets.token_urlsafe(32)


def hash_clave(clave: str) -> str:
    # Las claves son aleatorias de 256 bits: un SHA-256 simple es suficiente (no son contraseñas humanas).
    return hashlib.sha256(clave.encode()).hexdigest()


@dataclass
class Actor:
    rol: str
    id: str | None = None          # id de usuario (JWT) o de la estación
    estacion_id: str | None = None


def _no_autenticado(msg: str = 'Credenciales inválidas o ausentes') -> HTTPException:
    return HTTPException(401, msg, headers={'WWW-Authenticate': 'Bearer'})


def decodificar_jwt(token: str, secreto: str | None, audiencia: str) -> Actor:
    if not secreto:
        raise _no_autenticado('JWT no configurado en el servidor')
    try:
        datos = jwt.decode(token, secreto, algorithms=['HS256'], audience=audiencia, options={'require': ['exp', 'sub']})
    except jwt.PyJWTError as e:
        raise _no_autenticado(f'Token inválido: {e.__class__.__name__}') from e
    rol = (datos.get('app_metadata') or {}).get('role')
    if rol not in ROLES or rol == 'estacion':
        raise HTTPException(403, 'Rol no permitido')
    return Actor(rol=rol, id=datos['sub'])


def obtener_actor(request: Request, x_station_key: str | None = Header(default=None),
                  authorization: str | None = Header(default=None)) -> Actor:
    app = request.app
    if x_station_key:
        h = hash_clave(x_station_key)
        for est in app.state.repo.find('estaciones', clave_hash=h):
            if est.get('activa', True) and hmac.compare_digest(est['clave_hash'], h):
                return Actor(rol='estacion', id=est['id'], estacion_id=est['id'])
        raise _no_autenticado('X-Station-Key inválida')
    if authorization and authorization.lower().startswith('bearer '):
        return decodificar_jwt(authorization[7:].strip(), app.state.settings.supabase_jwt_secret,
                               app.state.settings.jwt_audience)
    raise _no_autenticado()


def requiere(*roles: str):
    """Dependencia: exige alguno de los roles dados."""
    def dep(actor: Actor = Depends(obtener_actor)) -> Actor:
        if actor.rol not in roles:
            raise HTTPException(403, 'No tienes permiso para esta operación')
        return actor
    return dep


def sesion_activa(repo, estacion_id: str, socio_id: str) -> bool:
    limite = datetime.now(timezone.utc) - timedelta(minutes=SESION_VIGENCIA_MIN)
    for s in repo.find('sesiones', estacion_id=estacion_id, socio_id=socio_id):
        if datetime.fromisoformat(s['inicio']) >= limite:
            return True
    return False


def autorizar_socio(request: Request, actor: Actor, socio_id: str) -> dict:
    """Devuelve el socio si el actor puede operar sobre él; si no, 403/404."""
    repo = request.app.state.repo
    socio = repo.get('socios', socio_id)
    if socio is None:
        raise HTTPException(404, 'Socio no encontrado')
    if actor.rol == 'admin':
        return socio
    if actor.rol == 'coach' and socio.get('coach_id') == actor.id:
        return socio
    if actor.rol == 'socio' and socio.get('user_id') == actor.id:
        return socio
    if actor.rol == 'estacion' and sesion_activa(repo, actor.estacion_id, socio_id):
        return socio
    raise HTTPException(403, 'No tienes acceso a este socio')
