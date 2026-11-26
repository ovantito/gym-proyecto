"""Carga datos de demo en Supabase: usuarios (Auth), 3,000 socios simulados (semilla 42) y una estación piloto.

Uso (desde la raíz del repo, con SUPABASE_URL y SUPABASE_SECRET_KEY en .env):
    python supabase/seed.py [archivo_salida]

- Crea en Supabase Auth a coach, coach2 y admin con app_metadata.role (si no existen) y contraseñas aleatorias.
- Reparte los socios entre coach y coach2 (el FK de socios.coach_id exige usuarios reales).
- La estación guarda SOLO el hash de su clave.
Las contraseñas y la clave de la estación se escriben en `archivo_salida` (JSON) y no se imprimen: guárdalas y borra el archivo.
"""
import json
import secrets
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from app.core.config import get_settings  # noqa: E402
from app.core.repositorio import RepoSupabase  # noqa: E402
from app.core.semilla import sembrar  # noqa: E402

USUARIOS = [('coach@tnt.demo', 'coach'), ('coach2@tnt.demo', 'coach'), ('admin@tnt.demo', 'admin')]


def asegurar_usuarios(cfg) -> tuple[dict[str, str], dict[str, str]]:
    """Devuelve ({email: user_id}, {email: contraseña solo de los creados ahora})."""
    h = {'apikey': cfg.supabase_secret_key, 'Content-Type': 'application/json'}
    base = f'{cfg.supabase_url.rstrip("/")}/auth/v1/admin/users'
    lista = httpx.get(base, params={'per_page': 200}, headers=h, timeout=20).raise_for_status().json()['users']
    existentes = {u['email']: u['id'] for u in lista}
    ids, claves = {}, {}
    for email, rol in USUARIOS:
        if email in existentes:
            ids[email] = existentes[email]
            continue
        pw = secrets.token_urlsafe(14)
        cuerpo = {'email': email, 'password': pw, 'email_confirm': True, 'app_metadata': {'role': rol}}
        r = httpx.post(base, headers=h, timeout=20, json=cuerpo)
        r.raise_for_status()
        ids[email], claves[email] = r.json()['id'], pw
    return ids, claves


def main() -> None:
    cfg = get_settings()
    if not cfg.usa_supabase:
        sys.exit('Faltan SUPABASE_URL y SUPABASE_SECRET_KEY (ver .env.example).')
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('seed_secretos.json')
    repo = RepoSupabase(cfg.supabase_url, cfg.supabase_secret_key)
    if repo.find('socios'):
        sys.exit('La tabla socios ya tiene datos; no se vuelve a sembrar.')
    ids, claves = asegurar_usuarios(cfg)
    est, clave = sembrar(repo, coaches=[ids['coach@tnt.demo'], ids['coach2@tnt.demo']])
    secretos = {'estacion_id': est['id'], 'estacion_clave': clave, 'usuarios': ids, 'passwords': claves}
    salida.write_text(json.dumps(secretos), encoding='utf-8')
    print(f"Sembrados 3000 socios (entre coach y coach2). Estación '{est['nombre']}' id={est['id']} (solo se guardó el hash).")
    print(f'Usuarios Auth listos: {len(ids)} ({len(claves)} nuevos). Secretos en {salida}: guárdalos y bórralo.')


if __name__ == '__main__':
    main()
