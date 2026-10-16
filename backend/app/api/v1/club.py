"""Router Club : synthèse agrégée (roster + podiums) de la page /club (#581)."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.repositories import athlete_repository
from app.schemas.club import ClubPodiums, ClubRosterRank, ClubSummary
from app.schemas.ids import DbId
from app.services import club_service

router = APIRouter(tags=["club"])


@router.get("/club/summary", response_model=ClubSummary)
def get_club_summary(
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    podiums: Literal["preview"] | None = Query(
        None,
        description="`preview` : seulement les 6 premiers podiums de chaque mode, la liste complète "
        "étant servie par `/club/podiums` ; `podiums_totals` donne les tailles complètes.",
    ),
    db: Session = Depends(get_db),
):
    """Roster (top 12) et podiums (4 modes de rang) du club, agrégés côté serveur."""
    return club_service.get_club_summary(db, federal_only=federal_only, podiums_preview=podiums == "preview")


@router.get("/club/podiums", response_model=ClubPodiums)
def get_club_podiums(
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    db: Session = Depends(get_db),
):
    """Tous les podiums du club, par mode de rang : la liste dépliée de /club (#1354)."""
    return club_service.get_club_podiums(db, federal_only=federal_only)


@router.get("/club/roster/rank/{athlete_id}", response_model=ClubRosterRank)
def get_club_roster_rank(
    athlete_id: DbId,
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    db: Session = Depends(get_db),
):
    """Rang exact de l'athlète dans le roster club, au-delà de l'aperçu de 12 (#504, #641)."""
    result = athlete_repository.club_rank(db, athlete_id, federal_only=federal_only)
    if result is None:
        raise NotFoundError("Athlète hors du roster club")
    rank, total = result
    return ClubRosterRank(rank=rank, total=total)
