"""Bloqueo por semáforo rojo: solo un coach/admin lo libera; volver a medirse no saca del rojo."""
from app.core.semilla import COACHES

from tests.test_ficha_persistente import MED_OK, PARQ_NO, _con_ficha, _dni, _socio_de

ALTA = {**MED_OK, 'presion_sistolica': 165, 'presion_diastolica': 102}
CRITICA = [True] + [False] * 6
MOTIVO = {'motivo': 'Lo evalué en persona'}


def _ficha(client, est_headers, sid):
    return client.get(f'/v1/socios/{sid}/ficha-salud', headers=est_headers).json()


def _medir(client, est_headers, sid, med):
    r = client.post(f'/v1/socios/{sid}/mediciones', json=med, headers=est_headers)
    assert r.status_code == 201 and r.json()['usada'] is True, r.text


def _bloqueado_por_presion(client, est_headers, abrir_sesion, app, coach=0, desde=300):
    i = _socio_de(app, COACHES[coach], desde)
    sid = _con_ficha(client, est_headers, abrir_sesion, i)
    assert _ficha(client, est_headers, sid)['bloqueado'] is False
    _medir(client, est_headers, sid, ALTA)
    return sid


def test_presion_alta_bloquea_y_una_medicion_normal_no_lo_saca_del_rojo(client, est_headers, abrir_sesion, app):
    sid = _bloqueado_por_presion(client, est_headers, abrir_sesion, app)
    f = _ficha(client, est_headers, sid)
    assert f['semaforo'] == 'rojo' and f['bloqueado'] is True and f['bloqueadoDesde']
    _medir(client, est_headers, sid, MED_OK)   # intenta «repetir hasta que salga normal»
    f = _ficha(client, est_headers, sid)
    assert f['semaforo'] == 'rojo' and f['bloqueado'] is True
    assert 'Bloqueado: requiere liberación del coach' in f['motivos']
    assert app.state.repo.get('socios', sid)['semaforo'] == 'rojo'
    assert len([a for a in app.state.repo.find('alertas', socio_id=sid, tipo='semaforo_rojo')]) == 1   # una alerta por bloqueo
    r = client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': PARQ_NO}, headers=est_headers)   # «sigo igual» tampoco
    assert r.json()['semaforo'] == 'rojo' and r.json()['bloqueado'] is True
    g = client.post(f'/v1/socios/{sid}/rutinas/generar', json={'hora': 19, 'dia': 0}, headers=est_headers).json()
    assert g['estado'] == 'requiere_apto_medico' and g['dias'] == [] and g['rutinaId'] is None


def test_parq_critico_y_pulso_alto_tambien_bloquean(client, est_headers, abrir_sesion, app):
    sid = _con_ficha(client, est_headers, abrir_sesion, 310, parq=CRITICA)
    assert _ficha(client, est_headers, sid)['bloqueado'] is True
    sid2 = _con_ficha(client, est_headers, abrir_sesion, 311)
    _medir(client, est_headers, sid2, {**MED_OK, 'pulso_reposo': 120})
    assert _ficha(client, est_headers, sid2)['bloqueado'] is True


def test_coach_libera_y_la_rutina_funciona(client, est_headers, abrir_sesion, app, coach0):
    sid = _bloqueado_por_presion(client, est_headers, abrir_sesion, app, desde=320)
    r = client.post(f'/v1/coach/fichas/{sid}/liberar', json=MOTIVO, headers=coach0)
    assert r.status_code == 200, r.text
    v = r.json()
    assert v['ficha']['bloqueado'] is False and v['ficha']['bloqueadoDesde'] is None
    assert v['ficha']['semaforo'] == 'verde' and v['socio']['semaforo'] == 'verde'   # solo PAR-Q y lesiones, sin la presión
    h = v['historial'][0]
    assert h['motivo'] == 'Lo evalué en persona' and h['hecho_por'] == COACHES[0]
    assert h['cambio']['antes']['bloqueado'] is True and h['cambio']['despues']['bloqueado'] is False
    assert not app.state.repo.find('alertas', socio_id=sid, tipo='semaforo_rojo', resuelta=False)
    g = client.post(f'/v1/socios/{sid}/rutinas/generar', json={'hora': 19, 'dia': 0}, headers=est_headers)
    assert g.status_code == 201 and g.json()['estado'] == 'activa' and g.json()['dias'][0]['ejercicios']
    # la próxima medición vuelve a calcular normal: normal = sigue libre; presión alta = se bloquea otra vez
    _medir(client, est_headers, sid, MED_OK)
    assert _ficha(client, est_headers, sid)['bloqueado'] is False
    _medir(client, est_headers, sid, ALTA)
    assert _ficha(client, est_headers, sid)['bloqueado'] is True


def test_no_se_libera_con_un_parq_critico(client, est_headers, abrir_sesion, coach0, app):
    i = _socio_de(app, COACHES[0], 340)
    sid = _con_ficha(client, est_headers, abrir_sesion, i, parq=CRITICA)
    r = client.post(f'/v1/coach/fichas/{sid}/liberar', json=MOTIVO, headers=coach0)
    assert r.status_code == 409 and r.json()['detail'] == 'Primero corrige la ficha: tiene una respuesta crítica del PAR-Q'
    assert _ficha(client, est_headers, sid)['bloqueado'] is True


def test_corregir_el_parq_critico_desbloquea_y_resuelve_la_alerta(client, est_headers, abrir_sesion, coach0, app):
    i = _socio_de(app, COACHES[0], 350)
    sid = _con_ficha(client, est_headers, abrir_sesion, i, parq=CRITICA)
    r = client.put(f'/v1/coach/fichas/{sid}', json={'parq': PARQ_NO, 'lesiones': [], 'motivo': 'Error al registrar'}, headers=coach0)
    assert r.status_code == 200 and r.json()['ficha']['bloqueado'] is False and r.json()['ficha']['semaforo'] == 'verde'
    assert not app.state.repo.find('alertas', socio_id=sid, tipo='semaforo_rojo', resuelta=False)
    # si tras corregir sigue rojo (presión alta), sigue bloqueado
    sid2 = _bloqueado_por_presion(client, est_headers, abrir_sesion, app, desde=360)
    cuerpo = {'parq': PARQ_NO, 'lesiones': ['rodilla'], 'motivo': 'Error al registrar'}
    r = client.put(f'/v1/coach/fichas/{sid2}', json=cuerpo, headers=coach0)
    assert r.json()['ficha']['semaforo'] == 'rojo' and r.json()['ficha']['bloqueado'] is True


def test_un_coach_ajeno_no_puede_liberar(client, est_headers, abrir_sesion, app, coach0, admin):
    sid = _bloqueado_por_presion(client, est_headers, abrir_sesion, app, coach=1, desde=380)
    assert client.post(f'/v1/coach/fichas/{sid}/liberar', json=MOTIVO, headers=coach0).status_code == 403
    assert _ficha(client, est_headers, sid)['bloqueado'] is True
    assert client.post(f'/v1/coach/fichas/{sid}/liberar', json=MOTIVO, headers=est_headers).status_code == 403   # la estación tampoco
    assert client.post(f'/v1/coach/fichas/{sid}/liberar', json=MOTIVO, headers=admin).status_code == 200


def test_liberar_exige_motivo_y_un_socio_bloqueado(client, est_headers, abrir_sesion, app, coach0):
    i = _socio_de(app, COACHES[0], 400)
    sid = _con_ficha(client, est_headers, abrir_sesion, i)   # verde: no está bloqueado
    r = client.post(f'/v1/coach/fichas/{sid}/liberar', json=MOTIVO, headers=coach0)
    assert r.status_code == 409 and r.json()['detail'] == 'El socio no está bloqueado'
    assert client.post(f'/v1/coach/fichas/{sid}/liberar', json={'motivo': 'x'}, headers=coach0).status_code == 422
    assert client.post(f'/v1/coach/fichas/{sid}/liberar', json={}, headers=coach0).status_code == 422
    assert _dni(app, sid)
