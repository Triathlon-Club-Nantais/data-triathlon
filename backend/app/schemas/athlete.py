"""Schémas Pydantic pour Athlete."""
from pydantic import BaseModel, ConfigDict


class AthleteBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    prenom: str = ""
    gender: str = ""
    club: str | None = None


class AthleteSearchResult(AthleteBrief):
    """Résultat de `GET /athletes/search` (#484) : `AthleteBrief` + le compte
    de participations qu'affiche la palette `⌘K` sous le nom. Pas de
    `birth_date` — cette route reste publique, la date de naissance reste
    réservée à `athletes:read` (voir `athlete_repository.search_admin`)."""

    participation_count: int


class AthleteSeasonActivity(BaseModel):
    """Athlète + son nombre d'épreuves sur la saison filtrée (#274).

    Pas de champ `club` : la route qui l'expose est déjà scopée club par
    l'appelant (`scope=club`), à la différence d'`AthleteBrief`.
    """

    id: int
    nom: str
    prenom: str = ""
    participation_count: int
