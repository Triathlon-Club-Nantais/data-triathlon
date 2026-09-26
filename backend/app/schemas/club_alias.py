"""DTO du registre d'alias de club (#635)."""
from datetime import datetime

from pydantic import BaseModel, Field


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
    # Borne des colonnes `String(120)` : SQLite l'ignore, PostgreSQL levait
    # une 500 au flush (#1121). La normalisation ne fait que raccourcir.
    canonical_name: str = Field(max_length=120)
    alias: str = Field(max_length=120)
