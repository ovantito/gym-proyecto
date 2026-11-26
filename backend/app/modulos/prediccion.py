"""Microservicio Predicción: espera por máquina (Random Forest de afluencia),
y riesgo de abandono + segmento (Random Forest + K-Means) para todos los socios (cron nocturno)."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, Depends, Query, Request

from app.core import umbrales as u
from app.core.repositorio import ahora
from app.core.seguridad import Actor, requiere
from ml.busqueda import espera_por_maquina

router = APIRouter(tags=['prediccion'])
MES_REFERENCIA = 4   # igual que el Colab: el modelo se entrenó con ene-may de un año simulado


def hora_dia_actual(request: Request) -> tuple[int, int]:
    n = datetime.now(ZoneInfo(request.app.state.settings.zona_horaria))
    return min(21, max(6, n.hour)), n.weekday()


def nivel_riesgo(p: float) -> str:
    return 'alto' if p >= u.RIESGO_ALTO else ('medio' if p >= u.RIESGO_MEDIO else 'bajo')


@router.get('/prediccion/espera')
def prediccion_espera(request: Request, hora: int | None = Query(default=None, ge=0, le=23),
                      dia: int | None = Query(default=None, ge=0, le=6, description='lunes=0 ... domingo=6'),
                      _: Actor = Depends(requiere('estacion', 'coach', 'admin'))):
    h0, d0 = hora_dia_actual(request)
    hora, dia = (h0 if hora is None else hora), (d0 if dia is None else dia)
    espera, ocup = espera_por_maquina(request.app.state.modelos.afluencia, hora, dia, mes=MES_REFERENCIA)
    return {'hora': hora, 'dia': dia, 'sociosEnSala': round(ocup), 'esperaMin': espera}


@router.post('/prediccion/abandono/lote')
def abandono_lote(request: Request, _: Actor = Depends(requiere('admin'))):
    """Lo llama el cron nocturno (con un JWT de admin). Guarda riesgo y segmento y crea alertas."""
    repo, modelos = request.app.state.repo, request.app.state.modelos
    socios = repo.find('socios')
    if not socios:
        return {'procesados': 0, 'alertasNuevas': 0, 'modelo': modelos.version}
    df = pd.DataFrame(socios)
    # El modelo recibe SOLO sus variables (nunca la ficha de salud; del semáforo solo el color).
    probs = modelos.abandono.predict_proba(df[modelos.vars_abandono])[:, 1]
    seg_vars = modelos.meta['kmeans']['variables']
    segs = modelos.kmeans.predict(modelos.kmeans_scaler.transform(df[seg_vars]))
    nombres = modelos.meta['kmeans']['metricas']['nombres_segmentos']
    abiertas = {a['socio_id'] for a in repo.find('alertas', tipo='abandono', resuelta=False)}
    nuevas = 0
    for socio, p, seg in zip(socios, probs, segs, strict=True):
        nivel = nivel_riesgo(float(p))
        repo.update('socios', socio['id'], {'riesgo_abandono': round(float(p), 3), 'nivel_riesgo': nivel,
                                            'segmento': nombres.get(str(int(seg)), f'segmento_{int(seg)}')})
        if nivel == 'alto' and socio['id'] not in abiertas:
            repo.insert('alertas', {'tipo': 'abandono', 'nivel': 'alta', 'socio_id': socio['id'],
                                    'coach_id': socio.get('coach_id'), 'resuelta': False, 'creada': ahora(),
                                    'mensaje': f'Riesgo alto de abandono ({p:.0%}). Contactar esta semana.'})
            nuevas += 1
    return {'procesados': len(socios), 'alertasNuevas': nuevas, 'modelo': modelos.version}
