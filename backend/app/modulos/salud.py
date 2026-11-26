"""Microservicio Salud: mediciones (con detección de lecturas atípicas) y ficha de salud + semáforo.

El semáforo se calcula con REGLAS FIJAS (umbrales en app/core/umbrales.py). Sin IA.
La ficha (PAR-Q+, lesiones) es dato sensible: vive en su propia tabla y NUNCA se pasa a un modelo;
los modelos solo reciben el color.
"""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Request

from app.core import umbrales as u
from app.core.repositorio import ahora
from app.core.seguridad import Actor, autorizar_socio, requiere
from app.schemas import FichaIn, MedicionIn

router = APIRouter(tags=['salud'])


# ----------------------------------------------------------------- semáforo (reglas fijas)
def calcular_semaforo(*, sistolica: int | None, diastolica: int | None, pulso: int | None,
                      parq: list[bool], lesiones: list[str]) -> tuple[str, list[str]]:
    """Devuelve (color, motivos). Los datos ausentes (None) no disparan ninguna regla."""
    rojos, amarillos = [], []
    if sistolica is not None and sistolica >= u.ROJO_PRESION_SISTOLICA:
        rojos.append(f'Presión sistólica {sistolica} ≥ {u.ROJO_PRESION_SISTOLICA}')
    if diastolica is not None and diastolica >= u.ROJO_PRESION_DIASTOLICA:
        rojos.append(f'Presión diastólica {diastolica} ≥ {u.ROJO_PRESION_DIASTOLICA}')
    if pulso is not None and pulso > u.ROJO_PULSO_REPOSO:
        rojos.append(f'Pulso en reposo {pulso} > {u.ROJO_PULSO_REPOSO}')
    if any(parq[i - 1] for i in u.PARQ_CRITICAS):
        rojos.append('PAR-Q+ con respuesta crítica')
    if rojos:
        return 'rojo', rojos
    if sistolica is not None and sistolica >= u.AMARILLO_PRESION_SISTOLICA:
        amarillos.append(f'Presión sistólica {sistolica} ≥ {u.AMARILLO_PRESION_SISTOLICA}')
    if diastolica is not None and diastolica >= u.AMARILLO_PRESION_DIASTOLICA:
        amarillos.append(f'Presión diastólica {diastolica} ≥ {u.AMARILLO_PRESION_DIASTOLICA}')
    if any(parq):
        amarillos.append('PAR-Q+ con alguna respuesta afirmativa')
    if lesiones:
        amarillos.append('Lesión declarada: ' + ', '.join(lesiones))
    return ('amarillo', amarillos) if amarillos else ('verde', [])


def maquinas_excluidas(lesiones: list[str]) -> list[str]:
    return sorted({m for les in lesiones for m in u.LESION_MAQUINAS_EXCLUIDAS.get(les, ())})


def ultima_medicion_valida(repo, socio_id: str) -> dict | None:
    ms = [m for m in repo.find('mediciones', socio_id=socio_id) if m.get('usada')]
    return max(ms, key=lambda m: m['fecha']) if ms else None


def _aplicar_ficha(repo, socio_id: str, parq, lesiones, sis, dia, pulso) -> dict:
    color, motivos = calcular_semaforo(sistolica=sis, diastolica=dia, pulso=pulso, parq=parq, lesiones=lesiones)
    ficha = repo.upsert('fichas_salud', {
        'socio_id': socio_id, 'parq': parq, 'lesiones': lesiones, 'semaforo': color, 'motivos': motivos,
        'maquinas_excluidas': maquinas_excluidas(lesiones), 'requiere_apto_medico': color == 'rojo',
        'actualizada': ahora()}, 'socio_id')
    repo.update('socios', socio_id, {'semaforo': color})
    return ficha


def _alerta(repo, socio: dict, tipo: str, nivel: str, mensaje: str) -> None:
    repo.insert('alertas', {'tipo': tipo, 'nivel': nivel, 'socio_id': socio['id'], 'coach_id': socio.get('coach_id'),
                            'mensaje': mensaje, 'resuelta': False, 'creada': ahora()})


# ----------------------------------------------------------------- Mean-Shift: lectura atípica
def es_atipica(modelos, delta_peso: float, delta_grasa: float, sistolica: float, duracion: float) -> bool:
    cols = modelos.meta['meanshift']['variables']
    fila = pd.DataFrame([[delta_peso, delta_grasa, sistolica, duracion]], columns=cols)
    cluster = int(modelos.meanshift.predict(modelos.meanshift_scaler.transform(fila))[0])
    return cluster not in modelos.meta['meanshift']['clusters_normales']


# ----------------------------------------------------------------- endpoints
@router.post('/socios/{socio_id}/mediciones', status_code=201)
def registrar_medicion(request: Request, socio_id: str, m: MedicionIn,
                       actor: Actor = Depends(requiere('estacion', 'coach', 'admin'))):
    socio = autorizar_socio(request, actor, socio_id)
    repo, modelos = request.app.state.repo, request.app.state.modelos
    previa = ultima_medicion_valida(repo, socio_id)
    d_peso = m.peso_kg - previa['peso_kg'] if previa else 0.0
    d_grasa = m.grasa_pct - previa['grasa_pct'] if previa else 0.0
    atipica = es_atipica(modelos, d_peso, d_grasa, m.presion_sistolica, m.duracion_seg)
    fila = repo.insert('mediciones', {
        'socio_id': socio_id, 'sesion_id': m.sesion_id, 'peso_kg': m.peso_kg, 'grasa_pct': m.grasa_pct,
        'presion_sistolica': m.presion_sistolica, 'presion_diastolica': m.presion_diastolica,
        'pulso_reposo': m.pulso_reposo, 'delta_peso_kg': round(d_peso, 2), 'delta_grasa_pct': round(d_grasa, 2),
        'atipica': atipica, 'usada': not atipica, 'fecha': ahora()})
    if atipica:   # no se usa para nada y se avisa a mantenimiento
        _alerta(repo, socio, 'mantenimiento', 'media',
                f'Lectura atípica (Δpeso {d_peso:+.1f} kg, Δgrasa {d_grasa:+.1f} %): revisar sensores de la estación')
        return {'medicionId': fila['id'], 'atipica': True, 'usada': False,
                'mensaje': 'Lectura atípica: no se usará. Se avisó a mantenimiento. Repite la medición.'}
    ficha = repo.find('fichas_salud', socio_id=socio_id)
    if ficha:   # presión y pulso nuevos pueden cambiar el color
        f = ficha[0]
        _aplicar_ficha(repo, socio_id, f['parq'], f['lesiones'], m.presion_sistolica, m.presion_diastolica, m.pulso_reposo)
    return {'medicionId': fila['id'], 'atipica': False, 'usada': True}


@router.put('/socios/{socio_id}/ficha-salud')
def guardar_ficha(request: Request, socio_id: str, f: FichaIn,
                  actor: Actor = Depends(requiere('estacion', 'coach', 'admin'))):
    socio = autorizar_socio(request, actor, socio_id)
    repo = request.app.state.repo
    ult = ultima_medicion_valida(repo, socio_id) or {}
    sis = f.presion_sistolica if f.presion_sistolica is not None else ult.get('presion_sistolica')
    dia = f.presion_diastolica if f.presion_diastolica is not None else ult.get('presion_diastolica')
    pulso = f.pulso_reposo if f.pulso_reposo is not None else ult.get('pulso_reposo')
    ficha = _aplicar_ficha(repo, socio_id, f.parq, f.lesiones, sis, dia, pulso)
    if ficha['semaforo'] == 'rojo':
        _alerta(repo, socio, 'semaforo_rojo', 'alta', 'Socio en rojo: requiere apto médico antes de entrenar')
    return {'semaforo': ficha['semaforo'], 'motivos': ficha['motivos'], 'requiereAptoMedico': ficha['requiere_apto_medico'],
            'maquinasExcluidas': ficha['maquinas_excluidas']}
