"""Router Athletes : recherche et fiche athlète avec ses participations."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.repositories import athlete_repository, participation_repository
from app.schemas.athlete import AthleteBrief
from app.schemas.participation import ParticipationOut

router = APIRouter(tags=["athletes"])


@router.get("/athletes", response_model=list[AthleteBrief])
def list_athletes(
    name: str | None = Query(None),
    club: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return athlete_repository.search(db, name=name, club=club, page=page, page_size=page_size)


@router.get("/athletes/{athlete_id}")
def get_athlete(athlete_id: int, db: Session = Depends(get_db)):
    athlete = athlete_repository.get(db, athlete_id)
    if not athlete:
        raise NotFoundError("Athlète introuvable")
    participations = participation_repository.list_for_athlete(db, athlete_id)
    return {
        "athlete": AthleteBrief.model_validate(athlete),
        "participations": [ParticipationOut.model_validate(p) for p in participations],
    }
