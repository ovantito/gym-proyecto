"""Lesiones que el socio puede declarar y qué máquinas del catálogo (M-01…M-18) se le excluyen por cada una.

Este es el ÚNICO lugar donde se configuran. Para cambiar una exclusión se edita aquí; el backend, la validación de
la ficha y las pruebas leen de este archivo. Cada máquina lleva escrito el porqué (el patrón de movimiento que
cargaría la zona lesionada), para que el coach pueda auditar o corregir el criterio.

Catálogo (ml/datos.py): M-01 Prensa 45° · M-02 Sentadilla en Smith · M-03 Hack squat · M-04 Curl femoral · M-05 Hip thrust ·
M-06 Peso muerto rumano · M-07 Press de pecho · M-08 Press banca · M-09 Aperturas en máquina · M-10 Jalón al pecho ·
M-11 Dominadas asistidas · M-12 Remo en polea · M-13 Press de hombro · M-14 Press militar · M-15 Elevaciones laterales ·
M-16 Crunch en máquina · M-17 Plancha en banco · M-18 Rueda abdominal.

Una lesión SIN máquinas que excluir no se queda sin efecto: baja la intensidad de la rutina (una serie menos) y, como
cualquier lesión, deja al socio en amarillo (rutina con restricciones y aprobación del coach).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Lesion:
    etiqueta: str                                              # como se muestra al socio y al coach
    excluidas: dict[str, str] = field(default_factory=dict)    # máquina -> por qué se excluye


LESIONES: dict[str, Lesion] = {
    'rodilla': Lesion('Rodilla', {
        'M-02': 'Sentadilla en Smith: flexión profunda de rodilla con la barra encima.',
        'M-03': 'Hack squat: flexión profunda de rodilla con carga sobre los hombros.',
    }),
    'hombro': Lesion('Hombro', {
        'M-08': 'Press banca: empuje horizontal con el hombro en rotación externa y carga alta.',
        'M-14': 'Press militar: empuje por encima de la cabeza con barra; el hombro queda en el rango más comprometido.',
    }),
    'espalda_baja': Lesion('Espalda baja (lumbar)', {
        'M-06': 'Peso muerto rumano: bisagra de cadera con la columna lumbar cargada en flexión.',
        'M-02': 'Sentadilla en Smith: la barra comprime la columna lumbar de forma axial.',
    }),
    'cuello': Lesion('Cuello (cervical)', {
        'M-02': 'Sentadilla en Smith: la barra apoya sobre el cuello y los trapecios (carga axial cervical).',
        'M-13': 'Press de hombro: empuje por encima de la cabeza que comprime la columna cervical.',
        'M-14': 'Press militar: empuje por encima de la cabeza con barra, carga axial sobre el cuello.',
        'M-11': 'Dominadas asistidas: el cuello queda en tracción y extensión mientras el cuerpo cuelga.',
    }),
    'muneca_codo': Lesion('Muñeca o codo', {
        'M-08': 'Press banca: la barra carga la muñeca en extensión y el codo en flexión bajo peso.',
        'M-14': 'Press militar: barra sostenida con la muñeca en extensión y el codo cargado por encima de la cabeza.',
        'M-11': 'Dominadas asistidas: todo el peso cuelga del agarre (muñeca y codo en tracción).',
        'M-17': 'Plancha en banco: el peso del cuerpo se apoya en el antebrazo/muñeca y el codo.',
        'M-18': 'Rueda abdominal: apoyo y empuje sobre la muñeca y el codo con el cuerpo extendido.',
    }),
    'tobillo': Lesion('Tobillo', {
        'M-02': 'Sentadilla en Smith: exige dorsiflexión profunda de tobillo bajo carga.',
        'M-03': 'Hack squat: los pies en plataforma inclinada cargan el tobillo en dorsiflexión forzada.',
    }),
    'cadera': Lesion('Cadera', {
        'M-05': 'Hip thrust: extensión de cadera con carga sobre la pelvis en todo el recorrido.',
        'M-06': 'Peso muerto rumano: bisagra de cadera con la carga más alta en la articulación.',
    }),
}

LESION_ETIQUETAS: dict[str, str] = {k: v.etiqueta for k, v in LESIONES.items()}
LESION_MAQUINAS_EXCLUIDAS: dict[str, tuple[str, ...]] = {k: tuple(v.excluidas) for k, v in LESIONES.items()}


def lesiones_sin_exclusion(lesiones: list[str]) -> list[str]:
    """Lesiones declaradas que no excluyen ninguna máquina: para ellas la rutina baja de intensidad."""
    return [x for x in lesiones if x in LESIONES and not LESIONES[x].excluidas]
