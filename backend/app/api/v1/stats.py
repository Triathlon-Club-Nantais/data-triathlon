"""Router Stats : agrégations club, saisons disponibles et géolocalisation."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.club import is_club_scope
from app.core.database import get_db
from app.core.season import parse_seasons
from app.repositories import participation_repository
from app.schemas.season import SeasonOut
from app.services import geocode_service, stats_service

router = APIRouter(tags=["stats"])


@router.get("/stats")
def get_stats(
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    seasons: str | None = Query(None),
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    db: Session = Depends(get_db),
):
    """Stats agrégées du club, filtrables par saison(s) (CSV d'années)."""
    return stats_service.get_stats(
        db,
        club_only=is_club_scope(scope),
        seasons=parse_seasons(seasons),
        federal_only=federal_only,
    )


@router.get("/stats/seasons", response_model=list[SeasonOut])
def list_seasons(
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    db: Session = Depends(get_db),
):
    """Saisons disponibles pour le sélecteur (avec saison en cours forcée)."""
    return stats_service.list_seasons(db, club_only=is_club_scope(scope), federal_only=federal_only)


@router.get("/stats/events-geo")
def get_events_geo(
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    db: Session = Depends(get_db),
):
    """Épreuves géocodées (lat/lon) pour la carte. Géocodage caché en mémoire."""
    rows = participation_repository.events_with_counts(
        db, club_only=is_club_scope(scope), federal_only=federal_only
    )
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
