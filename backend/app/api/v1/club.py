"""Router Club : synthèse agrégée (roster + podiums) de la page /club (#581)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.repositories import athlete_repository
from app.schemas.club import ClubRosterRank, ClubSummary
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


@router.get("/club/roster/rank/{athlete_id}", response_model=ClubRosterRank)
def get_club_roster_rank(
    athlete_id: int,
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    db: Session = Depends(get_db),
):
    """Rang exact de l'athlète dans le roster club, au-delà de l'aperçu de 12 (#504, #641)."""
    resultat = athlete_repository.club_rank(db, athlete_id, federal_only=federal_only)
    if resultat is None:
        raise NotFoundError("Athlète hors du roster club")
    rank, total = resultat
    return ClubRosterRank(rank=rank, total=total)
