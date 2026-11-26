"""Pruebas de la API (repositorio en memoria)."""
import time

import jwt
from app.core.config import get_settings

MED_OK = {'peso_kg': 70.0, 'grasa_pct': 22.0, 'presion_sistolica': 120, 'presion_diastolica': 78, 'pulso_reposo': 68}
PARQ_NO = [False] * 7


# ------------------------------------------------------------------ seguridad
def test_sin_station_key_da_401(client, estacion_id):
    r = client.post(f'/v1/estaciones/{estacion_id}/sesiones', json={'dni': '10000000'})
    assert r.status_code == 401


def test_station_key_invalida_da_401(client, estacion_id):
    r = client.post(f'/v1/estaciones/{estacion_id}/sesiones', json={'dni': '10000000'}, headers={'X-Station-Key': 'mala'})
    assert r.status_code == 401


def test_endpoints_protegidos_sin_credenciales(client):
    for metodo, url in [('get', '/v1/coach/alertas'), ('get', '/v1/prediccion/espera'),
                        ('post', '/v1/prediccion/abandono/lote'), ('get', '/v1/ejercicios/E-M-01/video')]:
        assert getattr(client, metodo)(url).status_code == 401


def test_jwt_expirado_o_firma_falsa_da_401(client):
    base = {'sub': 'x', 'aud': 'authenticated', 'app_metadata': {'role': 'admin'}}
    expirado = jwt.encode({**base, 'exp': int(time.time()) - 10}, get_settings().supabase_jwt_secret, algorithm='HS256')
    falso = jwt.encode({**base, 'exp': int(time.time()) + 600}, 'otra-clave-distinta-de-32-bytes-xxxxxx', algorithm='HS256')
    for t in (expirado, falso):
        assert client.get('/v1/coach/alertas', headers={'Authorization': f'Bearer {t}'}).status_code == 401


def test_estacion_no_puede_abrir_sesion_en_otra_estacion(client, est_headers):
    r = client.post('/v1/estaciones/otra-estacion/sesiones', json={'dni': '10000000'}, headers=est_headers)
    assert r.status_code == 403


def test_pydantic_valida_entradas(client, est_headers, estacion_id):
    url = f'/v1/estaciones/{estacion_id}/sesiones'
    assert client.post(url, json={'dni': "1' OR 1=1"}, headers=est_headers).status_code == 422
    assert client.post(url, json={'dni': '10000000', 'qr': 'TNT-00001'}, headers=est_headers).status_code == 422
    assert client.post(url, json={'dni': '10000000', 'extra': 1}, headers=est_headers).status_code == 422


def test_estacion_sin_sesion_no_accede_al_socio(client, est_headers, app):
    otro = app.state.repo.find('socios', dni='10000500')[0]['id']
    r = client.post(f'/v1/socios/{otro}/mediciones', json=MED_OK, headers=est_headers)
    assert r.status_code == 403


def test_coach_solo_ve_sus_socios(client, app, admin):
    from app.core.semilla import COACHES

    from tests.conftest import token
    ajeno = next(s for s in app.state.repo.find('socios') if s['coach_id'] != COACHES[0])
    r = client.put(f"/v1/socios/{ajeno['id']}/ficha-salud", json={'parq': PARQ_NO}, headers=token('coach', COACHES[0]))
    assert r.status_code == 403
    assert client.put(f"/v1/socios/{ajeno['id']}/ficha-salud", json={'parq': PARQ_NO}, headers=admin).status_code == 200


# ------------------------------------------------------------------ flujo completo
def test_flujo_completo_verde(client, est_headers, abrir_sesion):
    sid = abrir_sesion(1)
    assert client.post(f'/v1/socios/{sid}/mediciones', json=MED_OK, headers=est_headers).json()['usada'] is True
    f = client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': PARQ_NO}, headers=est_headers).json()
    assert f['semaforo'] == 'verde'
    r = client.post(f'/v1/socios/{sid}/rutinas/generar', json={'hora': 19, 'dia': 0}, headers=est_headers)
    assert r.status_code == 201
    j = r.json()
    assert j['estado'] == 'activa' and j['semaforo'] == 'verde'
    ej = j['dias'][0]['ejercicios']
    assert len(ej) == 6 and set(ej[0]) == {'id', 'nombre', 'maquina', 'series', 'repeticiones', 'descansoSeg'}


def test_socia_con_lesion_de_rodilla_no_recibe_m02_ni_m03(client, est_headers, abrir_sesion, coach0, app):
    sid = abrir_sesion(2)
    f = client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': PARQ_NO, 'lesiones': ['rodilla']}, headers=est_headers).json()
    assert f['semaforo'] == 'amarillo'
    for hora in (7, 19):
        j = client.post(f'/v1/socios/{sid}/rutinas/generar', json={'hora': hora, 'dia': 0}, headers=est_headers).json()
        maquinas = {e['maquina'] for e in j['dias'][0]['ejercicios']}
        assert not {'M-02', 'M-03'} & maquinas
        assert j['estado'] == 'pendiente_aprobacion'
    # el coach la ve pendiente y la aprueba
    socio = app.state.repo.get('socios', sid)
    from tests.conftest import token
    th = token('coach', socio['coach_id'])
    pend = client.get('/v1/coach/rutinas-pendientes', headers=th).json()
    assert any(p['id'] == j['rutinaId'] for p in pend)
    assert client.post(f"/v1/coach/rutinas/{j['rutinaId']}/aprobar", headers=th).json()['estado'] == 'activa'


def test_semaforo_rojo_no_genera_rutina(client, est_headers, abrir_sesion):
    sid = abrir_sesion(3)
    f = client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': PARQ_NO, 'presion_sistolica': 165,
                                                         'presion_diastolica': 95, 'pulso_reposo': 70}, headers=est_headers).json()
    assert f['semaforo'] == 'rojo' and f['requiereAptoMedico'] is True
    j = client.post(f'/v1/socios/{sid}/rutinas/generar', json={}, headers=est_headers).json()
    assert j['estado'] == 'requiere_apto_medico' and j['dias'] == []


def test_rutina_sin_ficha_da_409(client, est_headers, abrir_sesion):
    sid = abrir_sesion(4)
    assert client.post(f'/v1/socios/{sid}/rutinas/generar', json={}, headers=est_headers).status_code == 409


def test_medicion_atipica_no_se_usa_y_genera_alerta(client, est_headers, abrir_sesion, app):
    sid = abrir_sesion(5)
    assert client.post(f'/v1/socios/{sid}/mediciones', json=MED_OK, headers=est_headers).json()['usada'] is True
    salto = {**MED_OK, 'peso_kg': 76.5}   # +6.5 kg
    r = client.post(f'/v1/socios/{sid}/mediciones', json=salto, headers=est_headers).json()
    assert r['atipica'] is True and r['usada'] is False
    assert any(a['tipo'] == 'mantenimiento' and a['socio_id'] == sid for a in app.state.repo.find('alertas'))
    # la siguiente medición normal se compara contra la última VÁLIDA (70 kg), no contra la atípica
    r2 = client.post(f'/v1/socios/{sid}/mediciones', json={**MED_OK, 'peso_kg': 70.3}, headers=est_headers).json()
    assert r2['atipica'] is False


# ------------------------------------------------------------------ predicción, lote, video, salud
def test_prediccion_espera(client, est_headers):
    j = client.get('/v1/prediccion/espera?hora=19&dia=0', headers=est_headers).json()
    assert len(j['esperaMin']) == 18 and j['sociosEnSala'] > 30
    assert client.get('/v1/prediccion/espera?hora=99', headers=est_headers).status_code == 422


def test_lote_abandono_solo_admin_y_crea_alertas(client, est_headers, coach0, admin, app):
    assert client.post('/v1/prediccion/abandono/lote', headers=est_headers).status_code == 403
    assert client.post('/v1/prediccion/abandono/lote', headers=coach0).status_code == 403
    r = client.post('/v1/prediccion/abandono/lote', headers=admin).json()
    assert r['procesados'] == 3000 and r['alertasNuevas'] > 0
    assert client.post('/v1/prediccion/abandono/lote', headers=admin).json()['alertasNuevas'] == 0   # sin duplicados
    s = app.state.repo.find('socios')[0]
    assert s['segmento'] and s['nivel_riesgo'] in {'bajo', 'medio', 'alto'}
    assert client.get('/v1/coach/alertas', headers=coach0).status_code == 200


def test_video_url_firmada_15_min(client, est_headers):
    j = client.get('/v1/ejercicios/E-M-01/video', headers=est_headers).json()
    assert j['expiraEnSeg'] == 900 and 'X-Amz-Expires=900' in j['url'] and 'ejercicios/E-M-01.mp4' in j['url']
    assert client.get('/v1/ejercicios/E-M-99/video', headers=est_headers).status_code == 404
    assert client.get('/v1/ejercicios/../../secreto/video', headers=est_headers).status_code in (404, 422)


def test_health_con_version_de_modelos(client):
    j = client.get('/v1/salud').json()
    assert j['estado'] == 'ok' and j['modelos']['version'] and len(j['modelos']['cargados']) == 4


def test_cors_permite_la_estacion_en_desarrollo_y_bloquea_otros(client):
    pedido = {'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'x-station-key,content-type'}
    ok = client.options('/v1/salud', headers={'Origin': 'http://localhost:5173', **pedido})
    assert ok.headers.get('access-control-allow-origin') == 'http://localhost:5173'
    assert 'x-station-key' in ok.headers.get('access-control-allow-headers', '').lower()
    malo = client.options('/v1/salud', headers={'Origin': 'https://sitio-malo.example', **pedido})
    assert 'access-control-allow-origin' not in malo.headers
