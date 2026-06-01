from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from scrapers import scrape as do_scrape, ScrapedResult, detect_provider

router = APIRouter()


class ScrapeRequest(BaseModel):
    url: str


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


@router.post("/scrape", response_model=ScrapeResponse)
def scrape_url(body: ScrapeRequest):
    url = str(body.url).strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL invalide")

    try:
        result: ScrapedResult = do_scrape(url)
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


@router.get("/scrape/detect")
def detect(url: str):
    return {"provider": detect_provider(url)}
