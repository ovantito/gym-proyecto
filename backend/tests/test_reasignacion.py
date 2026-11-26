"""Reasignación de socios entre coaches (solo admin) y «ver panel como coach».

Usa su PROPIA app en memoria: el traspaso masivo cambia a quién pertenecen cientos de socios y no debe afectar a las
demás pruebas, que suponen el reparto original de la semilla.
"""
import httpx
import pytest
from app.core.repositorio import RepoMemoria, RepoSupabase, ahora
from app.core.semilla import COACHES
from app.main import create_app
from fastapi.testclient import TestClient

from tests.conftest import token

UUID_MALO = 'no-es-un-uuid'
MOTIVO = {'motivo': 'Cambio de turno'}


@pytest.fixture(scope='module')
def app2():
    return create_app()


@pytest.fixture(scope='module')
def c2(app2):
    return TestClient(app2)


@pytest.fixture(scope='module')
def adm():
    return token('admin', 'admin-1')


def _coach(i):
    return token('coach', COACHES[i])


def _socio_de(app, coach, n=0):
    return app.state.repo.find('socios', coach_id=coach)[n]


def _trabajo(repo, socio_id, coach):
    """Una alerta abierta, una resuelta, una rutina por aprobar y una activa de ese socio."""
    f = {'tipo': 'abandono', 'nivel': 'alta', 'mensaje': 'x', 'socio_id': socio_id, 'coach_id': coach, 'creada': ahora()}
    abierta = repo.insert('alertas', {**f, 'resuelta': False})
    resuelta = repo.insert('alertas', {**f, 'resuelta': True})
    r = {'socio_id': socio_id, 'coach_id': coach, 'semaforo': 'amarillo', 'dias': [], 'creada': ahora()}
    pendiente = repo.insert('rutinas', {**r, 'estado': 'pendiente_aprobacion'})
    activa = repo.insert('rutinas', {**r, 'estado': 'activa'})
    return abierta, resuelta, pendiente, activa


# ------------------------------------------------------------------ permisos
def test_un_coach_recibe_403_en_todo_lo_de_admin(c2, app2):
    h, sid = _coach(0), _socio_de(app2, COACHES[1])['id']
    assert c2.get('/v1/admin/coaches', headers=h).status_code == 403
    assert c2.get('/v1/admin/socios?dni=10000001', headers=h).status_code == 403
    assert c2.post(f'/v1/admin/socios/{sid}/reasignar', json={'coach_id': COACHES[0], **MOTIVO}, headers=h).status_code == 403
    traspaso = {'coach_destino_id': COACHES[0], **MOTIVO}
    assert c2.post(f'/v1/admin/coaches/{COACHES[1]}/traspasar', json=traspaso, headers=h).status_code == 403
    assert c2.patch(f'/v1/admin/coaches/{COACHES[1]}', json={'activo': False}, headers=h).status_code == 403
    assert c2.get('/v1/admin/coaches').status_code == 401
    assert _socio_de(app2, COACHES[0])['coach_id'] == COACHES[0] and app2.state.repo.find('reasignaciones') == []


def test_listado_de_coaches_con_conteos(c2, app2, adm):
    repo = app2.state.repo
    socio = _socio_de(app2, COACHES[2])
    _trabajo(repo, socio['id'], COACHES[2])
    filas = c2.get('/v1/admin/coaches', headers=adm).json()
    assert [f['nombre'] for f in filas] == sorted(f['nombre'] for f in filas) and len(filas) == 5
    c = next(f for f in filas if f['id'] == COACHES[2])
    assert c['socios'] == len(repo.find('socios', coach_id=COACHES[2])) == 600
    assert c['alertasAbiertas'] == 1 and c['rutinasPendientes'] == 1 and c['activo'] is True and c['email']


# ------------------------------------------------------------------ reasignar un socio
def test_reasignar_mueve_socio_trabajo_pendiente_e_historial(c2, app2, adm):
    repo = app2.state.repo
    socio = _socio_de(app2, COACHES[0], 5)
    assert c2.put(f"/v1/socios/{socio['id']}/ficha-salud", json={'parq': [False] * 7}, headers=adm).status_code == 200
    abierta, resuelta, pendiente, activa = _trabajo(repo, socio['id'], COACHES[0])
    dni = socio['dni']
    assert c2.get(f'/v1/coach/fichas?dni={dni}', headers=_coach(0)).status_code == 200

    r = c2.post(f"/v1/admin/socios/{socio['id']}/reasignar", json={'coach_id': COACHES[1], 'motivo': 'Pedido del socio'}, headers=adm)
    assert r.status_code == 200, r.text
    v = r.json()
    assert v['coach']['id'] == COACHES[1] and v['dni'] == dni
    assert v['historial'][0]['motivo'] == 'Pedido del socio' and v['historial'][0]['coachAntes']['id'] == COACHES[0]
    assert repo.get('socios', socio['id'])['coach_id'] == COACHES[1]
    assert repo.get('alertas', abierta['id'])['coach_id'] == COACHES[1]            # trabajo pendiente: viaja con el socio
    assert repo.get('rutinas', pendiente['id'])['coach_id'] == COACHES[1]
    assert repo.get('alertas', resuelta['id'])['coach_id'] == COACHES[0]           # lo ya cerrado se queda como estaba
    assert repo.get('rutinas', activa['id'])['coach_id'] == COACHES[0]
    fila = repo.find('reasignaciones', socio_id=socio['id'])[0]
    assert fila['coach_antes'] == COACHES[0] and fila['coach_despues'] == COACHES[1] and fila['hecho_por'] == 'admin-1'
    assert fila['lote_id'] is None
    assert c2.get(f'/v1/coach/fichas?dni={dni}', headers=_coach(0)).status_code == 404   # el coach viejo ya no lo ve
    assert c2.get(f'/v1/coach/fichas?dni={dni}', headers=_coach(1)).status_code == 200   # el nuevo sí
    assert c2.get(f"/v1/admin/socios?dni={dni}", headers=adm).json()['coach']['id'] == COACHES[1]


def test_reasignar_validaciones(c2, app2, adm):
    socio = _socio_de(app2, COACHES[3])
    url = f"/v1/admin/socios/{socio['id']}/reasignar"
    assert c2.post(url, json={'coach_id': COACHES[3], **MOTIVO}, headers=adm).json()['detail'] == 'Ya es su coach'
    assert c2.post(url, json={'coach_id': COACHES[3], **MOTIVO}, headers=adm).status_code == 409
    app2.state.repo.update('coaches', COACHES[4], {'activo': False})
    assert c2.post(url, json={'coach_id': COACHES[4], **MOTIVO}, headers=adm).status_code == 422   # inactivo
    app2.state.repo.update('coaches', COACHES[4], {'activo': True})
    assert c2.post(url, json={'coach_id': '6f1c1b2e-0000-4000-8000-0000000000ff', **MOTIVO}, headers=adm).status_code == 422   # no existe
    assert c2.post(url, json={'coach_id': UUID_MALO, **MOTIVO}, headers=adm).status_code == 422
    assert c2.post(url, json={'coach_id': COACHES[4], 'motivo': 'x'}, headers=adm).status_code == 422
    assert c2.post('/v1/admin/socios/no-existe/reasignar', json={'coach_id': COACHES[4], **MOTIVO}, headers=adm).status_code == 404
    assert c2.get('/v1/admin/socios?dni=99999999', headers=adm).status_code == 404
    assert app2.state.repo.get('socios', socio['id'])['coach_id'] == COACHES[3]


# ------------------------------------------------------------------ traspaso masivo
def test_traspaso_masivo_con_lote_y_desactivar_origen(c2, app2, adm):
    repo = app2.state.repo
    origen, destino = COACHES[3], COACHES[2]
    socios = repo.find('socios', coach_id=origen)
    antes_destino = len(repo.find('socios', coach_id=destino))
    _trabajo(repo, socios[0]['id'], origen)
    _trabajo(repo, socios[1]['id'], origen)
    n_alertas = len(repo.find('alertas', coach_id=origen, resuelta=False))
    n_rutinas = len(repo.find('rutinas', coach_id=origen, estado='pendiente_aprobacion'))
    assert n_alertas >= 2 and n_rutinas >= 2

    cuerpo = {'coach_destino_id': destino, 'motivo': 'Renuncia', 'desactivar_origen': True}
    r = c2.post(f'/v1/admin/coaches/{origen}/traspasar', json=cuerpo, headers=adm)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out['sociosMovidos'] == len(socios) == 600 and out['alertasMovidas'] == n_alertas and out['rutinasMovidas'] == n_rutinas
    assert repo.find('socios', coach_id=origen) == [] and len(repo.find('socios', coach_id=destino)) == antes_destino + 600
    assert repo.find('alertas', coach_id=origen, resuelta=False) == []
    filas = repo.find('reasignaciones', lote_id=out['loteId'])
    assert len(filas) == 600 and {f['motivo'] for f in filas} == {'Renuncia'}
    assert {f['socio_id'] for f in filas} == {s['id'] for s in socios}
    assert all(f['coach_antes'] == origen and f['coach_despues'] == destino for f in filas)
    assert repo.get('coaches', origen)['activo'] is False
    # ya inactivo: no puede ser destino; origen = destino y origen inexistente tampoco
    assert c2.post(f'/v1/admin/coaches/{destino}/traspasar', json={'coach_destino_id': origen, **MOTIVO}, headers=adm).status_code == 422
    assert c2.post(f'/v1/admin/coaches/{destino}/traspasar', json={'coach_destino_id': destino, **MOTIVO}, headers=adm).status_code == 409
    assert c2.post('/v1/admin/coaches/6f1c1b2e-0000-4000-8000-0000000000ff/traspasar',
                   json={'coach_destino_id': destino, **MOTIVO}, headers=adm).status_code == 422


def test_traspaso_sin_desactivar_deja_activo_al_origen(c2, app2, adm):
    repo = app2.state.repo
    r = c2.post(f'/v1/admin/coaches/{COACHES[4]}/traspasar', json={'coach_destino_id': COACHES[1], **MOTIVO}, headers=adm)
    assert r.status_code == 200 and r.json()['sociosMovidos'] == 600
    assert repo.get('coaches', COACHES[4])['activo'] is True


def test_desactivar_exige_que_no_tenga_socios(c2, app2, adm):
    r = c2.patch(f'/v1/admin/coaches/{COACHES[1]}', json={'activo': False}, headers=adm)
    n = len(app2.state.repo.find('socios', coach_id=COACHES[1]))
    assert r.status_code == 409 and r.json()['detail'] == f'Primero traspasa sus {n} socios'
    assert app2.state.repo.get('coaches', COACHES[1])['activo'] is True
    # el que quedó sin socios sí se puede activar y desactivar
    assert c2.patch(f'/v1/admin/coaches/{COACHES[4]}', json={'activo': False}, headers=adm).json()['activo'] is False
    assert c2.patch(f'/v1/admin/coaches/{COACHES[4]}', json={'activo': True}, headers=adm).json()['activo'] is True
    assert c2.patch('/v1/admin/coaches/6f1c1b2e-0000-4000-8000-0000000000ff', json={'activo': True}, headers=adm).status_code == 404


def test_un_coach_inactivo_no_puede_iniciar_sesion(c2, app2):
    login = {'email': 'coach@tnt.demo', 'password': 'clave-coach-prueba'}
    app2.state.repo.update('coaches', COACHES[0], {'activo': False})
    r = c2.post('/v1/auth/login', json=login)
    assert r.status_code == 403 and r.json()['detail'] == 'Tu usuario de coach está desactivado'
    app2.state.repo.update('coaches', COACHES[0], {'activo': True})
    r = c2.post('/v1/auth/login', json=login)
    assert r.status_code == 200 and r.json()['nombre'] == 'Coach Demo'   # el nombre sale de la tabla coaches


# ------------------------------------------------------------------ ver como coach
def test_admin_con_coach_id_ve_solo_ese_coach_y_el_coach_no_puede_espiar(c2, app2, adm):
    repo = app2.state.repo
    for s in repo.find('socios')[:1500]:
        repo.update('socios', s['id'], {'riesgo_abandono': 0.5, 'nivel_riesgo': 'medio', 'segmento': 'nocturno_nuevo'})
    c0, c1 = COACHES[0], COACHES[1]
    n0 = len(repo.find('socios', coach_id=c0))
    ajeno = _socio_de(app2, c1)
    _trabajo(repo, _socio_de(app2, c1)['id'], c1)

    todos = c2.get('/v1/coach/socios', headers=adm).json()['totalSocios']
    de_c0 = c2.get(f'/v1/coach/socios?coach_id={c0}', headers=adm).json()
    assert todos == 3000 and de_c0['totalSocios'] == n0 < todos
    ids0 = {s['id'] for s in repo.find('socios', coach_id=c0)}
    assert de_c0['socios'] and all(s['id'] in ids0 for s in de_c0['socios'])
    assert sum(p['socios'] for p in c2.get(f'/v1/coach/perfiles?coach_id={c0}', headers=adm).json()['perfiles']) <= n0
    assert all(a['coach_id'] == c1 for a in c2.get(f'/v1/coach/alertas?coach_id={c1}', headers=adm).json())
    assert c2.get(f'/v1/coach/alertas?coach_id={c0}', headers=adm).json() == []
    assert c2.get(f"/v1/coach/fichas?dni={ajeno['dni']}&coach_id={c0}", headers=adm).status_code == 404   # no es de c0
    assert c2.get(f"/v1/coach/fichas?dni={ajeno['dni']}&coach_id={c1}", headers=adm).status_code == 200
    assert c2.get('/v1/coach/rutinas-pendientes?coach_id=' + c1, headers=adm).json()
    assert c2.get(f'/v1/coach/rutinas-pendientes?coach_id={c0}', headers=adm).json() == []
    assert c2.get('/v1/coach/mantenimiento?coach_id=' + c0, headers=adm).status_code == 200
    assert c2.get(f'/v1/coach/socios?coach_id={UUID_MALO}', headers=adm).status_code == 422
    # un coach que manda el coach_id de otro sigue viendo SOLO lo suyo
    espia = c2.get(f'/v1/coach/socios?coach_id={c1}', headers=_coach(0)).json()
    assert espia['totalSocios'] == n0 and all(s['id'] in ids0 for s in espia['socios'])
    assert c2.get(f"/v1/coach/fichas?dni={ajeno['dni']}&coach_id={c1}", headers=_coach(0)).status_code == 404
    assert c2.get(f'/v1/coach/alertas?coach_id={c1}', headers=_coach(0)).json() == []
    assert c2.get(f'/v1/coach/rutinas-pendientes?coach_id={c1}', headers=_coach(0)).json() == []


# ------------------------------------------------------------------ update_donde
def test_update_donde_memoria_cuenta_y_exige_filtro():
    repo = RepoMemoria()
    repo.insert_muchos('socios', [{'coach_id': 'a'}, {'coach_id': 'a'}, {'coach_id': 'b'}])
    assert repo.update_donde('socios', {'coach_id': 'c'}, coach_id='a') == 2
    assert sorted(s['coach_id'] for s in repo.find('socios')) == ['b', 'c', 'c']
    assert repo.update_donde('socios', {'coach_id': 'z'}, coach_id='nadie') == 0
    with pytest.raises(ValueError):
        repo.update_donde('socios', {'coach_id': 'z'})
    assert sorted(s['coach_id'] for s in repo.find('socios')) == ['b', 'c', 'c']   # no tocó nada


def test_update_donde_supabase_es_un_solo_patch():
    vistas = []

    def responder(req: httpx.Request) -> httpx.Response:
        vistas.append(req)
        return httpx.Response(200, json=[{'id': str(i)} for i in range(3)])

    repo = RepoSupabase('https://x.supabase.co', 'sb_secret_x')
    repo.http = httpx.Client(transport=httpx.MockTransport(responder), base_url='https://x.supabase.co/rest/v1')
    assert repo.update_donde('alertas', {'coach_id': 'n'}, coach_id='o', resuelta=False) == 3
    assert len(vistas) == 1 and vistas[0].method == 'PATCH' and vistas[0].url.path == '/rest/v1/alertas'
    assert dict(vistas[0].url.params) == {'coach_id': 'eq.o', 'resuelta': 'eq.false'}
    assert vistas[0].headers['Prefer'] == 'return=representation'
    with pytest.raises(ValueError):
        repo.update_donde('alertas', {'coach_id': 'n'})
    assert len(vistas) == 1   # sin filtro ni siquiera llega a la red
