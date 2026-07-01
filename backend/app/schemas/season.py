"""Schéma Pydantic d'une saison sportive (sélecteur du tableau de bord)."""
from pydantic import BaseModel


class SeasonOut(BaseModel):
    """Saison disponible : année de début, libellé et compteurs."""

    start_year: int
    label: str
    event_count: int
    participation_count: int
    is_current: bool
