"""DTO du registre d'alias de club (#635)."""
from datetime import datetime

from pydantic import BaseModel


class ClubAliasOut(BaseModel):
    id: int
    canonical_name: str
    #: La forme normalisée de l'alias — c'est elle qui est comparée, donc
    #: c'est elle qu'on affiche (même choix que `CounterScopeEntryOut.value`).
    alias: str
    created_at: datetime
    created_by: str | None


class ClubAliasList(BaseModel):
    entries: list[ClubAliasOut]


class ClubAliasIn(BaseModel):
    canonical_name: str
    alias: str
