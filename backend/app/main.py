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


def _warn_if_auth_unconfigured() -> None:
    """Nomme, au démarrage, ce qui empêche toute connexion — en développement.

    Une installation sans secrets est un état **légitime** (FR-036) et ne doit
    rien casser : cette fonction ne change aucun comportement, elle nomme un
    état. Mais le silence complet a un coût mesuré — un `backend/.env` absent
    donne un backend qui démarre normalement, un `/auth/methods` à `[]` et un
    écran de connexion qui dit « aucun moyen de connexion » sans dire pourquoi.

    Restreint aux bases SQLite, à la demande : pas de bruit récurrent dans
    Sentry pour une installation qui n'utilise délibérément pas
    l'authentification. `is_sqlite` sert déjà de garde « environnement jetable »
    dans `scripts/reset_db.py`, qui refuse de tourner sur autre chose. Limite du
    choix : un développement branché sur PostgreSQL n'aura pas l'avertissement.
    """
    settings = get_settings()
    if not settings.is_sqlite:
        return

    missing = [
        name
        for name, value in (
            ("AUTH_SESSION_SECRET_KEY", settings.auth_session_secret_key),
            ("AUTH_REDIRECT_BASE_URL", settings.auth_redirect_base_url),
        )
        if not value
    ]
    if missing:
        logger.warning(
            "Authentication is not configured; no login method will be offered. "
            "Missing core settings: %s. Check backend/.env — pydantic-settings "
            "reads that exact name, not .env.local.",
            ", ".join(missing),
        )

    from app.services.auth.idp import registry

    # Le **slug** seul : le contrat `IdentityProvider` n'énumère aucun mécanisme,
    # et deviner ici `AUTH_<SLUG>_CLIENT_ID` remettrait dans cette usine la
    # connaissance du mécanisme que le contrat tient à l'écart (FR-033).
    unconfigured = [
        slug for slug in registry.slugs() if not registry.PROVIDERS[slug].is_configured()
    ]
    if unconfigured:
        logger.warning(
            "Identity provider(s) not configured: %s — see docs/ci-cd.md for "
            "the settings each one needs.",
            ", ".join(unconfigured),
        )


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

    _warn_if_auth_unconfigured()
    return app


app = create_app()
