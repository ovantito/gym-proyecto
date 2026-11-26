"""Pruebas de reglas fijas (semáforo), búsqueda (A*) y modelos."""
import random

import pytest
from app.modulos.salud import calcular_semaforo, es_atipica, maquinas_excluidas

from ml.busqueda import ProblemaRecorrido, a_estrella, hill_climbing, orden_fijo

SIN_PARQ = [False] * 7


def sem(sis=120, dia=80, pulso=70, parq=SIN_PARQ, lesiones=()):
    return calcular_semaforo(sistolica=sis, diastolica=dia, pulso=pulso, parq=list(parq), lesiones=list(lesiones))[0]


@pytest.mark.parametrize('kw,esperado', [
    ({}, 'verde'),
    ({'sis': 139, 'dia': 89}, 'verde'),
    ({'sis': 140}, 'amarillo'), ({'dia': 90}, 'amarillo'),
    ({'parq': [False, False, False, False, True, False, False]}, 'amarillo'),   # sí no crítico
    ({'lesiones': ['rodilla']}, 'amarillo'),
    ({'sis': 159, 'dia': 99}, 'amarillo'),
    ({'sis': 160}, 'rojo'), ({'dia': 100}, 'rojo'),
    ({'pulso': 100}, 'verde'), ({'pulso': 101}, 'rojo'),
    ({'parq': [True] + [False] * 6}, 'rojo'),                                    # respuesta crítica
    ({'parq': [False, False, True, False, False, False, False]}, 'rojo'),
    ({'sis': 170, 'lesiones': ['rodilla']}, 'rojo'),                              # rojo gana a amarillo
])
def test_semaforo_umbrales(kw, esperado):
    assert sem(**kw) == esperado


def test_semaforo_sin_datos_no_dispara_reglas():
    assert calcular_semaforo(sistolica=None, diastolica=None, pulso=None, parq=SIN_PARQ, lesiones=[])[0] == 'verde'


def _espera(rnd):
    from ml.datos import MAQUINAS
    return {m: round(rnd.uniform(0, 9), 2) for m in MAQUINAS.index}


def test_lesion_rodilla_nunca_recibe_m02_ni_m03():
    excl = maquinas_excluidas(['rodilla'])
    assert {'M-02', 'M-03'} <= set(excl)
    rnd = random.Random(1)
    for _ in range(60):
        for alg in (a_estrella, hill_climbing, orden_fijo):
            camino, _, _ = alg(ProblemaRecorrido(_espera(rnd), excl))
            assert not {'M-02', 'M-03'} & set(camino)
            assert len(camino) == 6


def test_astar_igual_o_menor_que_hill_climbing_y_orden_fijo():
    rnd = random.Random(7)
    for i in range(80):
        excl = ('M-02', 'M-03') if i % 5 == 0 else ()
        pb = ProblemaRecorrido(_espera(rnd), excl)
        c_a = a_estrella(pb)[1]
        assert c_a <= hill_climbing(pb)[1] + 1e-9
        assert c_a <= orden_fijo(pb)[1] + 1e-9


def test_abandono_no_usa_var_grasa_pct(app):
    mo = app.state.modelos
    assert 'var_grasa_pct' not in mo.vars_abandono
    assert 'var_grasa_pct' not in mo.meta['abandono']['variables']
    assert 'var_grasa_pct' not in list(mo.abandono.feature_names_in_)   # lo que el modelo realmente recibe
    assert not any('grasa' in n for n in mo.abandono.named_steps['prep'].get_feature_names_out())


def test_medicion_con_6kg_de_cambio_es_atipica(app):
    mo = app.state.modelos
    assert es_atipica(mo, 6.0, 0.0, 122, 210)
    assert es_atipica(mo, -6.0, 0.0, 122, 210)
    assert not es_atipica(mo, 0.4, -0.1, 122, 210)
