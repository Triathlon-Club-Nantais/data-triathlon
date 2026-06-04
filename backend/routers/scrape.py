import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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


@router.post("/scrape/event/stream")
async def scrape_event_stream(body: ScrapeRequest, db: Session = Depends(get_db)):
    """Import all participants with real-time SSE progress updates."""
    url = str(body.url).strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL invalide")

    def _sse(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    async def generate():
        # Phase 1 — scraping (blocking → run in thread)
        yield _sse({"phase": "scraping", "message": "Récupération des participants…"})
        try:
            loop = asyncio.get_event_loop()
            all_results = await loop.run_in_executor(None, do_scrape_event_all, url)
        except Exception as exc:
            yield _sse({"phase": "error", "message": str(exc)})
            return

        total = len(all_results)
        if total == 0:
            yield _sse({"phase": "done", "imported": 0, "skipped": 0, "total": 0})
            return

        event_name = all_results[0].event_name
        existing_bibs: set[str] = {
            row[0]
            for row in db.query(Result.bib_number)
            .filter(Result.event_name == event_name, Result.bib_number.isnot(None))
            .all()
        }

        yield _sse({"phase": "saving", "total": total, "imported": 0, "skipped": 0, "progress": 0})

        # Phase 2 — insert with progress
        imported = skipped = 0
        for i, r in enumerate(all_results):
            if r.bib_number in existing_bibs:
                skipped += 1
            else:
                db.add(Result(
                    source_url=r.source_url, provider=r.provider,
                    athlete_name=r.athlete_name, athlete_firstname=r.athlete_firstname,
                    club=r.club, category=r.category, gender=r.gender,
                    bib_number=r.bib_number, event_name=r.event_name,
                    event_date=r.event_date, event_type=r.event_type,
                    rank_overall=r.rank_overall, rank_category=r.rank_category,
                    rank_gender=r.rank_gender, total_time=r.total_time,
                    swim_time=r.swim_time, t1_time=r.t1_time, bike_time=r.bike_time,
                    t2_time=r.t2_time, run_time=r.run_time,
                    is_relay=r.is_relay, raw_data=r.raw_data,
                ))
                existing_bibs.add(r.bib_number)
                imported += 1

            if (i + 1) % 20 == 0 or i == total - 1:
                yield _sse({"phase": "saving", "total": total, "imported": imported,
                            "skipped": skipped, "progress": i + 1})

        db.commit()
        yield _sse({"phase": "done", "imported": imported, "skipped": skipped, "total": total})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/scrape/detect")
def detect(url: str):
    return {"provider": detect_provider(url)}
