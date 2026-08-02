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
    # que le validateur _split_csv reçoive bien la chaîne CSV brute (sinon JSONDecodeError).
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

    # ── Observabilité SQL (issue #89) ─────────────────────────────────────────
    # Garde-fou permanent : toute requête au-delà du seuil sort en WARNING.
    # 0 désactive ce log ; avec `sql_query_stats` à False, plus aucun listener
    # n'est posé — coût strictement nul.
    sql_slow_query_ms: int = 100
    # Bilan agrégé par unité de travail (requête HTTP, épreuve importée) : c'est
    # lui qui rend un N+1 visible. Verbeux, donc éteint par défaut.
    sql_query_stats: bool = False
    # Socle OpenTelemetry. Éteint = aucun paquet OTel n'est même chargé.
    # L'exporter se règle par la variable standard OTEL_TRACES_EXPORTER.
    otel_enabled: bool = False

    # ── Géocodage (Nominatim) ─────────────────────────────────────────────────
    geocode_user_agent: str = "TriathlonClubResults/1.0 contact@triclunantais.fr"
    geocode_min_interval_seconds: float = 1.1  # rate limit Nominatim : max 1 req/s

    # ── Authentification (#114) ───────────────────────────────────────────────
    # Huit réglages, tous absents par défaut : une installation sans secrets est
    # un état légitime où le site public reste intact et où aucun moyen de
    # connexion n'est proposé (FR-036).
    #
    # Signe le jeton d'état du parcours (JWS HS256). Vide = authentification non
    # configurée ; non vide, elle doit faire au moins 32 caractères (FR-037).
    auth_session_secret_key: str = ""
    auth_github_client_id: str = ""
    auth_github_client_secret: str = ""
    # Liste blanche des adresses autorisées à ouvrir une session, en CSV comme
    # CORS_ORIGINS. **Fail-closed** : vide interdit toute connexion (FR-007) —
    # une variable absente sur Render est un incident ordinaire, et « vide =
    # tout le monde » l'aurait transformé en ouverture à n'importe quel compte.
    auth_allowed_emails: Annotated[list[str], NoDecode] = []
    # Origine de l'**interface**, jamais celle de l'API : c'est elle qui proxifie
    # `/api/*`, donc elle seule à qui les cookies sont attribués. La destination
    # de retour vient d'ici et n'est jamais acceptée en paramètre (FR-026).
    auth_redirect_base_url: str = "http://127.0.0.1:3000"
    # En clair (développement), le préfixe `__Host-` est retiré du nom des
    # cookies : il exige `Secure`. Le nom est **dérivé** de ce réglage.
    auth_cookie_secure: bool = True
    auth_session_ttl_days: int = 7      # sans prolongation glissante
    auth_state_ttl_seconds: int = 600   # durée de vie du jeton d'état

    @field_validator("cors_origins", "auth_allowed_emails", mode="before")
    @classmethod
    def _split_csv(cls, v):
        """Accepte une chaîne CSV depuis l'environnement."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("auth_session_secret_key")
    @classmethod
    def _reject_weak_secret_key(cls, v: str) -> str:
        """Refuse une clé de signature trop courte (FR-037).

        Vide reste accepté : c'est ainsi qu'on déclare une installation **sans**
        authentification. Une clé courte, elle, est un défaut de configuration —
        le démarrage échoue plutôt que de signer avec.
        """
        if v and len(v) < 32:
            raise ValueError(
                "AUTH_SESSION_SECRET_KEY must be at least 32 characters long "
                '(python -c "import secrets; print(secrets.token_urlsafe(64))")'
            )
        return v

    @property
    def auth_is_configured(self) -> bool:
        """Vrai si le **socle** est configuré, indépendamment de tout fournisseur.

        Deux conditions seulement, et elles sont transverses : la clé qui signe
        le jeton d'état, et une liste d'autorisation non vide — sans elle aucune
        connexion ne peut aboutir, donc proposer un moyen de connexion mentirait
        (FR-007).

        Les secrets d'un fournisseur **ne sont pas ici** : chacun déclare sa
        propre configuration par `is_configured()`. Les exiger reviendrait à
        masquer un second fournisseur pourtant configuré, et à devoir modifier
        ce garde à chaque ajout — ce que FR-033 proscrit.
        """
        return bool(self.auth_session_secret_key and self.auth_allowed_emails)

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
