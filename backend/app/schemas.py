"""Esquemas Pydantic: validan TODO lo que entra por la API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.umbrales import LESION_MAQUINAS_EXCLUIDAS, PARQ_NUM_PREGUNTAS


class Estricto(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class SesionIn(Estricto):
    dni: str | None = Field(default=None, pattern=r'^\d{8}$')
    qr: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_\-]{3,64}$')

    @model_validator(mode='after')
    def uno_solo(self):
        if (self.dni is None) == (self.qr is None):
            raise ValueError('Envía exactamente uno: dni o qr')
        return self


class MedicionIn(Estricto):
    peso_kg: float = Field(ge=20, le=300)
    grasa_pct: float = Field(ge=2, le=70)
    presion_sistolica: int = Field(ge=60, le=260)
    presion_diastolica: int = Field(ge=30, le=160)
    pulso_reposo: int = Field(ge=30, le=220)
    talla_cm: float | None = Field(default=None, ge=120, le=220)   # tallímetro de la estación
    duracion_seg: float = Field(default=210, ge=1, le=3600)
    sesion_id: str | None = Field(default=None, max_length=64)


class FichaIn(Estricto):
    parq: list[bool] = Field(min_length=PARQ_NUM_PREGUNTAS, max_length=PARQ_NUM_PREGUNTAS)
    lesiones: list[str] = Field(default_factory=list, max_length=10)
    # Opcionales: si faltan se usa la última medición válida del socio.
    presion_sistolica: int | None = Field(default=None, ge=60, le=260)
    presion_diastolica: int | None = Field(default=None, ge=30, le=160)
    pulso_reposo: int | None = Field(default=None, ge=30, le=220)

    @model_validator(mode='after')
    def lesiones_conocidas(self):
        malas = [x for x in self.lesiones if x not in LESION_MAQUINAS_EXCLUIDAS]
        if malas:
            raise ValueError(f'Lesión no reconocida: {malas}. Válidas: {sorted(LESION_MAQUINAS_EXCLUIDAS)}')
        return self


class RutinaIn(Estricto):
    hora: int | None = Field(default=None, ge=0, le=23)
    dia: int | None = Field(default=None, ge=0, le=6)   # lunes=0


Semaforo = Literal['verde', 'amarillo', 'rojo']
