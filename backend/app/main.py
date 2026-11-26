"""Aplicación FastAPI de la Estación TNT Fit. Arranque:  uvicorn app.main:create_app --factory  (desde backend/)."""
from __future__ import annotations

import secrets

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import Settings, get_settings
from app.core.limites import limiter
from app.core.modelos import cargar_modelos
from app.core.repositorio import RepoMemoria, RepoSupabase, ahora
from app.core.semilla import sembrar, sembrar_usuarios
from app.modulos import admin, auth, coach, estacion, prediccion, rutinas, salud


def _registrar_version(repo, modelos) -> None:
    if not repo.find('modelos_version', version=modelos.version, fecha_entrenamiento=modelos.meta['fecha_entrenamiento']):
        repo.insert('modelos_version', {
            'version': modelos.version, 'fecha_entrenamiento': modelos.meta['fecha_entrenamiento'],
            'metricas': {k: modelos.meta[k]['metricas'] for k in ('afluencia', 'abandono', 'kmeans', 'meanshift')},
            'registrada': ahora()})


def create_app(settings: Settings | None = None, repo=None) -> FastAPI:
    cfg = settings or get_settings()
    app = FastAPI(title='Estación TNT Fit — API', version='1.0.0')
    app.state.settings = cfg
    if not cfg.usa_supabase and not cfg.supabase_jwt_secret:   # demo: secreto efímero para firmar los JWT del login
        cfg.supabase_jwt_secret = secrets.token_urlsafe(48)
    app.state.modelos = cargar_modelos(cfg.modelos_dir)   # una sola vez, al iniciar
    if repo is None and cfg.entorno == 'prod' and not cfg.usa_supabase:
        # Sin esto, un error de configuración dejaría el servicio público en modo demo (datos y usuarios de prueba).
        raise RuntimeError('ENTORNO=prod exige SUPABASE_URL y SUPABASE_SECRET_KEY; no se arranca en modo demo.')
    if repo is None:
        repo = RepoSupabase(cfg.supabase_url, cfg.supabase_secret_key) if cfg.usa_supabase else RepoMemoria()
        if isinstance(repo, RepoMemoria) and cfg.semilla_demo:
            est, clave = sembrar(repo, cfg.demo_station_key)
            print(f"[demo en memoria] estación id={est['id']}")
            if not cfg.demo_station_key:
                print(f'[demo en memoria] X-Station-Key: {clave}')
            for u in sembrar_usuarios(repo, cfg.demo_coach_password, cfg.demo_admin_password):
                print(f"[demo en memoria] panel · {u['rol']}: {u['email']} / {u['password']}")
    app.state.repo = repo
    _registrar_version(repo, app.state.modelos)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=cfg.origenes_cors, allow_credentials=False,
                       allow_methods=['GET', 'POST', 'PUT', 'PATCH'], allow_headers=['Authorization', 'Content-Type', 'X-Station-Key'])

    for m in (auth, estacion, salud, rutinas, prediccion, coach, admin):
        app.include_router(m.router, prefix='/v1')

    @app.get('/v1/salud', tags=['sistema'])
    def health(request: Request):
        mo = request.app.state.modelos
        return {'estado': 'ok', 'repositorio': request.app.state.repo.nombre,
                'modelos': {'version': mo.version, 'entrenado': mo.meta['fecha_entrenamiento'],
                            'scikit_learn': mo.meta['scikit_learn'],
                            'cargados': ['afluencia', 'abandono', 'kmeans', 'meanshift']}}

    return app

