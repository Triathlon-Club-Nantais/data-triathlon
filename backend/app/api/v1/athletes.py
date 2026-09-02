"""Router Athletes : recherche et fiche athlète avec ses participations."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.club import is_club_scope
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.permissions import P
from app.core.season import parse_seasons
from app.models.user import User
from app.repositories import (
    athlete_repository,
    participation_repository,
    season_validation_repository,
)
from app.schemas.athlete import AthleteBrief, AthleteSearchResult, AthleteSeasonActivity
from app.schemas.participation import AthleteParticipationOut

router = APIRouter(tags=["athletes"])


@router.get("/athletes", response_model=list[AthleteBrief])
def list_athletes(
    name: str | None = Query(None),
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return athlete_repository.search(
        db, name=name, club_only=is_club_scope(scope), page=page, page_size=page_size
    )


# Déclarée avant `/athletes/{athlete_id}` : sinon FastAPI matche "season-activity"
# comme un `athlete_id` (int) et rend 422 au lieu de résoudre cette route (#274).
@router.get("/athletes/season-activity", response_model=list[AthleteSeasonActivity])
def list_athletes_season_activity(
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    seasons: str | None = Query(None),
    federal_only: bool = Query(False, description="Retire trail, course à pied et cyclisme."),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.PAGES_PREVIEW)),
):
    """Athlètes ayant ≥1 participation sur `seasons`, avec leurs compteurs (#274, #382, #709)."""
    saisons = parse_seasons(seasons)
    lignes = athlete_repository.list_with_season_participation_count(
        db,
        seasons=saisons,
        club_only=is_club_scope(scope),
        federal_only=federal_only,
    )
    # Le statut de validation est mono-saison (research.md D9) : `null` dès que
    # `seasons` n'en désigne pas exactement une, sinon la carte des validés.
    validations = (
        season_validation_repository.map_by_athlete(
            db, athlete_ids=[a.id for a, *_ in lignes], season=saisons[0]
        )
        if len(saisons) == 1
        else {}
    )
    return [
        AthleteSeasonActivity(
            id=a.id,
            nom=a.nom,
            prenom=a.prenom,
            participation_count=affiliees_club,
            total_count=total,
            validated_count=validees,
            club_affiliated_count=affiliees_club,
            season_validated=validations.get(a.id, False) if len(saisons) == 1 else None,
        )
        for a, total, validees, affiliees_club in lignes
    ]


# Déclarée avant `/athletes/{athlete_id}`, même raison que
# `/athletes/season-activity` ci-dessus (#484).
@router.get("/athletes/search", response_model=list[AthleteSearchResult])
def search_athletes(
    q: str = Query(..., min_length=2),
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Recherche classée par pertinence pour la palette `⌘K` (#484, NAV-8).

    Distincte de `GET /athletes` : celle-ci trie par pertinence (préfixe
    exact, début de mot, sous-chaîne) puis volume, et rend le compte de
    participations — deux choses que `GET /athletes` ne fait pas et n'a pas à
    faire pour ses propres appelants.
    """
    lignes = athlete_repository.search_by_relevance(
        db, term=q, club_only=is_club_scope(scope), limit=limit
    )
    return [
        AthleteSearchResult(
            **AthleteBrief.model_validate(athlete).model_dump(), participation_count=nombre
        )
        for athlete, nombre in lignes
    ]


@router.get("/athletes/{athlete_id}")
def get_athlete(
    athlete_id: int,
    seasons: str | None = Query(None),
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    db: Session = Depends(get_db),
):
    """Fiche athlète et ses participations.

    Les deux filtres sont **optionnels et neutres par défaut** (#502) : sans
    eux, la route rend la carrière entière, comme depuis toujours. Ils servent
    la bande « Ma saison » du tableau de bord, qui doit compter sur la même
    base que les compteurs club affichés juste dessous — mêmes noms et mêmes
    sémantiques que sur `/stats` et `/athletes/season-activity`.
    """
    athlete = athlete_repository.get(db, athlete_id)
    if not athlete:
        raise NotFoundError("Athlète introuvable")
    participations = participation_repository.list_for_athlete(
        db, athlete_id, seasons=parse_seasons(seasons), federal_only=federal_only
    )
    counts = participation_repository.finishers_count_by_group(
        db, [p.course_id for p in participations]
    )
    items = []
    for p in participations:
        item = AthleteParticipationOut.model_validate(p)
        item.course_finishers = counts.get((p.course_id, bool(p.is_relay)))
        items.append(item)
    return {"athlete": AthleteBrief.model_validate(athlete), "participations": items}
