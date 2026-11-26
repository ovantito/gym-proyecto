"""Lesiones (config en app/core/lesiones.py) y síntomas «de hoy»."""
import pytest
from app.core import lesiones as cfg

from ml.datos import MAQUINAS
from tests.conftest import token  # noqa: F401  (fixtures de conftest)

PARQ_NO = [False] * 7
MED_OK = {'peso_kg': 70.0, 'grasa_pct': 22.0, 'presion_sistolica': 120, 'presion_diastolica': 78, 'pulso_reposo': 68}
IDS = list(cfg.LESIONES)


def test_config_cubre_las_7_lesiones_y_solo_usa_maquinas_del_catalogo():
    assert IDS == ['rodilla', 'hombro', 'espalda_baja', 'cuello', 'muneca_codo', 'tobillo', 'cadera']
    assert cfg.LESIONES['espalda_baja'].etiqueta == 'Espalda baja (lumbar)'
    for id_, les in cfg.LESIONES.items():
        assert les.excluidas, f'{id_} no excluye ninguna máquina'
        for m, porque in les.excluidas.items():
            assert m in MAQUINAS.index, f'{id_}: {m} no existe en el catálogo M-01…M-18'
            assert len(porque) > 15, f'{id_}/{m}: falta el porqué de la exclusión'


def _con_lesion(client, est_headers, abrir_sesion, i, lesion):
    sid = abrir_sesion(i)
    assert client.post(f'/v1/socios/{sid}/mediciones', json=MED_OK, headers=est_headers).status_code == 201
    r = client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': PARQ_NO, 'lesiones': [lesion]}, headers=est_headers)
    assert r.status_code == 200, r.text
    return sid, r.json()


@pytest.mark.parametrize('n, lesion', list(enumerate(IDS)))
def test_cada_lesion_excluye_sus_maquinas_y_nunca_salen_en_la_rutina(client, est_headers, abrir_sesion, n, lesion):
    sid, ficha = _con_lesion(client, est_headers, abrir_sesion, 220 + n, lesion)
    esperadas = set(cfg.LESION_MAQUINAS_EXCLUIDAS[lesion])
    assert ficha['semaforo'] == 'amarillo' and set(ficha['maquinasExcluidas']) == esperadas
    for hora in (7, 12, 19):   # A* en distintas franjas: nunca debe colarse una máquina prohibida
        j = client.post(f'/v1/socios/{sid}/rutinas/generar', json={'hora': hora, 'dia': 0}, headers=est_headers).json()
        usadas = {e['maquina'] for d in j['dias'] for e in d['ejercicios']}
        assert usadas and not usadas & esperadas, f'{lesion}: salió {usadas & esperadas}'


def test_todas_las_lesiones_juntas_siguen_dando_rutina_sin_maquinas_prohibidas(client, est_headers, abrir_sesion):
    sid = abrir_sesion(230)
    client.post(f'/v1/socios/{sid}/mediciones', json=MED_OK, headers=est_headers)
    r = client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': PARQ_NO, 'lesiones': IDS}, headers=est_headers)
    assert r.status_code == 200
    j = client.post(f'/v1/socios/{sid}/rutinas/generar', json={'hora': 19, 'dia': 0}, headers=est_headers).json()
    prohibidas = {m for ms in cfg.LESION_MAQUINAS_EXCLUIDAS.values() for m in ms}
    usadas = {e['maquina'] for d in j['dias'] for e in d['ejercicios']}
    assert usadas and not usadas & prohibidas


def test_lesion_desconocida_da_422(client, est_headers, abrir_sesion):
    sid = abrir_sesion(231)
    r = client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': PARQ_NO, 'lesiones': ['codo_de_tenista']}, headers=est_headers)
    assert r.status_code == 422


def test_lesion_sin_maquinas_que_excluir_baja_la_intensidad_y_queda_en_amarillo(client, est_headers, abrir_sesion, monkeypatch):
    monkeypatch.setitem(cfg.LESIONES, 'prueba', cfg.Lesion('Prueba'))
    monkeypatch.setitem(cfg.LESION_MAQUINAS_EXCLUIDAS, 'prueba', ())
    sid, ficha = _con_lesion(client, est_headers, abrir_sesion, 232, 'prueba')
    assert ficha['semaforo'] == 'amarillo' and ficha['maquinasExcluidas'] == []
    gen = {'hora': 19, 'dia': 0}
    ej = client.post(f'/v1/socios/{sid}/rutinas/generar', json=gen, headers=est_headers).json()['dias'][0]['ejercicios']
    assert len(ej) == 6 and {e['series'] for e in ej} == {1}   # amarillo normal = 2 series; aquí una menos
    sid2, _ = _con_lesion(client, est_headers, abrir_sesion, 233, 'rodilla')
    ej2 = client.post(f'/v1/socios/{sid2}/rutinas/generar', json=gen, headers=est_headers).json()['dias'][0]['ejercicios']
    assert {e['series'] for e in ej2} == {2}   # con exclusiones la pauta amarilla no se toca


# ------------------------------------------------------------------ síntomas de hoy
@pytest.mark.parametrize('sintoma, motivo', [('dolor_cabeza', 'Dolor de cabeza fuerte hoy'), ('mareo', 'Mareo hoy')])
def test_sintoma_de_hoy_da_amarillo_y_no_se_guarda_en_la_ficha(client, est_headers, abrir_sesion, sintoma, motivo):
    i = 240 + (sintoma == 'mareo')
    sid = abrir_sesion(i)
    client.post(f'/v1/socios/{sid}/mediciones', json=MED_OK, headers=est_headers)
    r = client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': PARQ_NO, 'sintomas_hoy': [sintoma]}, headers=est_headers).json()
    assert r['semaforo'] == 'amarillo' and motivo in r['motivos']
    guardada = client.get(f'/v1/socios/{sid}/ficha-salud', headers=est_headers).json()
    assert guardada['parq'] == PARQ_NO and guardada['lesiones'] == []          # nada permanente
    assert sintoma not in str(guardada.get('parq')) and 'sintomas_hoy' not in guardada


def test_al_volver_otro_dia_sin_sintomas_vuelve_a_verde(client, est_headers, abrir_sesion, app):
    sid = abrir_sesion(242)
    client.post(f'/v1/socios/{sid}/mediciones', json=MED_OK, headers=est_headers)
    url = f'/v1/socios/{sid}/ficha-salud'
    r = client.put(url, json={'parq': PARQ_NO, 'sintomas_hoy': ['mareo']}, headers=est_headers)
    assert r.json()['semaforo'] == 'amarillo'
    fila = app.state.repo.find('fichas_salud', socio_id=sid)[0]
    assert not any('sintoma' in k for k in fila)                                # ninguna columna/campo de síntomas
    assert fila['parq'] == PARQ_NO and fila['lesiones'] == []
    # «Sí, sigo igual» al día siguiente: se manda la ficha tal cual, sin síntomas
    r = client.put(f'/v1/socios/{sid}/ficha-salud', json={'parq': fila['parq'], 'lesiones': fila['lesiones']}, headers=est_headers)
    assert r.json()['semaforo'] == 'verde' and r.json()['motivos'] == []


def test_sintoma_invalido_da_422_y_el_dolor_de_cabeza_no_pasa_a_rojo(client, est_headers, abrir_sesion):
    sid = abrir_sesion(243)
    url = f'/v1/socios/{sid}/ficha-salud'
    assert client.put(url, json={'parq': PARQ_NO, 'sintomas_hoy': ['invento']}, headers=est_headers).status_code == 422
    r = client.put(url, json={'parq': PARQ_NO, 'sintomas_hoy': ['dolor_cabeza', 'mareo']}, headers=est_headers).json()
    assert r['semaforo'] == 'amarillo' and not r['requiereAptoMedico']


def test_panel_de_rutinas_por_aprobar_incluye_las_lesiones(client, est_headers, abrir_sesion, app):
    from app.core.semilla import COACHES

    from tests.test_ficha_persistente import _socio_de
    i = _socio_de(app, COACHES[0], 250)
    sid, _ = _con_lesion(client, est_headers, abrir_sesion, i, 'cuello')
    client.post(f'/v1/socios/{sid}/rutinas/generar', json={'hora': 19, 'dia': 0}, headers=est_headers)
    pend = client.get('/v1/coach/rutinas-pendientes', headers=token('coach', COACHES[0])).json()
    r = next(x for x in pend if x['socio_id'] == sid)
    assert r['lesiones'] == ['cuello'] and 'M-13' in r['maquinasExcluidas']
