from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parents[3]   # tnt-fit/


class Settings(BaseSettings):
    """Toda la configuración sale de variables de entorno / .env (nunca del código)."""

    model_config = SettingsConfigDict(env_file=('.env', '../.env'), extra='ignore')

    entorno: str = 'dev'
    # Supabase (si faltan, se usa el repositorio en memoria)
    supabase_url: str | None = None
    supabase_secret_key: str | None = None   # sb_secret_...: SOLO backend/.env y Render; jamás en un frontend
    supabase_jwt_secret: str | None = None
    supabase_publishable_key: str | None = None   # sb_publishable_...: pública; el login del panel contra Supabase Auth
    supabase_jwks_url: str | None = None   # por defecto: <SUPABASE_URL>/auth/v1/.well-known/jwks.json
    jwt_audience: str = 'authenticated'
    # CORS: dominios del frontend separados por coma. Vacío = ninguno permitido.
    cors_origins: str = ''
    rate_limit_defecto: str = '120/minute'
    rate_limit_sesiones: str = '10/minute'
    rate_limit_login: str = '5/minute'
    rate_limit_ver: str = '30/minute'
    # Modelos
    modelos_dir: Path = RAIZ / 'ml' / 'modelos'
    modo_offline: bool = False   # True => Hill Climbing en vez de A*
    zona_horaria: str = 'America/Lima'
    # Demo en memoria
    semilla_demo: bool = True
    demo_station_key: str | None = None   # si no se da, se genera una aleatoria y se imprime
    demo_coach_password: str | None = None   # idem para los usuarios demo del panel
    demo_admin_password: str | None = None
    # Cloudflare R2 (videos)
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str | None = None
    r2_prefijo: str = 'ejercicios/'

    @field_validator('r2_account_id')
    @classmethod
    def _solo_el_id(cls, v: str | None) -> str | None:
        """Si pegaron la URL del endpoint completa, se extrae solo el Account ID (32 caracteres hex)."""
        if not v:
            return None
        m = re.search(r'[0-9a-fA-F]{32}', v)
        return m.group(0) if m else v.strip()

    @property
    def origenes_cors(self) -> list[str]:
        lista = [o.strip() for o in self.cors_origins.split(',') if o.strip()]
        if not lista and self.entorno == 'dev':   # desarrollo: estación (5173) y panel del coach (5174)
            return ['http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:5174', 'http://127.0.0.1:5174']
        return lista

    @property
    def jwks_url_efectiva(self) -> str | None:
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        return f'{self.supabase_url.rstrip("/")}/auth/v1/.well-known/jwks.json' if self.supabase_url else None

    @property
    def usa_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
