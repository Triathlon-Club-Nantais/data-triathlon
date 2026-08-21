"""DTO de la gestion admin du mot de passe partagé du site (#509).

Patron identique à `schemas/benevole_access.py` (#271) : un seul secret
partagé, jamais rendu en dehors de `SiteAccessGeneratedOut`.
"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.site_access import MAX_PASSWORD_LENGTH


class SiteAccessConfigOut(BaseModel):
    """État courant — **jamais** le mot de passe ni son empreinte."""

    configured: bool
    updated_at: datetime | None = None
    updated_by: str | None = None


class SiteAccessReplaceIn(BaseModel):
    """Corps de `PUT /admin/site-access`.

    `max_length` est celle de la connexion, **au même jeton** : poser un mot de
    passe que `POST /site-access/session` refuserait ensuite en 422 mettrait
    tout le monde dehors (relevé en revue de #513, cf. `MAX_PASSWORD_LENGTH`).
    """

    password: str = Field(min_length=8, max_length=MAX_PASSWORD_LENGTH)


class SiteAccessGeneratedOut(BaseModel):
    """Réponse de `POST /admin/site-access/generate` — la **seule** route qui
    renvoie jamais un mot de passe en clair."""

    password: str
    updated_at: datetime
    updated_by: str
