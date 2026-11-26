"""Microservicio Coach: alertas y aprobación de rutinas. Un coach solo ve a SUS socios; admin ve todo."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.repositorio import ahora
from app.core.seguridad import Actor, requiere

router = APIRouter(tags=['coach'])


def _filtro(actor: Actor) -> dict:
    return {} if actor.rol == 'admin' else {'coach_id': actor.id}


@router.get('/coach/alertas')
def alertas(request: Request, actor: Actor = Depends(requiere('coach', 'admin'))):
    filas = request.app.state.repo.find('alertas', resuelta=False, **_filtro(actor))
    return sorted(filas, key=lambda a: a['creada'], reverse=True)


@router.get('/coach/rutinas-pendientes')
def rutinas_pendientes(request: Request, actor: Actor = Depends(requiere('coach', 'admin'))):
    filas = request.app.state.repo.find('rutinas', estado='pendiente_aprobacion', **_filtro(actor))
    return sorted(filas, key=lambda r: r['creada'])


@router.post('/coach/rutinas/{rutina_id}/aprobar')
def aprobar(request: Request, rutina_id: str, actor: Actor = Depends(requiere('coach', 'admin'))):
    repo = request.app.state.repo
    rutina = repo.get('rutinas', rutina_id)
    if rutina is None:
        raise HTTPException(404, 'Rutina no encontrada')
    if actor.rol == 'coach' and rutina.get('coach_id') != actor.id:
        raise HTTPException(403, 'Esta rutina no es de uno de tus socios')
    if rutina['estado'] != 'pendiente_aprobacion':
        raise HTTPException(409, f"La rutina está en estado '{rutina['estado']}'")
    nueva = repo.update('rutinas', rutina_id, {'estado': 'activa', 'aprobada_por': actor.id, 'aprobada_en': ahora()})
    for a in repo.find('alertas', rutina_id=rutina_id, resuelta=False):
        repo.update('alertas', a['id'], {'resuelta': True})
    return nueva
