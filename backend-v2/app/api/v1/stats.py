"""Router Stats : agrégations club et géolocalisation des épreuves."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import participation_repository
from app.services import geocode_service, stats_service

router = APIRouter(tags=["stats"])


@router.get("/stats")
def get_stats(club: str | None = Query(None), db: Session = Depends(get_db)):
    return stats_service.get_stats(db, club)


@router.get("/stats/events-geo")
def get_events_geo(club: str | None = Query(None), db: Session = Depends(get_db)):
    """Épreuves géocodées (lat/lon) pour la carte. Géocodage caché en mémoire."""
    rows = participation_repository.events_with_counts(db, club=club)
    geo_events = []
    for r in rows:
        if not r.event_name:
            continue
        coord = geocode_service.geocode(r.event_name)
        if coord:
            geo_events.append({
                "event_name": r.event_name,
                "event_date": r.event_date.isoformat() if r.event_date else None,
                "event_type": r.event_type or "",
                "count": r.total,
                "tcn_count": int(r.tcn_count or 0),
                "lat": coord[0],
                "lon": coord[1],
            })
    return geo_events
