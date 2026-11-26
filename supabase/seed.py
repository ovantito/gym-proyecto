"""Carga los 3,000 socios simulados (semilla 42) y una estación piloto en Supabase.

Uso (desde la raíz del repo, con SUPABASE_URL y SUPABASE_SECRET_KEY en .env o en el entorno):
    python supabase/seed.py

Los socios simulados tienen coach_id de coaches ficticios; en Supabase real, asigna coaches
reales con: update socios set coach_id = '<uuid del coach>' where ...;
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from app.core.config import get_settings  # noqa: E402
from app.core.repositorio import RepoSupabase  # noqa: E402
from app.core.semilla import sembrar  # noqa: E402


def main() -> None:
    cfg = get_settings()
    if not cfg.usa_supabase:
        sys.exit('Faltan SUPABASE_URL y SUPABASE_SECRET_KEY (ver .env.example).')
    repo = RepoSupabase(cfg.supabase_url, cfg.supabase_secret_key)
    if repo.find('socios'):
        sys.exit('La tabla socios ya tiene datos; no se vuelve a sembrar.')
    est, clave = sembrar(repo)
    print(f"Sembrados 3000 socios. Estación '{est['nombre']}' id={est['id']}")
    print(f'X-Station-Key (guárdala ahora, no se vuelve a mostrar): {clave}')


if __name__ == '__main__':
    main()
