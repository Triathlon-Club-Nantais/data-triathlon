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
    """Athlète + ses compteurs d'épreuves sur la saison filtrée (#274, #709).

    Pas de champ `club` : la route qui l'expose est déjà scopée club par
    l'appelant (`scope=club`), à la différence d'`AthleteBrief`.

    `participation_count` reste tel quel (égal à `club_affiliated_count`) —
    additif seulement, Principe IV (research.md D3). `total_count` /
    `validated_count` / `club_affiliated_count` sont les trois compteurs
    distincts demandés par #709 (FR-001 à FR-003). `season_validated` est
    posé par la User Story 3 (`null` tant qu'elle n'est pas implémentée ou
    que `seasons` désigne plusieurs saisons, research.md D9).
    """

    id: int
    nom: str
    prenom: str = ""
    participation_count: int
    total_count: int
    validated_count: int
    club_affiliated_count: int
    season_validated: bool | None = None
