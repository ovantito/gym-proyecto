"""Carga de los modelos .joblib UNA sola vez, al iniciar la aplicación."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib


@dataclass
class Modelos:
    afluencia: Any
    abandono: Any
    kmeans: Any
    kmeans_scaler: Any
    meanshift: Any
    meanshift_scaler: Any
    meta: dict

    @property
    def version(self) -> str:
        return self.meta['version']

    @property
    def vars_abandono(self) -> list[str]:
        return self.meta['abandono']['variables']


def cargar_modelos(directorio: Path) -> Modelos:
    d = Path(directorio)
    meta = json.loads((d / 'metadata.json').read_text(encoding='utf-8'))
    return Modelos(
        afluencia=joblib.load(d / 'afluencia.joblib'),
        abandono=joblib.load(d / 'abandono.joblib'),
        kmeans=joblib.load(d / 'kmeans.joblib'),
        kmeans_scaler=joblib.load(d / 'kmeans_scaler.joblib'),
        meanshift=joblib.load(d / 'meanshift.joblib'),
        meanshift_scaler=joblib.load(d / 'meanshift_scaler.joblib'),
        meta=meta,
    )
