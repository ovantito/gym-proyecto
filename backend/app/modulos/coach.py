"""Microservicio Coach: todo lo que ve el panel. Un coach solo ve a SUS socios; el admin ve todo."""
from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.repositorio import ahora
from app.core.seguridad import Actor, requiere
from app.core.umbrales import LESION_MAQUINAS_EXCLUIDAS, PARQ_CRITICAS, PARQ_NUM_PREGUNTAS
from app.modulos.salud import _alerta, _aplicar_ficha, ficha_publica, recalcular_ficha, ultima_medicion_valida

router = APIRouter(tags=['coach'])


class MotivoIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    motivo: str = Field(min_length=3, max_length=200)


def _filtro(actor: Actor, coach_id: str | None = None) -> dict:
    """Qué filas ve el actor. El admin ve todo o, con `coach_id`, el panel de ese coach («ver como»).
    Un coach ve SIEMPRE lo suyo: si manda `coach_id` se ignora, para que no pueda espiar a otro coach."""
    if actor.rol != 'admin':
        return {'coach_id': actor.id}
    return {'coach_id': coach_id} if coach_id else {}


# Parámetro opcional ?coach_id=<uuid> de los listados (validado como UUID). Solo lo respeta el admin.
CoachVista = Annotated[UUID | None, Query(description='Solo admin: ver el panel de este coach')]


def _vista(coach_id: UUID | None) -> str | None:
    return str(coach_id) if coach_id else None


def _socios_visibles(repo, actor: Actor, coach_id: str | None = None) -> list[dict]:
    return repo.find('socios', **_filtro(actor, coach_id))


def _nombre(repo, socio_id: str | None) -> str:
    s = repo.get('socios', socio_id) if socio_id else None
    return s['nombre'] if s else '—'


# ------------------------------------------------------------------ alertas
@router.get('/coach/alertas')
def alertas(request: Request, coach_id: CoachVista = None, actor: Actor = Depends(requiere('coach', 'admin'))):
    repo = request.app.state.repo
    filas = repo.find('alertas', resuelta=False, **_filtro(actor, _vista(coach_id)))
    for a in filas:
        a['socioNombre'] = _nombre(repo, a.get('socio_id'))
    return sorted(filas, key=lambda a: a['creada'], reverse=True)


@router.post('/coach/alertas/{alerta_id}/atender')
def atender_alerta(request: Request, alerta_id: str, actor: Actor = Depends(requiere('coach', 'admin'))):
    """"Registrar contacto": marca la alerta como atendida y anota el contacto del coach en el socio."""
    repo = request.app.state.repo
    a = repo.get('alertas', alerta_id)
    if a is None:
        raise HTTPException(404, 'Alerta no encontrada')
    if actor.rol == 'coach' and a.get('coach_id') != actor.id:
        raise HTTPException(403, 'Esta alerta no es de uno de tus socios')
    if a['socio_id']:
        repo.update('socios', a['socio_id'], {'coach_contacto_30d': 1})
    return repo.update('alertas', alerta_id, {'resuelta': True, 'atendida_por': actor.id, 'atendida_en': ahora()})


# ------------------------------------------------------------------ fichas de salud
class CorreccionFichaIn(BaseModel):
    """El coach reemplaza las condiciones de la ficha; `motivo` es obligatorio y queda en el historial."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    parq: list[bool] = Field(min_length=PARQ_NUM_PREGUNTAS, max_length=PARQ_NUM_PREGUNTAS)
    lesiones: list[str] = Field(default_factory=list, max_length=10)
    motivo: str = Field(min_length=3, max_length=200)

    @model_validator(mode='after')
    def lesiones_conocidas(self):
        malas = [x for x in self.lesiones if x not in LESION_MAQUINAS_EXCLUIDAS]
        if malas:
            raise ValueError(f'Lesión no reconocida: {malas}')
        return self


def _socio_del_coach(repo, actor: Actor, socio_id: str) -> dict:
    socio = repo.get('socios', socio_id)
    if socio is None:
        raise HTTPException(404, 'Socio no encontrado')
    if actor.rol == 'coach' and socio.get('coach_id') != actor.id:
        raise HTTPException(403, 'Este socio no es uno de tus socios')
    return socio


def _vista_ficha(repo, socio: dict) -> dict:
    previas = repo.find('fichas_salud', socio_id=socio['id'])
    historial = sorted(repo.find('fichas_salud_historial', socio_id=socio['id']), key=lambda h: h['fecha'], reverse=True)
    m = ultima_medicion_valida(repo, socio['id'])
    medicion = None if m is None else {
        'pesoKg': m['peso_kg'], 'tallaCm': m.get('talla_cm'), 'imc': m.get('imc'), 'grasaPct': m['grasa_pct'],
        'sistolica': m['presion_sistolica'], 'diastolica': m['presion_diastolica'], 'pulso': m['pulso_reposo'], 'fecha': m['fecha']}
    return {'socio': {'id': socio['id'], 'nombre': socio['nombre'], 'dni': socio.get('dni'), 'semaforo': socio['semaforo']},
            'ficha': ficha_publica(previas[0]) if previas else None, 'medicion': medicion, 'historial': historial}


@router.get('/coach/fichas')
def buscar_ficha(request: Request, dni: str = Query(pattern=r'^\d{8}$'), coach_id: CoachVista = None,
                 actor: Actor = Depends(requiere('coach', 'admin'))):
    """Busca un socio por DNI entre los que el actor puede ver. Un socio de otro coach responde igual que uno inexistente."""
    repo = request.app.state.repo
    socio = next(iter(repo.find('socios', dni=dni, **_filtro(actor, _vista(coach_id)))), None)
    if socio is None:
        raise HTTPException(404, 'No encontramos ese DNI entre tus socios')
    return _vista_ficha(repo, socio)


@router.put('/coach/fichas/{socio_id}')
def corregir_ficha(request: Request, socio_id: str, datos: CorreccionFichaIn, actor: Actor = Depends(requiere('coach', 'admin'))):
    repo = request.app.state.repo
    socio = _socio_del_coach(repo, actor, socio_id)
    previas = repo.find('fichas_salud', socio_id=socio_id)
    if not previas:
        raise HTTPException(409, 'El socio aún no tiene ficha de salud')
    antes = previas[0]
    if antes['parq'] == datos.parq and sorted(antes['lesiones']) == sorted(datos.lesiones):
        raise HTTPException(409, 'No hay ningún cambio que guardar')
    # Recalcula con la última medición. Si estaba bloqueado y ya no sale rojo, la corrección cuenta como liberación.
    nueva = recalcular_ficha(repo, socio_id, datos.parq, datos.lesiones, permite_desbloqueo=True)
    repo.insert('fichas_salud_historial', {
        'socio_id': socio_id, 'motivo': datos.motivo, 'hecho_por': actor.id, 'fecha': ahora(),
        'cambio': _cambio(antes, nueva)})
    if nueva['semaforo'] == 'rojo' and antes['semaforo'] != 'rojo':
        _alerta(repo, socio, 'semaforo_rojo', 'alta', 'Socio en rojo: requiere apto médico antes de entrenar')
    if antes.get('bloqueado') and not nueva.get('bloqueado'):
        _resolver_alertas_rojas(repo, socio_id, actor)
    return _vista_ficha(repo, repo.get('socios', socio_id))


def _cambio(antes: dict, despues: dict) -> dict:
    def estado(f: dict) -> dict:
        return {'parq': f['parq'], 'lesiones': f['lesiones'], 'semaforo': f['semaforo'], 'bloqueado': bool(f.get('bloqueado'))}
    return {'antes': estado(antes), 'despues': estado(despues)}


def _resolver_alertas_rojas(repo, socio_id: str, actor: Actor) -> None:
    for a in repo.find('alertas', tipo='semaforo_rojo', socio_id=socio_id, resuelta=False):
        repo.update('alertas', a['id'], {'resuelta': True, 'atendida_por': actor.id, 'atendida_en': ahora()})


@router.post('/coach/fichas/{socio_id}/liberar')
def liberar_socio(request: Request, socio_id: str, datos: MotivoIn, actor: Actor = Depends(requiere('coach', 'admin'))):
    """Libera a un socio bloqueado por semáforo rojo. El coach ya lo evaluó en persona: el color se recalcula SOLO con
    PAR-Q y lesiones (sin la presión ni el pulso de la última lectura). La próxima medición vuelve a calcular normal."""
    repo = request.app.state.repo
    _socio_del_coach(repo, actor, socio_id)
    previas = repo.find('fichas_salud', socio_id=socio_id)
    if not previas or not previas[0].get('bloqueado'):
        raise HTTPException(409, 'El socio no está bloqueado')
    antes = previas[0]
    if any(antes['parq'][i - 1] for i in PARQ_CRITICAS):
        raise HTTPException(409, 'Primero corrige la ficha: tiene una respuesta crítica del PAR-Q')
    nueva = _aplicar_ficha(repo, socio_id, antes['parq'], antes['lesiones'], None, None, None, permite_desbloqueo=True)
    repo.insert('fichas_salud_historial', {'socio_id': socio_id, 'motivo': datos.motivo, 'hecho_por': actor.id, 'fecha': ahora(),
                                           'cambio': _cambio(antes, nueva)})
    _resolver_alertas_rojas(repo, socio_id, actor)
    return _vista_ficha(repo, repo.get('socios', socio_id))


# ------------------------------------------------------------------ rutinas por aprobar
@router.get('/coach/rutinas-pendientes')
def rutinas_pendientes(request: Request, coach_id: CoachVista = None, actor: Actor = Depends(requiere('coach', 'admin'))):
    repo = request.app.state.repo
    filas = repo.find('rutinas', estado='pendiente_aprobacion', **_filtro(actor, _vista(coach_id)))
    for r in filas:
        ficha = (repo.find('fichas_salud', socio_id=r['socio_id']) or [{}])[0]
        r['socioNombre'] = _nombre(repo, r['socio_id'])
        r['motivos'] = ficha.get('motivos', [])
        r['maquinasExcluidas'] = ficha.get('maquinas_excluidas', [])
    return sorted(filas, key=lambda r: r['creada'])


def _rutina_del_coach(repo, actor: Actor, rutina_id: str) -> dict:
    rutina = repo.get('rutinas', rutina_id)
    if rutina is None:
        raise HTTPException(404, 'Rutina no encontrada')
    if actor.rol == 'coach' and rutina.get('coach_id') != actor.id:
        raise HTTPException(403, 'Esta rutina no es de uno de tus socios')
    if rutina['estado'] != 'pendiente_aprobacion':
        raise HTTPException(409, f"La rutina está en estado '{rutina['estado']}'")
    return rutina


def _resolver_alertas(repo, rutina_id: str) -> None:
    for a in repo.find('alertas', rutina_id=rutina_id, resuelta=False):
        repo.update('alertas', a['id'], {'resuelta': True})


@router.post('/coach/rutinas/{rutina_id}/aprobar')
def aprobar(request: Request, rutina_id: str, actor: Actor = Depends(requiere('coach', 'admin'))):
    repo = request.app.state.repo
    _rutina_del_coach(repo, actor, rutina_id)
    nueva = repo.update('rutinas', rutina_id, {'estado': 'activa', 'aprobada_por': actor.id, 'aprobada_en': ahora()})
    _resolver_alertas(repo, rutina_id)
    return nueva


@router.post('/coach/rutinas/{rutina_id}/rechazar')
def rechazar(request: Request, rutina_id: str, datos: MotivoIn, actor: Actor = Depends(requiere('coach', 'admin'))):
    repo = request.app.state.repo
    _rutina_del_coach(repo, actor, rutina_id)
    nueva = repo.update('rutinas', rutina_id, {'estado': 'rechazada', 'motivo_rechazo': datos.motivo, 'aprobada_por': actor.id,
                                               'aprobada_en': ahora()})
    _resolver_alertas(repo, rutina_id)
    return nueva


# ------------------------------------------------------------------ riesgo de abandono (Random Forest)
def _factores(s: dict, ref: dict) -> list[dict]:
    """Los 3 datos más relevantes en palabras simples, comparados con la mediana de todos los socios."""
    def efecto(valor, mediana, peor_si_mayor):
        if mediana == 0 or abs(valor - mediana) / abs(mediana) < 0.15:
            return 'neutro'
        return 'sube' if (valor > mediana) == peor_si_mayor else 'baja'

    d, v, a = s['dias_ultima_visita'], s['visitas_semana'], s['antiguedad_meses']
    ed, ev, ea = efecto(d, ref['dias'], True), efecto(v, ref['visitas'], False), efecto(a, ref['antig'], False)
    return [
        {'dato': 'dias_ultima_visita', 'efecto': ed,
         'texto': f'{int(d)} días sin venir' + {'sube': ' (más que la mayoría)', 'baja': ' (viene seguido)', 'neutro': ''}[ed]},
        {'dato': 'visitas_semana', 'efecto': ev,
         'texto': f'{v:g} visitas por semana' + {'sube': ' (menos que la mayoría)', 'baja': ' (más que la mayoría)', 'neutro': ''}[ev]},
        {'dato': 'antiguedad_meses', 'efecto': ea,
         'texto': f'{a:g} meses como socio' + {'sube': ' (socio nuevo)', 'baja': ' (socio veterano)', 'neutro': ''}[ea]},
    ]


@router.get('/coach/socios')
def socios_riesgo(request: Request, limite: int = 200, coach_id: CoachVista = None,
                  actor: Actor = Depends(requiere('coach', 'admin'))):
    repo = request.app.state.repo
    todos = repo.find('socios')
    ref = {'dias': statistics.median(s['dias_ultima_visita'] for s in todos) if todos else 0,
           'visitas': statistics.median(s['visitas_semana'] for s in todos) if todos else 0,
           'antig': statistics.median(s['antiguedad_meses'] for s in todos) if todos else 0}
    f = _filtro(actor, _vista(coach_id))
    propios = [s for s in todos if all(s.get(k) == v for k, v in f.items())]
    abiertas = {a['socio_id']: a['id'] for a in repo.find('alertas', tipo='abandono', resuelta=False)}
    analizados = [s for s in propios if s.get('riesgo_abandono') is not None]
    analizados.sort(key=lambda s: s['riesgo_abandono'], reverse=True)
    filas = [{'id': s['id'], 'nombre': s['nombre'], 'probabilidad': s['riesgo_abandono'], 'nivel': s['nivel_riesgo'],
              'segmento': s.get('segmento'), 'factores': _factores(s, ref), 'alertaId': abiertas.get(s['id'])}
             for s in analizados[:max(1, min(limite, 500))]]
    return {'analizado': bool(analizados), 'totalSocios': len(propios), 'socios': filas}


# ------------------------------------------------------------------ perfiles (K-Means)
@router.get('/coach/perfiles')
def perfiles(request: Request, coach_id: CoachVista = None, actor: Actor = Depends(requiere('coach', 'admin'))):
    repo = request.app.state.repo
    grupos: dict[str, list[dict]] = defaultdict(list)
    for s in _socios_visibles(repo, actor, _vista(coach_id)):
        if s.get('segmento'):
            grupos[s['segmento']].append(s)
    out = []
    for seg, ss in grupos.items():
        riesgos = [s['riesgo_abandono'] for s in ss if s.get('riesgo_abandono') is not None]
        out.append({'segmento': seg, 'socios': len(ss),
                    'riesgoMedioPct': round(100 * statistics.mean(riesgos), 1) if riesgos else 0.0,
                    'riesgoAlto': sum(1 for s in ss if s.get('nivel_riesgo') == 'alto')})
    return {'analizado': bool(out), 'perfiles': sorted(out, key=lambda p: -p['socios'])}


# ------------------------------------------------------------------ estaciones y mantenimiento (Mean-Shift)
def falla_probable(m: dict) -> str:
    if abs(m.get('delta_peso_kg') or 0) >= 3:
        return 'báscula'
    if abs(m.get('delta_grasa_pct') or 0) >= 3:
        return 'electrodos'
    return 'duración'   # lector trabado: la medición duró demasiado o muy poco


@router.get('/coach/mantenimiento')
def mantenimiento(request: Request, coach_id: CoachVista = None, actor: Actor = Depends(requiere('coach', 'admin'))):
    repo = request.app.state.repo
    visibles = {s['id'] for s in _socios_visibles(repo, actor, _vista(coach_id))}
    por_estacion: dict[str, dict] = {}
    for m in repo.find('mediciones', atipica=True):
        if m['socio_id'] not in visibles:
            continue
        ses = repo.get('sesiones', m['sesion_id']) if m.get('sesion_id') else None
        est = repo.get('estaciones', ses['estacion_id']) if ses else None
        clave = est['id'] if est else 'desconocida'
        grupo = por_estacion.setdefault(clave, {'estacionId': clave, 'estacion': est['nombre'] if est else 'Estación desconocida',
                                                'lecturas': []})
        grupo['lecturas'].append({'fecha': m['fecha'], 'falla': falla_probable(m), 'deltaPesoKg': m.get('delta_peso_kg'),
                                  'deltaGrasaPct': m.get('delta_grasa_pct')})
    for g in por_estacion.values():
        g['lecturas'].sort(key=lambda x: x['fecha'], reverse=True)
    return sorted(por_estacion.values(), key=lambda g: -len(g['lecturas']))


# ------------------------------------------------------------------ modelo de IA
@router.get('/coach/modelo')
def modelo(request: Request, _: Actor = Depends(requiere('coach', 'admin'))):
    mo = request.app.state.modelos
    m = mo.meta
    return {'version': mo.version, 'fechaEntrenamiento': m['fecha_entrenamiento'], 'scikitLearn': m['scikit_learn'],
            'metricas': {'abandono': {'rocAuc': m['abandono']['metricas']['roc_auc'], 'f1': m['abandono']['metricas']['f1'],
                                      'precision': m['abandono']['metricas']['precision'], 'recall': m['abandono']['metricas']['recall']},
                         'afluencia': {'r2': m['afluencia']['metricas']['r2'], 'maeSocios': m['afluencia']['metricas']['mae_socios']},
                         'kmeans': {'silueta': m['kmeans']['metricas']['silueta']},
                         'meanshift': {'f1': m['meanshift']['metricas']['f1']}}}
