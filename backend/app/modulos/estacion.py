"""Microservicio Estación: identifica al socio (DNI o QR) y abre una sesión."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import get_settings
from app.core.limites import limiter
from app.core.repositorio import ahora
from app.core.seguridad import Actor, requiere
from app.schemas import SesionIn

router = APIRouter(tags=['estacion'])


@router.post('/estaciones/{estacion_id}/sesiones', status_code=201)
@limiter.limit(lambda: get_settings().rate_limit_sesiones)
def abrir_sesion(request: Request, estacion_id: str, datos: SesionIn, actor: Actor = Depends(requiere('estacion'))):
    if actor.estacion_id != estacion_id:   # una estación no puede abrir sesiones en nombre de otra
        raise HTTPException(403, 'La clave no corresponde a esta estación')
    repo = request.app.state.repo
    campo, valor = ('dni', datos.dni) if datos.dni else ('qr', datos.qr)
    encontrados = repo.find('socios', **{campo: valor})
    if not encontrados:
        raise HTTPException(404, 'Socio no encontrado')
    socio = encontrados[0]
    ses = repo.insert('sesiones', {'estacion_id': estacion_id, 'socio_id': socio['id'], 'inicio': ahora()})
    # Solo datos mínimos: nada de salud (la ficha es un recurso aparte).
    return {'sesionId': ses['id'], 'socio': {'id': socio['id'], 'nombre': socio['nombre'], 'semaforo': socio['semaforo']}}
