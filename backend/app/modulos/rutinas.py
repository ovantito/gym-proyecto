"""Microservicio Rutinas: espera (Random Forest) + orden óptimo (A*) respetando el semáforo.
También entrega la URL firmada (15 min) del video de cada ejercicio en Cloudflare R2."""
from __future__ import annotations

import boto3
from botocore.config import Config
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi.responses import RedirectResponse

from app.core import umbrales as u
from app.core.config import get_settings
from app.core.limites import limiter
from app.core.repositorio import ahora
from app.core.seguridad import Actor, autorizar_socio, requiere
from app.modulos.prediccion import MES_REFERENCIA, hora_dia_actual
from app.schemas import RutinaIn
from ml.busqueda import ProblemaRecorrido, a_estrella, espera_por_maquina, hill_climbing
from ml.datos import MAQUINAS

router = APIRouter(tags=['rutinas'])


def ordenar_rutina(espera: dict[str, float], excluidas: list[str], offline: bool = False):
    """A* (o Hill Climbing en modo offline/respaldo). Devuelve (máquinas en orden, costo min, algoritmo)."""
    pb = ProblemaRecorrido(espera, excluidas)
    if offline:
        camino, costo, _ = hill_climbing(pb)
        return camino, costo, 'hill_climbing'
    try:
        camino, costo, _ = a_estrella(pb)
        return camino, costo, 'a_estrella'
    except Exception:   # respaldo: si A* falla, la estación sigue funcionando
        camino, costo, _ = hill_climbing(pb)
        return camino, costo, 'hill_climbing'


def armar_dias(camino: list[str], semaforo: str) -> list[dict]:
    pauta = u.RUTINA_POR_SEMAFORO[semaforo]
    ejercicios = [{'id': f'E-{m}', 'nombre': MAQUINAS.loc[m, 'nombre'], 'maquina': m, **pauta} for m in camino]
    return [{'ejercicios': ejercicios}]


@router.post('/socios/{socio_id}/rutinas/generar', status_code=201)
def generar_rutina(request: Request, socio_id: str, datos: RutinaIn | None = None,
                   actor: Actor = Depends(requiere('estacion', 'coach', 'admin'))):
    socio = autorizar_socio(request, actor, socio_id)
    repo, modelos, cfg = request.app.state.repo, request.app.state.modelos, request.app.state.settings
    fichas = repo.find('fichas_salud', socio_id=socio_id)
    if not fichas:
        raise HTTPException(409, 'Falta la ficha de salud (PAR-Q+) del socio')
    # De la ficha solo salen el color y la lista de máquinas prohibidas; el modelo nunca la ve.
    semaforo, excluidas = fichas[0]['semaforo'], fichas[0]['maquinas_excluidas']
    if semaforo == 'rojo':
        return {'rutinaId': None, 'semaforo': 'rojo', 'dias': [], 'estado': 'requiere_apto_medico',
                'alertas': ['Semáforo rojo: presentar apto médico antes de entrenar. Se avisó al coach.']}

    h0, d0 = hora_dia_actual(request)
    hora = (datos.hora if datos and datos.hora is not None else h0)
    dia = (datos.dia if datos and datos.dia is not None else d0)
    espera, ocup = espera_por_maquina(modelos.afluencia, hora, dia, mes=MES_REFERENCIA)
    camino, costo, algoritmo = ordenar_rutina(espera, excluidas, cfg.modo_offline)

    estado = 'pendiente_aprobacion' if semaforo == 'amarillo' else 'activa'
    dias = armar_dias(camino, semaforo)
    alertas = []
    if excluidas:
        alertas.append('Máquinas excluidas por lesión: ' + ', '.join(excluidas))
    if estado == 'pendiente_aprobacion':
        alertas.append('Rutina con restricciones: pendiente de aprobación del coach')
    rutina = repo.insert('rutinas', {
        'socio_id': socio_id, 'coach_id': socio.get('coach_id'), 'semaforo': semaforo, 'dias': dias, 'estado': estado,
        'algoritmo': algoritmo, 'costo_min': round(costo, 2), 'creada': ahora()})
    if estado == 'pendiente_aprobacion':
        repo.insert('alertas', {'tipo': 'rutina_pendiente', 'nivel': 'media', 'socio_id': socio_id,
                                'coach_id': socio.get('coach_id'), 'rutina_id': rutina['id'], 'resuelta': False,
                                'creada': ahora(), 'mensaje': 'Rutina amarilla pendiente de aprobación'})
    return {'rutinaId': rutina['id'], 'semaforo': semaforo, 'dias': dias, 'estado': estado, 'alertas': alertas,
            'detalle': {'algoritmo': algoritmo, 'tiempoPerdidoEstimadoMin': round(costo, 1), 'sociosEnSala': round(ocup)}}


def _url_firmada(c, ejercicio_id: str) -> str:
    """URL firmada nueva (15 min) del video en Cloudflare R2. 404 si no existe el ejercicio, 503 si R2 no está configurado."""
    if ejercicio_id[2:] not in MAQUINAS.index:
        raise HTTPException(404, 'Ejercicio no encontrado')
    if not all([c.r2_account_id, c.r2_access_key_id, c.r2_secret_access_key, c.r2_bucket]):
        raise HTTPException(503, 'Videos no configurados (faltan variables R2)')
    s3 = boto3.client('s3', endpoint_url=f'https://{c.r2_account_id}.r2.cloudflarestorage.com',
                      aws_access_key_id=c.r2_access_key_id, aws_secret_access_key=c.r2_secret_access_key,
                      region_name='auto', config=Config(signature_version='s3v4'))
    return s3.generate_presigned_url('get_object', ExpiresIn=u.VIDEO_URL_TTL_SEG,
                                     Params={'Bucket': c.r2_bucket, 'Key': f'{c.r2_prefijo}{ejercicio_id}.mp4'})


@router.get('/ejercicios/{ejercicio_id}/video')
def video_ejercicio(request: Request, ejercicio_id: str = Path(pattern=r'^E-M-\d{2}$'),
                    _: Actor = Depends(requiere('estacion', 'coach', 'admin', 'socio'))):
    return {'url': _url_firmada(request.app.state.settings, ejercicio_id), 'expiraEnSeg': u.VIDEO_URL_TTL_SEG}


@router.get('/ejercicios/{ejercicio_id}/ver')
@limiter.limit(lambda: get_settings().rate_limit_ver)
def ver_video(request: Request, ejercicio_id: str = Path(pattern=r'^E-M-\d{2}$')):
    """PÚBLICO y permanente: es el destino del QR del ticket. Genera una URL firmada nueva en cada visita y redirige (302).
    Solo sirve videos de ejercicios (nada personal); por eso no pide credenciales, pero tiene límite de peticiones."""
    return RedirectResponse(_url_firmada(request.app.state.settings, ejercicio_id), status_code=302)


@router.get('/rutinas/{rutina_id}')
def estado_rutina(request: Request, rutina_id: str, actor: Actor = Depends(requiere('estacion', 'coach', 'admin', 'socio'))):
    """Estado de una rutina (la estación lo consulta cada 5 s mientras espera la aprobación del coach)."""
    rutina = request.app.state.repo.get('rutinas', rutina_id)
    if rutina is None:
        raise HTTPException(404, 'Rutina no encontrada')
    autorizar_socio(request, actor, rutina['socio_id'])
    return {'rutinaId': rutina['id'], 'estado': rutina['estado'], 'motivoRechazo': rutina.get('motivo_rechazo')}
