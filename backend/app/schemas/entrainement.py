"""DTO Pydantic pour le calendrier des entraînements jeunes (#868, epic #863)."""
from datetime import date as date_
from datetime import datetime
from datetime import time as time_

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ParticipantRead(BaseModel):
    """Un participant inscrit à un entraînement.

    `jeune_id` seul — pas de nom ni de contact : le profil du jeune référencé
    est porté par la sous-issue parallèle #867, hors du contrat de cette
    ressource (cf. `research.md` §Dépendance sur le profil jeune).
    """

    jeune_id: int
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_utc(self, value: datetime) -> str:
        return f"{value.isoformat()}Z"


class EntrainementRead(BaseModel):
    """Un entraînement tel qu'il apparaît dans la liste du calendrier.

    `participant_count` évite un aller-retour par séance pour afficher la
    liste ; il ne remplace pas le détail, qui seul nomme les inscrits.
    """

    id: int
    date: date_
    heure_debut: time_ | None
    lieu: str | None
    type_seance: str | None
    participant_count: int


class EntrainementDetailRead(EntrainementRead):
    """Un entraînement et sa liste de participants inscrits."""

    participants: list[ParticipantRead]


class EntrainementCreate(BaseModel):
    """Création d'un entraînement. Seule `date` est obligatoire (#868)."""

    model_config = ConfigDict(extra="forbid")

    date: date_
    heure_debut: time_ | None = None
    lieu: str | None = None
    type_seance: str | None = None


class EntrainementUpdate(BaseModel):
    """Modification d'un entraînement. Les quatre champs sont facultatifs et
    indépendants — seuls ceux fournis sont écrits (même patron que `GroupUpdate`)."""

    model_config = ConfigDict(extra="forbid")

    date: date_ | None = None
    heure_debut: time_ | None = None
    lieu: str | None = None
    type_seance: str | None = None


class ParticipantAdd(BaseModel):
    """Inscription d'un jeune à un entraînement, par son identifiant seul."""

    model_config = ConfigDict(extra="forbid")

    jeune_id: int = Field(gt=0)
