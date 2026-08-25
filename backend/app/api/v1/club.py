"""Router Club : synthèse agrégée (roster + podiums) de la page /club (#581)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.club import ClubSummary
from app.services import club_service

router = APIRouter(tags=["club"])


@router.get("/club/summary", response_model=ClubSummary)
def get_club_summary(
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    db: Session = Depends(get_db),
):
    """Roster (top 12) et podiums (4 modes de rang) du club, agrégés côté serveur."""
    return club_service.get_club_summary(db, federal_only=federal_only)
