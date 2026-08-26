"""DTO de la portée des compteurs (#95)."""
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from app.models.counter_scope_entry import CLUB_LABEL, NON_FEDERAL_DISCIPLINE


class ScopeKind(StrEnum):
    """La nature d'entrée, telle qu'elle s'écrit dans l'URL.

    Distincte de ce qui est stocké (`non_federal_discipline`, `tcn_club_label`) :
    l'URL est un contrat public lu par des humains, la colonne est un jeton
    technique. Une nature inconnue rend 422 par FastAPI, jamais une liste vide.
    """

    DISCIPLINES = "disciplines"
    CLUB_LABELS = "club-labels"

    @property
    def stored(self) -> str:
        return NON_FEDERAL_DISCIPLINE if self is ScopeKind.DISCIPLINES else CLUB_LABEL


class CounterScopeEntryOut(BaseModel):
    id: int
    value: str
    #: Pour une discipline : le slug appartient-il à la nomenclature ? Porte
    #: l'avertissement de FR-011. Toujours `True` pour un libellé de club, qui
    #: n'a pas de nomenclature de référence.
    is_known: bool
    created_at: datetime
    #: Nom d'affichage de l'auteur, `None` pour les entrées d'amorçage — l'écran
    #: les rend par « Configuration initiale ».
    created_by: str | None


class CounterScopeOut(BaseModel):
    """Les deux listes d'un coup : l'écran les affiche ensemble."""

    disciplines: list[CounterScopeEntryOut]
    club_labels: list[CounterScopeEntryOut]


class CounterScopeEntryIn(BaseModel):
    value: str
