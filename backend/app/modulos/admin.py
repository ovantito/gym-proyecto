"""Administración de coaches y asignación de socios. SOLO el admin: un coach recibe 403.

Reasignar mueve también el trabajo pendiente (alertas abiertas y rutinas por aprobar) para que no quede huérfano,
y cada movimiento queda en `reasignaciones` (historial auditable). El traspaso masivo usa `update_donde`
(un solo UPDATE por tabla) e `insert_muchos` para el historial: nunca un UPDATE por socio.
"""
from __future__ import annotations

import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.repositorio import ahora
from app.core.seguridad import Actor, requiere

router = APIRouter(tags=['admin'], prefix='/admin')

UUID_RE = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'


class Estricto(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class ReasignarIn(Estricto):
    coach_id: str = Field(pattern=UUID_RE)
    motivo: str = Field(min_length=3, max_length=200)


class TraspasoIn(Estricto):
    coach_destino_id: str = Field(pattern=UUID_RE)
    motivo: str = Field(min_length=3, max_length=200)
    desactivar_origen: bool = False


class EstadoCoachIn(Estricto):
    activo: bool


def _coach(repo, coach_id: str) -> dict | None:
    return repo.get('coaches', coach_id)


def _coach_activo(repo, coach_id: str) -> dict:
    c = _coach(repo, coach_id)
    if c is None:
        raise HTTPException(422, 'El coach no existe')
    if not c['activo']:
        raise HTTPException(422, f"El coach {c['nombre']} está inactivo")
    return c


def _mover_trabajo(repo, origen: str, destino: str) -> tuple[int, int]:
    """Alertas sin resolver y rutinas por aprobar pasan al coach nuevo. Devuelve (alertas, rutinas)."""
    a = repo.update_donde('alertas', {'coach_id': destino}, coach_id=origen, resuelta=False)
    r = repo.update_donde('rutinas', {'coach_id': destino}, coach_id=origen, estado='pendiente_aprobacion')
    return a, r


def _mover_trabajo_de_socio(repo, socio_id: str, destino: str) -> None:
    for a in repo.find('alertas', socio_id=socio_id, resuelta=False):
        repo.update('alertas', a['id'], {'coach_id': destino})
    for r in repo.find('rutinas', socio_id=socio_id, estado='pendiente_aprobacion'):
        repo.update('rutinas', r['id'], {'coach_id': destino})


def _vista_socio(repo, socio: dict) -> dict:
    nombres = {c['id']: c['nombre'] for c in repo.find('coaches')}
    filas = sorted(repo.find('reasignaciones', socio_id=socio['id']), key=lambda h: h['fecha'], reverse=True)[:10]
    return {'id': socio['id'], 'nombre': socio['nombre'], 'dni': socio.get('dni'), 'plan': socio.get('plan'),
            'semaforo': socio.get('semaforo'),
            'coach': {'id': socio.get('coach_id'), 'nombre': nombres.get(socio.get('coach_id'))},
            'historial': [{'id': h['id'], 'fecha': h['fecha'], 'motivo': h['motivo'], 'loteId': h.get('lote_id'),
                           'coachAntes': {'id': h.get('coach_antes'), 'nombre': nombres.get(h.get('coach_antes'))},
                           'coachDespues': {'id': h['coach_despues'], 'nombre': nombres.get(h['coach_despues'])}} for h in filas]}


@router.get('/coaches')
def listar_coaches(request: Request, _: Actor = Depends(requiere('admin'))):
    repo = request.app.state.repo
    socios = Counter(s['coach_id'] for s in repo.find('socios'))
    alertas = Counter(a['coach_id'] for a in repo.find('alertas', resuelta=False))
    rutinas = Counter(r['coach_id'] for r in repo.find('rutinas', estado='pendiente_aprobacion'))
    filas = [{'id': c['id'], 'nombre': c['nombre'], 'email': c['email'], 'activo': c['activo'], 'socios': socios[c['id']],
              'alertasAbiertas': alertas[c['id']], 'rutinasPendientes': rutinas[c['id']]} for c in repo.find('coaches')]
    return sorted(filas, key=lambda c: c['nombre'])


@router.get('/socios')
def buscar_socio(request: Request, dni: str = Query(pattern=r'^\d{8}$'), _: Actor = Depends(requiere('admin'))):
    repo = request.app.state.repo
    encontrados = repo.find('socios', dni=dni)
    if not encontrados:
        raise HTTPException(404, 'Socio no encontrado')
    return _vista_socio(repo, encontrados[0])


@router.post('/socios/{socio_id}/reasignar')
def reasignar_socio(request: Request, socio_id: str, datos: ReasignarIn, actor: Actor = Depends(requiere('admin'))):
    repo = request.app.state.repo
    socio = repo.get('socios', socio_id)
    if socio is None:
        raise HTTPException(404, 'Socio no encontrado')
    nuevo = _coach_activo(repo, datos.coach_id)
    if socio.get('coach_id') == nuevo['id']:
        raise HTTPException(409, 'Ya es su coach')
    antes = socio.get('coach_id')
    repo.update('socios', socio_id, {'coach_id': nuevo['id']})
    _mover_trabajo_de_socio(repo, socio_id, nuevo['id'])
    repo.insert('reasignaciones', {'socio_id': socio_id, 'coach_antes': antes, 'coach_despues': nuevo['id'], 'motivo': datos.motivo,
                                   'hecho_por': actor.id, 'lote_id': None, 'fecha': ahora()})
    return _vista_socio(repo, repo.get('socios', socio_id))


@router.post('/coaches/{coach_id}/traspasar')
def traspasar_coach(request: Request, coach_id: str, datos: TraspasoIn, actor: Actor = Depends(requiere('admin'))):
    repo = request.app.state.repo
    if _coach(repo, coach_id) is None:
        raise HTTPException(422, 'El coach de origen no existe')
    destino = _coach_activo(repo, datos.coach_destino_id)
    if coach_id == destino['id']:
        raise HTTPException(409, 'El coach de origen y el de destino son el mismo')
    socios = repo.find('socios', coach_id=coach_id)
    lote, fecha = str(uuid.uuid4()), ahora()
    movidos = repo.update_donde('socios', {'coach_id': destino['id']}, coach_id=coach_id) if socios else 0
    alertas, rutinas = _mover_trabajo(repo, coach_id, destino['id'])
    repo.insert_muchos('reasignaciones', [
        {'socio_id': s['id'], 'coach_antes': coach_id, 'coach_despues': destino['id'], 'motivo': datos.motivo,
         'hecho_por': actor.id, 'lote_id': lote, 'fecha': fecha} for s in socios])
    if datos.desactivar_origen:
        repo.update('coaches', coach_id, {'activo': False})
    return {'sociosMovidos': movidos, 'alertasMovidas': alertas, 'rutinasMovidas': rutinas, 'loteId': lote}


@router.patch('/coaches/{coach_id}')
def cambiar_estado_coach(request: Request, coach_id: str, datos: EstadoCoachIn, _: Actor = Depends(requiere('admin'))):
    repo = request.app.state.repo
    c = _coach(repo, coach_id)
    if c is None:
        raise HTTPException(404, 'Coach no encontrado')
    if not datos.activo:
        n = len(repo.find('socios', coach_id=coach_id))
        if n:
            raise HTTPException(409, f'Primero traspasa sus {n} socios')
    return repo.update('coaches', coach_id, {'activo': datos.activo})
