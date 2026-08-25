"""DTO des retours utilisateurs (#267) — formes de `contracts/feedback-api.md`."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models.user_feedback import FEEDBACK_STATUSES
from app.schemas.admin import _PatchNonVide


class FeedbackCreate(BaseModel):
    """Corps de `POST /feedback` — route publique, aucune authentification.

    L'email de l'émetteur n'est **jamais** un champ ici : il est déduit côté
    serveur de la session SSO courante (contracts/feedback-api.md).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    type: Literal["bug", "feedback"]
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)
    #: Auto-joints par le client (research.md) — bornés comme `title`/`body`,
    #: sans quoi rien n'empêchait une valeur arbitrairement longue en base.
    page_url: str | None = Field(default=None, max_length=2000)
    user_agent: str | None = Field(default=None, max_length=500)
    #: Champ caché du formulaire (research.md §D2) : rempli → rejet silencieux.
    honeypot: str | None = None


class FeedbackCreated(BaseModel):
    """Réponse minimale de la création — identique que le signalement soit
    réellement inséré ou rejeté en silence pour honeypot (research.md §D2)."""

    id: int
    status: str


class FeedbackCounts(BaseModel):
    """Le nombre de signalements par statut — le « N nouveaux » de la file (#500).

    Les quatre statuts sont **toujours** des clés, à zéro le cas échéant : le
    front en tire ses quatre filtres, et un filtre qui apparaîtrait seulement
    quand il a des lignes serait un filtre introuvable. Une route à part, comme
    `GET /courses/count` : envelopper `GET /admin/feedback` dans une page pour y
    loger des totaux serait un changement de contrat de v1 (Principe IV).
    """

    nouveau: int = 0
    en_cours: int = 0
    traite: int = 0
    ignore: int = 0
    total: int = 0


class FeedbackRead(BaseModel):
    """Un signalement, tel que rendu à un pouvoir `feedback:read`.

    **Ne porte jamais `ip_address`** (data-model.md §D4) : le champ existe en
    base pour la limitation de débit, il ne traverse jamais la frontière HTTP.
    `email` est `None` pour un signalement anonyme.
    """

    id: int
    type: str
    title: str
    body: str
    page_url: str | None
    user_agent: str | None
    status: str
    github_url: str | None
    created_at: datetime
    email: str | None


class FeedbackUpdate(_PatchNonVide):
    """Corps de `PATCH /admin/feedback/{id}` — `status` et/ou `github_url`,
    séparément ou ensemble (contracts/feedback-api.md). Aucun des deux champs
    n'admet `null` : ni l'un ni l'autre ne se « vide » dans cette v1."""

    status: str | None = Field(default=None, min_length=1)
    #: `HttpUrl` valide et normalise (patron `ScrapeRequest.url`, #49) — la
    #: normalisation est acceptable ici, une URL d'issue GitHub n'a pas de
    #: forme ambiguë à préserver.
    github_url: HttpUrl | None = None

    @field_validator("status")
    @classmethod
    def _statut_connu(cls, valeur: str | None) -> str | None:
        if valeur is not None and valeur not in FEEDBACK_STATUSES:
            raise ValueError(
                f"Statut inconnu. Valeurs acceptées : {', '.join(FEEDBACK_STATUSES)}."
            )
        return valeur
