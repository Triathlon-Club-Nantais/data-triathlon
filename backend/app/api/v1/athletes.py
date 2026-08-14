"""Router Athletes : recherche et fiche athlète avec ses participations."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.club import is_club_scope
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.season import parse_seasons
from app.repositories import athlete_repository, participation_repository
from app.schemas.athlete import AthleteBrief, AthleteSeasonActivity
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
    db: Session = Depends(get_db),
):
    """Athlètes ayant ≥1 participation sur `seasons`, avec leur compte (#274)."""
    lignes = athlete_repository.list_with_season_participation_count(
        db, seasons=parse_seasons(seasons), club_only=is_club_scope(scope)
    )
    return [
        AthleteSeasonActivity(id=a.id, nom=a.nom, prenom=a.prenom, participation_count=n)
        for a, n in lignes
    ]


@router.get("/athletes/{athlete_id}")
def get_athlete(athlete_id: int, db: Session = Depends(get_db)):
    athlete = athlete_repository.get(db, athlete_id)
    if not athlete:
        raise NotFoundError("Athlète introuvable")
    participations = participation_repository.list_for_athlete(db, athlete_id)
    counts = participation_repository.finishers_count_by_group(
        db, [p.course_id for p in participations]
    )
    items = []
    for p in participations:
        item = AthleteParticipationOut.model_validate(p)
        item.course_finishers = counts.get((p.course_id, bool(p.is_relay)))
        items.append(item)
    return {"athlete": AthleteBrief.model_validate(athlete), "participations": items}
