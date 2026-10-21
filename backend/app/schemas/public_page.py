"""Réglages de la fiche publique de l'athlète rattaché (#1692)."""
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.ids import DbId
from app.schemas.season_goal import SeasonGoalRead


class PublicPageSettingsWrite(BaseModel):
    hide_best_times: bool = False
    hide_progression: bool = False
    hide_comparison: bool = False
    links: list[str] = Field([], max_length=3)
    pinned_participation_id: DbId | None = None


class PublicPageSettingsRead(PublicPageSettingsWrite):
    #: Plusieurs comptes sont rattachés à ma fiche : liens, objectif et épingle n'y sont alors pas montrés.
    shared: bool = False


class PublicLink(BaseModel):
    url: str
    label: str


class PublicPageRead(BaseModel):
    """Ce que la fiche publique montre (#1692) : neutre tant que rien n'est réglé."""

    hidden: list[Literal["best_times", "progression", "comparison"]] = []
    links: list[PublicLink] = []
    goal: SeasonGoalRead | None = None
    pinned_participation_id: int | None = None
