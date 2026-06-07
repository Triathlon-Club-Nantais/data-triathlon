"""Router Participations : création manuelle, liste filtrée, détail, suppression."""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.repositories import participation_repo
from app.schemas.participation import ParticipationCreate, ParticipationOut
from app.scrapers.base import ScrapedResult
from app.services import scrape_service

router = APIRouter(tags=["participations"])


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _to_scraped(body: ParticipationCreate) -> ScrapedResult:
    return ScrapedResult(
        source_url=body.source_url,
        provider=body.provider,
        athlete_name=body.athlete_name,
        athlete_firstname=body.athlete_firstname,
        club=body.club,
        category=body.category,
        gender=body.gender,
        bib_number=body.bib_number,
        event_name=body.event_name,
        event_date=_parse_date(body.event_date),
        event_type=body.event_type,
        rank_overall=body.rank_overall,
        rank_category=body.rank_category,
        rank_gender=body.rank_gender,
        total_time=body.total_time,
        swim_time=body.swim_time,
        t1_time=body.t1_time,
        bike_time=body.bike_time,
        t2_time=body.t2_time,
        run_time=body.run_time,
        is_relay=body.is_relay,
        raw_data=body.raw_data,
    )


@router.post("/participations", response_model=ParticipationOut, status_code=201)
def create_participation(body: ParticipationCreate, db: Session = Depends(get_db)):
    """Crée manuellement un résultat (athlète + course + participation)."""
    participation = scrape_service.save_one(db, _to_scraped(body))
    return participation_repo.get(db, participation.id)


@router.get("/participations", response_model=list[ParticipationOut])
def list_participations(
    name: str | None = Query(None),
    event_type: str | None = Query(None),
    event_name: str | None = Query(None),
    club: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    return participation_repo.list_participations(
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club=club,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
        page=page,
        page_size=page_size,
    )


@router.get("/participations/{participation_id}", response_model=ParticipationOut)
def get_participation(participation_id: int, db: Session = Depends(get_db)):
    row = participation_repo.get(db, participation_id)
    if not row:
        raise NotFoundError("Résultat introuvable")
    return row


@router.delete("/participations/{participation_id}", status_code=204)
def delete_participation(participation_id: int, db: Session = Depends(get_db)):
    row = participation_repo.get(db, participation_id)
    if not row:
        raise NotFoundError("Résultat introuvable")
    db.delete(row)
    db.commit()
