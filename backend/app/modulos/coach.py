"""Microservicio Coach: todo lo que ve el panel. Un coach solo ve a SUS socios; el admin ve todo."""
from __future__ import annotations

import statistics
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.repositorio import ahora
from app.core.seguridad import Actor, requiere

router = APIRouter(tags=['coach'])


class MotivoIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    motivo: str = Field(min_length=3, max_length=200)


def _filtro(actor: Actor) -> dict:
    return {} if actor.rol == 'admin' else {'coach_id': actor.id}


def _socios_visibles(repo, actor: Actor) -> list[dict]:
    return repo.find('socios', **_filtro(actor))


def _nombre(repo, socio_id: str | None) -> str:
    s = repo.get('socios', socio_id) if socio_id else None
    return s['nombre'] if s else '—'


# ------------------------------------------------------------------ alertas
@router.get('/coach/alertas')
def alertas(request: Request, actor: Actor = Depends(requiere('coach', 'admin'))):
    repo = request.app.state.repo
    filas = repo.find('alertas', resuelta=False, **_filtro(actor))
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


# ------------------------------------------------------------------ rutinas por aprobar
@router.get('/coach/rutinas-pendientes')
def rutinas_pendientes(request: Request, actor: Actor = Depends(requiere('coach', 'admin'))):
    repo = request.app.state.repo
    filas = repo.find('rutinas', estado='pendiente_aprobacion', **_filtro(actor))
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
def socios_riesgo(request: Request, limite: int = 200, actor: Actor = Depends(requiere('coach', 'admin'))):
    repo = request.app.state.repo
    todos = repo.find('socios')
    ref = {'dias': statistics.median(s['dias_ultima_visita'] for s in todos) if todos else 0,
           'visitas': statistics.median(s['visitas_semana'] for s in todos) if todos else 0,
           'antig': statistics.median(s['antiguedad_meses'] for s in todos) if todos else 0}
    propios = todos if actor.rol == 'admin' else [s for s in todos if s.get('coach_id') == actor.id]
    abiertas = {a['socio_id']: a['id'] for a in repo.find('alertas', tipo='abandono', resuelta=False)}
    analizados = [s for s in propios if s.get('riesgo_abandono') is not None]
    analizados.sort(key=lambda s: s['riesgo_abandono'], reverse=True)
    filas = [{'id': s['id'], 'nombre': s['nombre'], 'probabilidad': s['riesgo_abandono'], 'nivel': s['nivel_riesgo'],
              'segmento': s.get('segmento'), 'factores': _factores(s, ref), 'alertaId': abiertas.get(s['id'])}
             for s in analizados[:max(1, min(limite, 500))]]
    return {'analizado': bool(analizados), 'totalSocios': len(propios), 'socios': filas}


# ------------------------------------------------------------------ perfiles (K-Means)
@router.get('/coach/perfiles')
def perfiles(request: Request, actor: Actor = Depends(requiere('coach', 'admin'))):
    repo = request.app.state.repo
    grupos: dict[str, list[dict]] = defaultdict(list)
    for s in _socios_visibles(repo, actor):
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
def mantenimiento(request: Request, actor: Actor = Depends(requiere('coach', 'admin'))):
    repo = request.app.state.repo
    visibles = {s['id'] for s in _socios_visibles(repo, actor)}
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
