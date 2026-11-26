"""Microservicio Salud: mediciones (con detección de lecturas atípicas) y ficha de salud + semáforo.

El semáforo se calcula con REGLAS FIJAS (umbrales en app/core/umbrales.py). Sin IA.
La ficha (PAR-Q+, lesiones) es dato sensible: vive en su propia tabla y NUNCA se pasa a un modelo;
los modelos solo reciben el color.
"""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request

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
    # `fecha` tiene resolución de segundos: ante un empate gana la última insertada (reversed)
    return max(reversed(ms), key=lambda m: m['fecha']) if ms else None


def _aplicar_ficha(repo, socio_id: str, parq, lesiones, sis, dia, pulso) -> dict:
    color, motivos = calcular_semaforo(sistolica=sis, diastolica=dia, pulso=pulso, parq=parq, lesiones=lesiones)
    ficha = repo.upsert('fichas_salud', {
        'socio_id': socio_id, 'parq': parq, 'lesiones': lesiones, 'semaforo': color, 'motivos': motivos,
        'maquinas_excluidas': maquinas_excluidas(lesiones), 'requiere_apto_medico': color == 'rojo',
        'actualizada': ahora()}, 'socio_id')
    repo.update('socios', socio_id, {'semaforo': color})
    return ficha


def condiciones_quitadas(previa: dict, parq: list[bool], lesiones: list[str]) -> list[str]:
    """Condiciones que ya estaban en la ficha guardada y faltan en la nueva (PAR-Q+ en «sí» o lesiones)."""
    quitadas = [f'lesión: {x}' for x in previa.get('lesiones', []) if x not in lesiones]
    quitadas += [f'PAR-Q+ pregunta {i + 1}' for i, v in enumerate(previa.get('parq', [])) if v and not parq[i]]
    return quitadas


def recalcular_ficha(repo, socio_id: str, parq: list[bool], lesiones: list[str], sis=None, dia=None, pulso=None) -> dict:
    """Guarda la ficha y recalcula el semáforo; lo que no se manda sale de la última medición válida del socio."""
    ult = ultima_medicion_valida(repo, socio_id) or {}
    return _aplicar_ficha(repo, socio_id, parq, lesiones,
                          sis if sis is not None else ult.get('presion_sistolica'),
                          dia if dia is not None else ult.get('presion_diastolica'),
                          pulso if pulso is not None else ult.get('pulso_reposo'))


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
    imc = round(m.peso_kg / (m.talla_cm / 100) ** 2, 1) if m.talla_cm else None
    fila = repo.insert('mediciones', {
        'socio_id': socio_id, 'sesion_id': m.sesion_id, 'peso_kg': m.peso_kg, 'grasa_pct': m.grasa_pct,
        'presion_sistolica': m.presion_sistolica, 'presion_diastolica': m.presion_diastolica,
        'pulso_reposo': m.pulso_reposo, 'talla_cm': m.talla_cm, 'imc': imc,
        'delta_peso_kg': round(d_peso, 2), 'delta_grasa_pct': round(d_grasa, 2),
        'duracion_seg': m.duracion_seg, 'atipica': atipica, 'usada': not atipica, 'fecha': ahora()})
    if atipica:   # no se usa para nada y se avisa a mantenimiento
        _alerta(repo, socio, 'mantenimiento', 'media',
                f'Lectura atípica (Δpeso {d_peso:+.1f} kg, Δgrasa {d_grasa:+.1f} %): revisar sensores de la estación')
        return {'medicionId': fila['id'], 'atipica': True, 'usada': False,
                'mensaje': 'Lectura atípica: no se usará. Se avisó a mantenimiento. Repite la medición.'}
    ficha = repo.find('fichas_salud', socio_id=socio_id)
    if ficha:   # presión y pulso nuevos pueden cambiar el color
        f = ficha[0]
        _aplicar_ficha(repo, socio_id, f['parq'], f['lesiones'], m.presion_sistolica, m.presion_diastolica, m.pulso_reposo)
    return {'medicionId': fila['id'], 'atipica': False, 'usada': True, 'imc': imc}


@router.get('/socios/{socio_id}/ficha-salud')
def ver_ficha(request: Request, socio_id: str, actor: Actor = Depends(requiere('estacion', 'coach', 'admin'))):
    """Ficha guardada del socio (la estación la precarga al identificarse). `existe: false` si aún no tiene."""
    autorizar_socio(request, actor, socio_id)
    previas = request.app.state.repo.find('fichas_salud', socio_id=socio_id)
    if not previas:
        return {'existe': False}
    return {'existe': True, **ficha_publica(previas[0])}


def ficha_publica(f: dict) -> dict:
    return {'parq': f['parq'], 'lesiones': f['lesiones'], 'semaforo': f['semaforo'], 'motivos': f['motivos'],
            'requiereAptoMedico': f['requiere_apto_medico'], 'maquinasExcluidas': f['maquinas_excluidas'],
            'actualizada': f.get('actualizada')}


@router.put('/socios/{socio_id}/ficha-salud')
def guardar_ficha(request: Request, socio_id: str, f: FichaIn,
                  actor: Actor = Depends(requiere('estacion', 'coach', 'admin'))):
    socio = autorizar_socio(request, actor, socio_id)
    repo = request.app.state.repo
    previas = repo.find('fichas_salud', socio_id=socio_id)
    if previas:   # la ficha solo puede crecer aquí: quitar condiciones es cosa del coach (con motivo e historial)
        quitadas = condiciones_quitadas(previas[0], f.parq, f.lesiones)
        if quitadas:
            raise HTTPException(409, 'No se puede quitar una condición ya registrada. Habla con tu coach: ' + ', '.join(quitadas))
    ficha = recalcular_ficha(repo, socio_id, f.parq, f.lesiones, f.presion_sistolica, f.presion_diastolica, f.pulso_reposo)
    if ficha['semaforo'] == 'rojo':
        _alerta(repo, socio, 'semaforo_rojo', 'alta', 'Socio en rojo: requiere apto médico antes de entrenar')
    return {'semaforo': ficha['semaforo'], 'motivos': ficha['motivos'], 'requiereAptoMedico': ficha['requiere_apto_medico'],
            'maquinasExcluidas': ficha['maquinas_excluidas']}
