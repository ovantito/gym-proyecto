"""Ficha de salud persistente: precarga, «solo crece» desde la estación y corrección del coach con historial."""
from app.core.semilla import COACHES

PARQ_NO = [False] * 7
MED_OK = {'peso_kg': 70.0, 'grasa_pct': 22.0, 'presion_sistolica': 120, 'presion_diastolica': 78, 'pulso_reposo': 68}


def _dni(app, socio_id: str) -> str:
    return app.state.repo.get('socios', socio_id)['dni']


def _socio_de(app, coach: str, desde: int = 60) -> int:
    """Índice i (DNI 10000000+i) de un socio de ese coach, a partir de `desde`."""
    for i in range(desde, desde + 50):
        s = app.state.repo.find('socios', dni=str(10000000 + i))
        if s and s[0]['coach_id'] == coach:
            return i
    raise AssertionError('sin socio')


def _con_ficha(client, est_headers, abrir_sesion, i, parq=None, lesiones=None) -> str:
    sid = abrir_sesion(i)
    assert client.post(f'/v1/socios/{sid}/mediciones', json=MED_OK, headers=est_headers).status_code == 201
    r = client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': parq or PARQ_NO, 'lesiones': lesiones or []}, headers=est_headers)
    assert r.status_code == 200, r.text
    return sid


# ------------------------------------------------------------------ estación: ficha precargada
def test_sin_ficha_la_estacion_recibe_existe_false(client, est_headers, abrir_sesion):
    sid = abrir_sesion(80)
    assert client.get(f'/v1/socios/{sid}/ficha-salud', headers=est_headers).json() == {'existe': False}


def test_ficha_precargada_al_volver(client, est_headers, abrir_sesion):
    sid = _con_ficha(client, est_headers, abrir_sesion, 81, parq=[False, False, False, True, False, False, False], lesiones=['rodilla'])
    abrir_sesion(81)   # el socio vuelve otro día
    f = client.get(f'/v1/socios/{sid}/ficha-salud', headers=est_headers).json()
    assert f['existe'] and f['lesiones'] == ['rodilla'] and f['parq'][3] is True and f['semaforo'] == 'amarillo'


def test_sigo_igual_reutiliza_la_ficha_y_recalcula_con_la_medicion_de_hoy(client, est_headers, abrir_sesion):
    sid = _con_ficha(client, est_headers, abrir_sesion, 82, lesiones=['hombro'])
    previa = client.get(f'/v1/socios/{sid}/ficha-salud', headers=est_headers).json()
    hoy = {**MED_OK, 'presion_sistolica': 165, 'presion_diastolica': 102}   # hoy llega con la presión alta
    assert client.post(f'/v1/socios/{sid}/mediciones', json=hoy, headers=est_headers).json()['usada'] is True
    r = client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': previa['parq'], 'lesiones': previa['lesiones']}, headers=est_headers)
    assert r.status_code == 200 and r.json()['semaforo'] == 'rojo'


# ------------------------------------------------------------------ estación y backend: no se puede quitar
def test_estacion_no_puede_quitar_una_lesion_409(client, est_headers, abrir_sesion):
    sid = _con_ficha(client, est_headers, abrir_sesion, 83, lesiones=['rodilla'])
    r = client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': PARQ_NO, 'lesiones': []}, headers=est_headers)
    assert r.status_code == 409 and 'rodilla' in r.json()['detail']
    assert client.get(f'/v1/socios/{sid}/ficha-salud', headers=est_headers).json()['lesiones'] == ['rodilla']   # no cambió nada


def test_estacion_no_puede_quitar_un_si_del_parq_409(client, est_headers, abrir_sesion):
    sid = _con_ficha(client, est_headers, abrir_sesion, 84, parq=[False, False, False, False, True, False, False])
    r = client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': PARQ_NO}, headers=est_headers)
    assert r.status_code == 409


def test_estacion_si_puede_agregar_condiciones(client, est_headers, abrir_sesion):
    sid = _con_ficha(client, est_headers, abrir_sesion, 85, lesiones=['rodilla'])
    r = client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': PARQ_NO, 'lesiones': ['rodilla', 'hombro']}, headers=est_headers)
    assert r.status_code == 200
    assert set(client.get(f'/v1/socios/{sid}/ficha-salud', headers=est_headers).json()['lesiones']) == {'rodilla', 'hombro'}


def test_el_409_aplica_tambien_al_coach_por_el_endpoint_normal(client, est_headers, abrir_sesion, app, coach0):
    i = _socio_de(app, COACHES[0], 100)
    sid = _con_ficha(client, est_headers, abrir_sesion, i, lesiones=['cadera'])
    assert client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': PARQ_NO}, headers=coach0).status_code == 409


# ------------------------------------------------------------------ panel del coach
def test_coach_quita_condicion_con_motivo_y_queda_en_el_historial(client, est_headers, abrir_sesion, app, coach0):
    i = _socio_de(app, COACHES[0], 120)
    sid = _con_ficha(client, est_headers, abrir_sesion, i, lesiones=['rodilla'])
    dni = _dni(app, sid)
    v = client.get(f'/v1/coach/fichas?dni={dni}', headers=coach0).json()
    assert v['socio']['id'] == sid and v['ficha']['semaforo'] == 'amarillo' and v['historial'] == []

    cuerpo = {'parq': PARQ_NO, 'lesiones': [], 'motivo': 'Presentó apto médico'}
    r = client.put(f'/v1/coach/fichas/{sid}', json=cuerpo, headers=coach0)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out['ficha']['lesiones'] == [] and out['ficha']['semaforo'] == 'verde'      # semáforo recalculado
    assert out['socio']['semaforo'] == 'verde'
    h = out['historial'][0]
    assert h['motivo'] == 'Presentó apto médico' and h['hecho_por'] == COACHES[0]
    assert h['cambio']['antes']['lesiones'] == ['rodilla'] and h['cambio']['despues']['lesiones'] == []
    assert h['cambio']['antes']['semaforo'] == 'amarillo' and h['cambio']['despues']['semaforo'] == 'verde'
    # la estación ya ve la ficha corregida y puede seguir con ella
    assert client.get(f'/v1/socios/{sid}/ficha-salud', headers=est_headers).json()['lesiones'] == []


def test_coach_no_guarda_sin_motivo_ni_sin_cambios(client, est_headers, abrir_sesion, app, coach0):
    i = _socio_de(app, COACHES[0], 140)
    sid = _con_ficha(client, est_headers, abrir_sesion, i, lesiones=['rodilla'])
    for cuerpo in ({'parq': PARQ_NO, 'lesiones': []}, {'parq': PARQ_NO, 'lesiones': [], 'motivo': ''},
                   {'parq': PARQ_NO, 'lesiones': [], 'motivo': '  '}):
        assert client.put(f'/v1/coach/fichas/{sid}', json=cuerpo, headers=coach0).status_code == 422
    sin_cambio = {'parq': PARQ_NO, 'lesiones': ['rodilla'], 'motivo': 'Error al registrar'}
    assert client.put(f'/v1/coach/fichas/{sid}', json=sin_cambio, headers=coach0).status_code == 409
    assert client.get(f'/v1/coach/fichas?dni={_dni(app, sid)}', headers=coach0).json()['historial'] == []


def test_coach_puede_corregir_agregando_y_recalcula_a_rojo(client, est_headers, abrir_sesion, app, coach0):
    i = _socio_de(app, COACHES[0], 160)
    sid = _con_ficha(client, est_headers, abrir_sesion, i)
    cuerpo = {'parq': [True] + [False] * 6, 'lesiones': [], 'motivo': 'Error al registrar'}
    r = client.put(f'/v1/coach/fichas/{sid}', json=cuerpo, headers=coach0)
    assert r.status_code == 200 and r.json()['ficha']['semaforo'] == 'rojo'


def test_coach_no_toca_fichas_de_socios_de_otro_coach(client, est_headers, abrir_sesion, app, coach0, admin):
    i = _socio_de(app, COACHES[1], 180)
    sid = _con_ficha(client, est_headers, abrir_sesion, i, lesiones=['rodilla'])
    dni = _dni(app, sid)
    assert client.get(f'/v1/coach/fichas?dni={dni}', headers=coach0).status_code == 404   # ni siquiera revela que existe
    cuerpo = {'parq': PARQ_NO, 'lesiones': [], 'motivo': 'Presentó apto médico'}
    assert client.put(f'/v1/coach/fichas/{sid}', json=cuerpo, headers=coach0).status_code == 403
    assert client.get(f'/v1/socios/{sid}/ficha-salud', headers=coach0).status_code == 403
    assert client.get(f'/v1/socios/{sid}/ficha-salud', headers=admin).json()['lesiones'] == ['rodilla']   # no se tocó
    assert app.state.repo.find('fichas_salud_historial', socio_id=sid) == []
    # el admin sí ve todos
    assert client.get(f'/v1/coach/fichas?dni={dni}', headers=admin).status_code == 200
    assert client.put(f'/v1/coach/fichas/{sid}', json=cuerpo, headers=admin).status_code == 200


def test_busqueda_por_dni_valida_el_formato_y_exige_rol(client, est_headers, coach0):
    assert client.get('/v1/coach/fichas?dni=abc', headers=coach0).status_code == 422
    assert client.get('/v1/coach/fichas?dni=99999999', headers=coach0).status_code == 404
    assert client.get('/v1/coach/fichas?dni=10000000', headers=est_headers).status_code == 403   # la estación no entra al panel
    assert client.get('/v1/coach/fichas?dni=10000000').status_code == 401


def test_panel_muestra_la_ultima_medicion_con_talla_e_imc(client, est_headers, abrir_sesion, app, coach0):
    i = _socio_de(app, COACHES[0], 270)
    sid = abrir_sesion(i)
    dni = _dni(app, sid)
    assert client.get(f'/v1/coach/fichas?dni={dni}', headers=coach0).json()['medicion'] is None   # aún sin mediciones
    med = {**MED_OK, 'peso_kg': 72.3, 'talla_cm': 170}
    assert client.post(f'/v1/socios/{sid}/mediciones', json=med, headers=est_headers).status_code == 201
    m = client.get(f'/v1/coach/fichas?dni={dni}', headers=coach0).json()['medicion']
    assert m['imc'] == 25.0 and m['tallaCm'] == 170 and m['pesoKg'] == 72.3
    assert (m['sistolica'], m['diastolica'], m['pulso']) == (120, 78, 68) and m['fecha']
