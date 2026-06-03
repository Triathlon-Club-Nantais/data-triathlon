from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Result
from scrapers import scrape as do_scrape, scrape_event_all as do_scrape_event_all, ScrapedResult, detect_provider
from scrapers.base import MultipleMatchesError

router = APIRouter()


class ScrapeRequest(BaseModel):
    url: str
    bib: str | None = None


class ScrapeResponse(BaseModel):
    provider: str
    source_url: str
    athlete_name: str
    athlete_firstname: str
    club: str
    category: str
    gender: str
    bib_number: str
    event_name: str
    event_date: str | None
    event_type: str
    rank_overall: int | None
    rank_category: int | None
    rank_gender: int | None
    total_time: str
    swim_time: str
    t1_time: str
    bike_time: str
    t2_time: str
    run_time: str
    raw_data: dict


@router.post("/scrape")
def scrape_url(body: ScrapeRequest):
    url = str(body.url).strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL invalide")

    try:
        result: ScrapedResult = do_scrape(url, bib=body.bib)
    except MultipleMatchesError as exc:
        return {"multiple_matches": True, "candidates": exc.candidates}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Erreur lors du scraping : {exc}")

    return ScrapeResponse(
        provider=result.provider,
        source_url=result.source_url,
        athlete_name=result.athlete_name,
        athlete_firstname=result.athlete_firstname,
        club=result.club,
        category=result.category,
        gender=result.gender,
        bib_number=result.bib_number,
        event_name=result.event_name,
        event_date=result.event_date.isoformat() if result.event_date else None,
        event_type=result.event_type,
        rank_overall=result.rank_overall,
        rank_category=result.rank_category,
        rank_gender=result.rank_gender,
        total_time=result.total_time,
        swim_time=result.swim_time,
        t1_time=result.t1_time,
        bike_time=result.bike_time,
        t2_time=result.t2_time,
        run_time=result.run_time,
        raw_data=result.raw_data,
    )


@router.post("/scrape/event")
def scrape_event(body: ScrapeRequest, db: Session = Depends(get_db)):
    """Import all participants from an event into the database."""
    url = str(body.url).strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL invalide")

    try:
        all_results = do_scrape_event_all(url)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Erreur lors de l'import : {exc}")

    if not all_results:
        return {"imported": 0, "skipped": 0}

    event_name = all_results[0].event_name

    # Single DB query to collect already-existing bibs for this event
    existing_bibs: set[str] = {
        row[0]
        for row in db.query(Result.bib_number)
        .filter(Result.event_name == event_name, Result.bib_number.isnot(None))
        .all()
    }

    imported = skipped = 0
    for r in all_results:
        if r.bib_number in existing_bibs:
            skipped += 1
            continue
        db.add(Result(
            source_url=r.source_url,
            provider=r.provider,
            athlete_name=r.athlete_name,
            athlete_firstname=r.athlete_firstname,
            club=r.club,
            category=r.category,
            gender=r.gender,
            bib_number=r.bib_number,
            event_name=r.event_name,
            event_date=r.event_date,
            event_type=r.event_type,
            rank_overall=r.rank_overall,
            rank_category=r.rank_category,
            rank_gender=r.rank_gender,
            total_time=r.total_time,
            swim_time=r.swim_time,
            t1_time=r.t1_time,
            bike_time=r.bike_time,
            t2_time=r.t2_time,
            run_time=r.run_time,
            is_relay=r.is_relay,
            raw_data=r.raw_data,
        ))
        existing_bibs.add(r.bib_number)
        imported += 1

    db.commit()
    return {"imported": imported, "skipped": skipped}


@router.get("/scrape/detect")
def detect(url: str):
    return {"provider": detect_provider(url)}
