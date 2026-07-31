"""
Configuration centralisée de l'application.

Toutes les variables d'environnement passent par cet objet `Settings` typé
(pydantic-settings) — plus aucun `os.getenv` éparpillé dans le code.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Base de données ───────────────────────────────────────────────────────
    database_url: str = "sqlite:///./triathlon.db"

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Liste restreinte en production (plus de "*"). Format : URLs séparées par des
    # virgules dans la variable d'env CORS_ORIGINS.
    # NoDecode : désactive le parsing JSON de pydantic-settings pour ce champ, afin
    # que le validateur _split_cors reçoive bien la chaîne CSV brute (sinon JSONDecodeError).
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_json: bool = False  # True → logs JSON (ingestion Render/Datadog)

    # ── Cache TTL dynamique (PRD F1) ──────────────────────────────────────────
    # Course en cours (un temps final manquant) → re-scrape rapide.
    cache_ttl_in_progress_seconds: int = 10 * 60  # 10 minutes
    # Course terminée (tous les temps présents) → re-scrape rare.
    cache_ttl_finished_seconds: int = 30 * 24 * 60 * 60  # 30 jours

    # ── Géocodage (Nominatim) ─────────────────────────────────────────────────
    geocode_user_agent: str = "TriathlonClubResults/1.0 contact@triclunantais.fr"
    geocode_min_interval_seconds: float = 1.1  # rate limit Nominatim : max 1 req/s

    # ── Authentification GitHub OAuth (issue #114) ────────────────────────────
    # Client OAuth GitHub — laisser vides désactive l'auth sans casser l'API publique
    # (les endpoints /api/v1/auth/github/* renvoient alors 503, cf. FR-020).
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""
    # Cible du callback GitHub. Défaut None → l'endpoint construit
    # request.url_for("github_callback") au runtime.
    # **Obligatoire en prod**, et sur le domaine du FRONTEND (Vercel) — pas
    # celui du backend (Render). Les cookies `tcn_oauth_state` et `tcn_session`
    # sont posés par la réponse au navigateur, qui les attribue au domaine de
    # l'origine appelée (Vercel via le rewrite `/api/*`). Si le callback pointe
    # sur Render, GitHub renvoie le navigateur sur Render → cookie state
    # host-only sur Vercel jamais envoyé → 400 « État CSRF invalide. »
    # systématique. Cf. review B1 de la PR #159.
    github_oauth_redirect_url: str | None = None
    # Clé HMAC de signature des cookies de session et du cookie de state OAuth.
    # Sa rotation invalide toutes les sessions en cours (kill-switch).
    session_secret_key: str = ""
    session_max_age_seconds: int = 7 * 24 * 60 * 60  # 7 jours
    # False en dev sur http://localhost (sinon le navigateur ignore le cookie).
    # Doit rester True en prod (Render, Vercel = TLS).
    session_cookie_secure: bool = True
    # Où le callback redirige après avoir posé le cookie. Une chaîne fixe côté
    # config, jamais un paramètre d'entrée du callback (open redirect sinon).
    frontend_post_login_url: str = "/"
    # Liste blanche de logins GitHub autorisés à ouvrir une session (CSV).
    # Vide = **tout compte GitHub accepté** — mode explicite, à réserver au
    # dev. En prod, renseigner les logins des contributeurs. Un login GitHub
    # est stable (GitHub bloque la réutilisation à la suppression). Cf. review
    # B2 de la PR #159 : sans allowlist, tout compte GitHub obtient une fiche
    # `users`, ce qui pollue la table sur laquelle #115 posera `require_role`.
    github_allowed_logins: Annotated[list[str], NoDecode] = []

    @field_validator("cors_origins", "github_allowed_logins", mode="before")
    @classmethod
    def _split_csv(cls, v):
        """Accepte une chaîne CSV depuis l'environnement."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("session_secret_key")
    @classmethod
    def _reject_weak_session_secret(cls, v: str) -> str:
        """Empty is ok (disables auth explicitly, FR-020); short is not.

        A `dev` or `changeme` value would pass unnoticed and produce a HMAC
        signature trivially forgeable — this is exactly what would break
        after RBAC lands in #115.
        """
        if v and len(v) < 32:
            raise ValueError(
                "SESSION_SECRET_KEY must be at least 32 characters (or empty "
                "to explicitly disable auth). Generate with: "
                'python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Instance unique (mise en cache) des réglages."""
    settings = Settings()
    # Supabase (et certains PaaS) exposent postgres:// — SQLAlchemy veut postgresql://
    if settings.database_url.startswith("postgres://"):
        settings.database_url = settings.database_url.replace("postgres://", "postgresql://", 1)
    return settings
