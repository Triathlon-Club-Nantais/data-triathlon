"""
Point d'entrée FastAPI — usine à application.

Lancement : `uvicorn app.main:app --reload --port 8001`
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    setup_logging()
    settings = get_settings()

    app = FastAPI(title="Triathlon Club Results — v2")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # Bilan SQL par requête HTTP (#89). Monté seulement si le bilan est activé :
    # éteint, l'application n'a pas même un middleware de plus dans sa pile.
    if settings.sql_query_stats:
        from app.core.sql_observability import SqlStatsMiddleware

        app.add_middleware(SqlStatsMiddleware)

    # API versionnée : tous les endpoints v1 sont montés sous /api/v1.
    from app.api.v1.router import api_router as v1_router

    app.include_router(v1_router, prefix="/api/v1")

    logger.info("Application initialisée (CORS: %s)", settings.cors_origins)

    # Socle OpenTelemetry (#89) : éteint par défaut, aucun paquet OTel chargé.
    from app.core.database import engine
    from app.core.tracing import setup_tracing

    setup_tracing(enabled=settings.otel_enabled, app=app, engine=engine)

    return app


app = create_app()
