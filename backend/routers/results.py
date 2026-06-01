from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Result

router = APIRouter()


class ResultCreate(BaseModel):
    source_url: str
    provider: str
    athlete_name: str = ""
    athlete_firstname: str = ""
    club: str = ""
    category: str = ""
    gender: str = ""
    bib_number: str = ""
    event_name: str = ""
    event_date: Optional[str] = None
    event_type: str = ""
    rank_overall: Optional[int] = None
    rank_category: Optional[int] = None
    rank_gender: Optional[int] = None
    total_time: str = ""
    swim_time: str = ""
    t1_time: str = ""
    bike_time: str = ""
    t2_time: str = ""
    run_time: str = ""
    raw_data: dict = {}


class ResultOut(ResultCreate):
    id: int
    scraped_at: Optional[str] = None

    class Config:
        from_attributes = True


@router.post("/results", response_model=ResultOut, status_code=201)
def create_result(body: ResultCreate, db: Session = Depends(get_db)):
    event_date = None
    if body.event_date:
        try:
            event_date = date.fromisoformat(body.event_date)
        except ValueError:
            pass

    result = Result(
        source_url=body.source_url,
        provider=body.provider,
        athlete_name=body.athlete_name,
        athlete_firstname=body.athlete_firstname,
        club=body.club,
        category=body.category,
        gender=body.gender,
        bib_number=body.bib_number,
        event_name=body.event_name,
        event_date=event_date,
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
        raw_data=body.raw_data,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return _serialize(result)


@router.get("/results", response_model=list[ResultOut])
def list_results(
    name: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    event_name: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(Result)
    if name:
        pattern = f"%{name}%"
        q = q.filter(
            Result.athlete_name.ilike(pattern) | Result.athlete_firstname.ilike(pattern)
        )
    if event_type:
        q = q.filter(Result.event_type == event_type)
    if event_name:
        q = q.filter(Result.event_name.ilike(f"%{event_name}%"))
    if date_from:
        try:
            q = q.filter(Result.event_date >= date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(Result.event_date <= date.fromisoformat(date_to))
        except ValueError:
            pass

    offset = (page - 1) * page_size
    rows = q.order_by(Result.scraped_at.desc()).offset(offset).limit(page_size).all()
    return [_serialize(r) for r in rows]


@router.get("/results/{result_id}", response_model=ResultOut)
def get_result(result_id: int, db: Session = Depends(get_db)):
    row = db.get(Result, result_id)
    if not row:
        raise HTTPException(status_code=404, detail="Résultat introuvable")
    return _serialize(row)


@router.delete("/results/{result_id}", status_code=204)
def delete_result(result_id: int, db: Session = Depends(get_db)):
    row = db.get(Result, result_id)
    if not row:
        raise HTTPException(status_code=404, detail="Résultat introuvable")
    db.delete(row)
    db.commit()


def _serialize(r: Result) -> dict:
    return {
        "id": r.id,
        "source_url": r.source_url or "",
        "provider": r.provider or "",
        "athlete_name": r.athlete_name or "",
        "athlete_firstname": r.athlete_firstname or "",
        "club": r.club or "",
        "category": r.category or "",
        "gender": r.gender or "",
        "bib_number": r.bib_number or "",
        "event_name": r.event_name or "",
        "event_date": r.event_date.isoformat() if r.event_date else None,
        "event_type": r.event_type or "",
        "rank_overall": r.rank_overall,
        "rank_category": r.rank_category,
        "rank_gender": r.rank_gender,
        "total_time": r.total_time or "",
        "swim_time": r.swim_time or "",
        "t1_time": r.t1_time or "",
        "bike_time": r.bike_time or "",
        "t2_time": r.t2_time or "",
        "run_time": r.run_time or "",
        "raw_data": r.raw_data or {},
        "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None,
    }
