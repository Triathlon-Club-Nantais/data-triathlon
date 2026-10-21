"""Réglages de la fiche publique de l'athlète rattaché (#1692)."""
from pydantic import BaseModel, Field

from app.schemas.ids import DbId


class PublicPageSettingsWrite(BaseModel):
    hide_best_times: bool = False
    hide_progression: bool = False
    hide_comparison: bool = False
    links: list[str] = Field([], max_length=3)
    pinned_participation_id: DbId | None = None


class PublicPageSettingsRead(PublicPageSettingsWrite):
    #: Plusieurs comptes sont rattachés à ma fiche : liens, objectif et épingle n'y sont alors pas montrés.
    shared: bool = False
