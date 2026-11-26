"""A* y Hill Climbing del Script 3 del Colab, como funciones reutilizables.

Problema: ordenar la rutina (un ejercicio por patrón de movimiento) para minimizar
el tiempo perdido = traslado + acomodo + espera estimada en cada máquina.
  - Estado:  (patrones ya hechos, máquina actual)
  - Heurística de A*: suma de (menor espera posible + acomodo) por patrón pendiente.
    Es admisible (ignora el traslado), por eso A* es óptimo.
Hill Climbing queda solo como respaldo (modo offline): rápido pero no siempre óptimo.
"""
from __future__ import annotations

import heapq
import itertools
from collections.abc import Iterable

import pandas as pd

try:  # importable como paquete (ml.busqueda) o como módulo suelto
    from .datos import CAMBIO_MIN, ESTACION, MAQUINAS, PATRONES, VEL_M_MIN
except ImportError:  # pragma: no cover
    from datos import CAMBIO_MIN, ESTACION, MAQUINAS, PATRONES, VEL_M_MIN


def dist(a, b) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def pos(m: str):
    return ESTACION if m == 'EST' else (MAQUINAS.loc[m, 'x'], MAQUINAS.loc[m, 'y'])


class ProblemaRecorrido:
    """`excluidas`: códigos de máquina que el semáforo/lesión prohíbe."""

    def __init__(self, espera: dict[str, float], excluidas: Iterable[str] = ()):
        self.espera = espera
        excluidas = set(excluidas)
        self.opciones = {p: [m for m in MAQUINAS.index[MAQUINAS.patron == p] if m not in excluidas] for p in PATRONES}
        # un patrón sin ninguna máquina permitida se omite (no hay nada que hacer en él)
        self.patrones = [p for p in PATRONES if self.opciones[p]]
        self.min_esp = {p: min(espera[m] for m in self.opciones[p]) for p in self.patrones}

    def inicio(self):
        return (frozenset(), 'EST')

    def es_meta(self, s) -> bool:
        return len(s[0]) == len(self.patrones)

    def sucesores(self, s):
        hechos, actual = s
        for p in self.patrones:
            if p in hechos:
                continue
            for m in self.opciones[p]:
                costo = dist(pos(actual), pos(m)) / VEL_M_MIN + CAMBIO_MIN + self.espera[m]
                yield (hechos | {p}, m), m, costo

    def h(self, s) -> float:
        return sum(self.min_esp[p] + CAMBIO_MIN for p in self.patrones if p not in s[0])


def a_estrella(pb: ProblemaRecorrido):
    """Devuelve (camino de códigos de máquina, costo en min, nodos generados)."""
    ini = pb.inicio()
    cont = itertools.count()
    frontera = [(pb.h(ini), next(cont), 0.0, ini, [])]
    mejor_g = {ini: 0.0}
    gen = 0
    while frontera:
        _, _, g, s, camino = heapq.heappop(frontera)
        if pb.es_meta(s):
            return camino, g, gen
        if g > mejor_g.get(s, 1e18):
            continue
        for s2, m, c in pb.sucesores(s):
            gen += 1
            g2 = g + c
            if g2 < mejor_g.get(s2, 1e18) - 1e-9:
                mejor_g[s2] = g2
                heapq.heappush(frontera, (g2 + pb.h(s2), next(cont), g2, s2, camino + [m]))
    return [], 0.0, gen


def hill_climbing(pb: ProblemaRecorrido):
    """Respaldo offline: siempre el vecino inmediato más barato, sin retroceder."""
    s, camino, g, gen = pb.inicio(), [], 0.0, 0
    while not pb.es_meta(s):
        vecinos = list(pb.sucesores(s))
        gen += len(vecinos)
        s, m, c = min(vecinos, key=lambda v: v[2])
        camino.append(m)
        g += c
    return camino, g, gen


def orden_fijo(pb: ProblemaRecorrido):
    """Línea base sin motor: orden impreso de patrones y la máquina más popular permitida."""
    s, c, camino = 'EST', 0.0, []
    for p in pb.patrones:
        m = max(pb.opciones[p], key=lambda k: MAQUINAS.loc[k, 'popularidad'])
        c += dist(pos(s), pos(m)) / VEL_M_MIN + CAMBIO_MIN + pb.espera[m]
        s = m
        camino.append(m)
    return camino, c, 0


def espera_por_maquina(modelo_afluencia, hora: int, dia_semana: int, mes: int = 4, feriado: int = 0):
    """Minutos de espera estimados por máquina = popularidad × ocupación predicha (Script 2)."""
    ocup = float(modelo_afluencia.predict(pd.DataFrame([{'hora': hora, 'dia_semana': dia_semana, 'mes': mes, 'feriado': feriado}]))[0])
    espera = {m: round(max(0.0, float(MAQUINAS.loc[m, 'popularidad']) * ocup / 9.0 - 1.0), 2) for m in MAQUINAS.index}
    return espera, ocup
