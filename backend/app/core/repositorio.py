"""Repositorio de datos. Dos implementaciones con la misma interfaz mínima:

- RepoMemoria: para probar sin internet (se pierde al reiniciar).
- RepoSupabase: PostgREST de Supabase vía httpx, con la secret key sb_secret_... (solo en el servidor).
Los IDs los genera la aplicación (uuid4) para que ambas se comporten igual.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import httpx


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def nuevo_id() -> str:
    return str(uuid.uuid4())


class RepoMemoria:
    nombre = 'memoria'

    def __init__(self) -> None:
        self.t: dict[str, dict[str, dict]] = {}

    def insert(self, tabla: str, fila: dict) -> dict:
        fila = {'id': nuevo_id(), **fila}
        self.t.setdefault(tabla, {})[fila['id']] = dict(fila)
        return dict(fila)

    def insert_muchos(self, tabla: str, filas: list[dict]) -> None:
        for f in filas:
            self.insert(tabla, f)

    def get(self, tabla: str, id_: str) -> dict | None:
        f = self.t.get(tabla, {}).get(id_)
        return dict(f) if f else None

    def find(self, tabla: str, **eq: Any) -> list[dict]:
        return [dict(f) for f in self.t.get(tabla, {}).values() if all(f.get(k) == v for k, v in eq.items())]

    def update(self, tabla: str, id_: str, patch: dict) -> dict | None:
        f = self.t.get(tabla, {}).get(id_)
        if f is None:
            return None
        f.update(patch)
        return dict(f)

    def update_donde(self, tabla: str, patch: dict, **eq: Any) -> int:
        """Actualiza TODAS las filas que cumplen el filtro y devuelve cuántas cambió. Sin filtro: ValueError."""
        if not eq:
            raise ValueError('update_donde exige al menos un filtro (no se actualiza la tabla completa)')
        filas = [f for f in self.t.get(tabla, {}).values() if all(f.get(k) == v for k, v in eq.items())]
        for f in filas:
            f.update(patch)
        return len(filas)

    def upsert(self, tabla: str, fila: dict, clave: str) -> dict:
        previas = self.find(tabla, **{clave: fila[clave]})
        if previas:
            return self.update(tabla, previas[0]['id'], fila)  # type: ignore[return-value]
        return self.insert(tabla, fila)


class RepoSupabase:
    nombre = 'supabase'

    def __init__(self, url: str, secret_key: str) -> None:
        self.http = httpx.Client(
            base_url=f'{url.rstrip("/")}/rest/v1', timeout=15,
            # Las claves sb_secret_ no son JWT: van SOLO en `apikey` (no en Authorization: Bearer).
            headers={'apikey': secret_key, 'Content-Type': 'application/json'})

    def _ok(self, r: httpx.Response) -> httpx.Response:
        r.raise_for_status()
        return r

    def insert(self, tabla: str, fila: dict) -> dict:
        fila = {'id': nuevo_id(), **fila}
        r = self._ok(self.http.post(f'/{tabla}', json=fila, headers={'Prefer': 'return=representation'}))
        return r.json()[0]

    def insert_muchos(self, tabla: str, filas: list[dict]) -> None:
        for i in range(0, len(filas), 500):
            lote = [{'id': nuevo_id(), **f} for f in filas[i:i + 500]]
            self._ok(self.http.post(f'/{tabla}', json=lote, headers={'Prefer': 'return=minimal'}))

    def get(self, tabla: str, id_: str) -> dict | None:
        r = self._ok(self.http.get(f'/{tabla}', params={'id': f'eq.{id_}'}))
        d = r.json()
        return d[0] if d else None

    def find(self, tabla: str, **eq: Any) -> list[dict]:
        params = {k: f'eq.{str(v).lower() if isinstance(v, bool) else v}' for k, v in eq.items()}
        out: list[dict] = []
        while True:   # PostgREST devuelve máx. 1000 filas por petición
            r = self._ok(self.http.get(f'/{tabla}', params=params, headers={'Range': f'{len(out)}-{len(out) + 999}'}))
            lote = r.json()
            out += lote
            if len(lote) < 1000:
                return out

    def update(self, tabla: str, id_: str, patch: dict) -> dict | None:
        r = self._ok(self.http.patch(f'/{tabla}', params={'id': f'eq.{id_}'}, json=patch,
                                     headers={'Prefer': 'return=representation'}))
        d = r.json()
        return d[0] if d else None

    def update_donde(self, tabla: str, patch: dict, **eq: Any) -> int:
        """Un solo PATCH para todas las filas del filtro (el traspaso masivo mueve ~1500 socios). Devuelve cuántas cambió."""
        if not eq:
            raise ValueError('update_donde exige al menos un filtro (no se actualiza la tabla completa)')
        params = {k: f'eq.{str(v).lower() if isinstance(v, bool) else v}' for k, v in eq.items()}
        r = self._ok(self.http.patch(f'/{tabla}', params=params, json=patch, headers={'Prefer': 'return=representation'}))
        return len(r.json())

    def upsert(self, tabla: str, fila: dict, clave: str) -> dict:
        r = self._ok(self.http.post(f'/{tabla}', params={'on_conflict': clave}, json=fila,
                                    headers={'Prefer': 'resolution=merge-duplicates,return=representation'}))
        return r.json()[0]
