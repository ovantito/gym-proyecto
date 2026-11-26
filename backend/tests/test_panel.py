"""Pruebas de lo que usa el panel del coach (login, aislamiento entre coaches, rechazo, atender, QR permanente...)."""
from app.core.semilla import COACHES
from app.modulos.salud import es_atipica

from tests.conftest import token

MED = {'peso_kg': 70.0, 'grasa_pct': 22.0, 'presion_sistolica': 120, 'presion_diastolica': 78, 'pulso_reposo': 68}
PARQ_NO = [False] * 7


def _login(client, email, password):
    return client.post('/v1/auth/login', json={'email': email, 'password': password})


def _amarilla(client, est_headers, abrir_sesion, i):
    """Socio nº i con lesión de rodilla → rutina pendiente de aprobación. Devuelve (socio_id, rutina_id)."""
    sid = abrir_sesion(i)
    client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': PARQ_NO, 'lesiones': ['rodilla']}, headers=est_headers)
    r = client.post(f'/v1/socios/{sid}/rutinas/generar', json={'hora': 19, 'dia': 0}, headers=est_headers).json()
    assert r['estado'] == 'pendiente_aprobacion'
    return sid, r['rutinaId']


# ------------------------------------------------------------------ login
def test_login_correcto_devuelve_jwt_que_el_backend_acepta(client):
    r = _login(client, 'coach@tnt.demo', 'clave-coach-prueba')
    assert r.status_code == 200 and r.json()['rol'] == 'coach'
    assert client.get('/v1/coach/alertas', headers={'Authorization': f"Bearer {r.json()['token']}"}).status_code == 200
    assert _login(client, 'admin@tnt.demo', 'clave-admin-prueba').json()['rol'] == 'admin'


def test_login_incorrecto_da_401_sin_revelar_si_el_correo_existe(client):
    a = _login(client, 'coach@tnt.demo', 'mala')
    b = _login(client, 'nadie@tnt.demo', 'mala')
    assert a.status_code == b.status_code == 401 and a.json() == b.json()
    assert client.post('/v1/auth/login', json={'email': 'no-es-correo', 'password': 'x'}).status_code == 422


# ------------------------------------------------------------------ aislamiento entre coaches
def test_un_coach_no_ve_socios_de_otro_coach(client, admin):
    assert client.post('/v1/prediccion/abandono/lote', headers=admin).status_code == 200
    r0 = client.get('/v1/coach/socios?limite=500', headers=token('coach', COACHES[0])).json()
    r1 = client.get('/v1/coach/socios?limite=500', headers=token('coach', COACHES[1])).json()
    c0, c1 = r0['socios'], r1['socios']
    assert c0 and c1 and not {s['id'] for s in c0} & {s['id'] for s in c1}
    assert r0['totalSocios'] == r1['totalSocios'] == 600   # cada coach solo cuenta los suyos
    assert client.get('/v1/coach/socios', headers=admin).json()['totalSocios'] == 3000
    for s in c0:
        assert s['nombre'] and len(s['factores']) == 3


def test_un_coach_no_puede_atender_alertas_ni_rutinas_de_otro(client, est_headers, abrir_sesion):
    _, rutina = _amarilla(client, est_headers, abrir_sesion, 15)   # socio 15 → coach 0
    otro = token('coach', COACHES[1])
    assert client.post(f'/v1/coach/rutinas/{rutina}/aprobar', headers=otro).status_code == 403
    assert client.post(f'/v1/coach/rutinas/{rutina}/rechazar', json={'motivo': 'no'}, headers=otro).status_code in (403, 422)
    assert all(r['id'] != rutina for r in client.get('/v1/coach/rutinas-pendientes', headers=otro).json())
    alerta = next(a for a in client.get('/v1/coach/alertas', headers=token('coach', COACHES[0])).json() if a['tipo'] == 'abandono')
    assert client.post(f"/v1/coach/alertas/{alerta['id']}/atender", headers=otro).status_code == 403


# ------------------------------------------------------------------ aprobar / rechazar y consulta de la estación
def test_aprobar_y_la_estacion_ve_el_cambio(client, est_headers, abrir_sesion):
    _, rutina = _amarilla(client, est_headers, abrir_sesion, 20)   # coach 0
    coach = token('coach', COACHES[0])
    p = next(r for r in client.get('/v1/coach/rutinas-pendientes', headers=coach).json() if r['id'] == rutina)
    assert p['socioNombre'] and p['motivos'] and 'M-02' in p['maquinasExcluidas']
    assert client.get(f'/v1/rutinas/{rutina}', headers=est_headers).json()['estado'] == 'pendiente_aprobacion'
    assert client.post(f'/v1/coach/rutinas/{rutina}/aprobar', headers=coach).json()['estado'] == 'activa'
    assert client.get(f'/v1/rutinas/{rutina}', headers=est_headers).json()['estado'] == 'activa'


def test_rechazar_guarda_motivo(client, est_headers, abrir_sesion):
    _, rutina = _amarilla(client, est_headers, abrir_sesion, 25)
    coach = token('coach', COACHES[0])
    assert client.post(f'/v1/coach/rutinas/{rutina}/rechazar', json={'motivo': ''}, headers=coach).status_code == 422
    assert client.post(f'/v1/coach/rutinas/{rutina}/rechazar', json={'motivo': 'Carga muy alta'}, headers=coach).status_code == 200
    j = client.get(f'/v1/rutinas/{rutina}', headers=est_headers).json()
    assert j['estado'] == 'rechazada' and j['motivoRechazo'] == 'Carga muy alta'
    assert client.post(f'/v1/coach/rutinas/{rutina}/aprobar', headers=coach).status_code == 409


def test_la_estacion_solo_consulta_rutinas_de_su_socio_con_sesion(client, est_headers, abrir_sesion, app):
    _, rutina = _amarilla(client, est_headers, abrir_sesion, 30)
    ajena = app.state.repo.find('rutinas')[0]
    ajena_otro = next(r for r in app.state.repo.find('rutinas') if r['socio_id'] != app.state.repo.get('rutinas', rutina)['socio_id'])
    assert ajena and client.get(f"/v1/rutinas/{ajena_otro['id']}", headers=est_headers).status_code in (200, 403)
    assert client.get('/v1/rutinas/no-existe', headers=est_headers).status_code == 404
    assert client.get(f'/v1/rutinas/{rutina}').status_code == 401


# ------------------------------------------------------------------ registrar contacto
def test_registrar_contacto_marca_la_alerta_como_atendida(client, app):
    coach = token('coach', COACHES[0])
    alerta = next(a for a in client.get('/v1/coach/alertas', headers=coach).json() if a['tipo'] == 'abandono')
    r = client.post(f"/v1/coach/alertas/{alerta['id']}/atender", headers=coach)
    assert r.status_code == 200 and r.json()['resuelta'] is True
    assert app.state.repo.get('socios', alerta['socio_id'])['coach_contacto_30d'] == 1
    assert all(a['id'] != alerta['id'] for a in client.get('/v1/coach/alertas', headers=coach).json())


# ------------------------------------------------------------------ perfiles, mantenimiento, modelo
def test_perfiles_y_modelo(client, admin):
    client.post('/v1/prediccion/abandono/lote', headers=admin)
    p = client.get('/v1/coach/perfiles', headers=admin).json()
    assert p['analizado'] and len(p['perfiles']) == 3 and sum(x['socios'] for x in p['perfiles']) == 3000
    m = client.get('/v1/coach/modelo', headers=admin).json()
    assert m['version'] and 0.5 < m['metricas']['abandono']['rocAuc'] < 1 and m['metricas']['kmeans']['silueta'] > 0


def test_mantenimiento_agrupa_lecturas_atipicas_por_estacion(client, est_headers, estacion_id, admin):
    r = client.post(f'/v1/estaciones/{estacion_id}/sesiones', json={'dni': str(10000000 + 35)}, headers=est_headers).json()
    sid, ses = r['socio']['id'], r['sesionId']
    client.post(f'/v1/socios/{sid}/mediciones', json={**MED, 'sesion_id': ses}, headers=est_headers)
    assert client.post(f'/v1/socios/{sid}/mediciones', json={**MED, 'peso_kg': 77, 'sesion_id': ses}, headers=est_headers).json()['atipica']
    grupos = client.get('/v1/coach/mantenimiento', headers=admin).json()
    g = next(x for x in grupos if x['estacionId'] == estacion_id)
    assert g['estacion'] == 'Estación piloto' and g['lecturas'][0]['falla'] == 'báscula'


# ------------------------------------------------------------------ presión alta → rojo por reglas
def test_presion_alta_165_102_no_es_atipica_y_da_rojo(client, est_headers, abrir_sesion, app):
    assert not es_atipica(app.state.modelos, 0.1, 0.0, 165, 210)
    sid = abrir_sesion(40)
    alta = {**MED, 'presion_sistolica': 165, 'presion_diastolica': 102}
    m = client.post(f'/v1/socios/{sid}/mediciones', json=alta, headers=est_headers).json()
    assert m['usada'] is True
    f = client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': PARQ_NO}, headers=est_headers).json()
    assert f['semaforo'] == 'rojo'


# ------------------------------------------------------------------ QR permanente
def test_ver_video_es_publico_y_redirige_con_url_firmada_nueva(client):
    r = client.get('/v1/ejercicios/E-M-01/ver', follow_redirects=False)
    assert r.status_code == 302 and 'X-Amz-Expires=900' in r.headers['location'] and 'Prensa-de-pierna.mp4' in r.headers['location']
    assert client.get('/v1/ejercicios/E-M-99/ver', follow_redirects=False).status_code == 404
    assert client.get('/v1/ejercicios/xx/ver', follow_redirects=False).status_code == 422


# ------------------------------------------------------------------ las claves secretas nunca llegan a un frontend
def test_ningun_frontend_menciona_la_secret_key():
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[2]
    prohibido = ('sb_secret_', 'SUPABASE_SECRET_KEY', 'service_role')
    for app in ('estacion', 'panel-coach'):
        for f in (raiz / app).rglob('*'):
            if not f.is_file() or 'node_modules' in f.parts or 'dist' in f.parts or f.name == 'package-lock.json':
                continue
            texto = f.read_text(encoding='utf-8', errors='ignore')
            assert not any(p in texto for p in prohibido), f'{f} contiene una clave secreta'


def test_cada_maquina_tiene_video_asignado():
    from app.core.videos import VIDEOS

    from ml.datos import MAQUINAS
    assert {f'E-{m}' for m in MAQUINAS.index} == set(VIDEOS)
    assert all(v.endswith('.mp4') for v in VIDEOS.values())
