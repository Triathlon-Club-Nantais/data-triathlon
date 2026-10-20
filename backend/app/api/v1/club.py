"""Router Club : synthèse agrégée (roster + podiums) de la page /club (#581)."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.season import SEASON_MAX, SEASON_MIN, parse_seasons
from app.repositories import athlete_repository
from app.schemas.club import (
    ClubBestTime,
    ClubLastOuting,
    ClubPodiums,
    ClubRosterRank,
    ClubSplitMedians,
    ClubSummary,
)
from app.schemas.ids import DbId
from app.services import club_service, stats_service

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
    seasons: str | None = Query(None, description="Saisons (années de début, CSV) ; absentes, toutes saisons."),
    gender: Literal["M", "F"] | None = Query(
        None, description="Sexe de l'athlète ; absent, les deux sexes (et les athlètes sans sexe connu)."
    ),
    db: Session = Depends(get_db),
):
    """Roster (top 12) et podiums (4 modes de rang) du club, agrégés côté serveur."""
    return club_service.get_club_summary(
        db, federal_only=federal_only, podiums_preview=podiums == "preview",
        seasons=parse_seasons(seasons), gender=gender,
    )


@router.get("/club/podiums", response_model=ClubPodiums)
def get_club_podiums(
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    seasons: str | None = Query(None, description="Saisons (années de début, CSV) ; absentes, toutes saisons."),
    gender: Literal["M", "F"] | None = Query(
        None, description="Sexe de l'athlète ; absent, les deux sexes (et les athlètes sans sexe connu)."
    ),
    db: Session = Depends(get_db),
):
    """Tous les podiums du club, par mode de rang : la liste dépliée de /club (#1354)."""
    return club_service.get_club_podiums(
        db, federal_only=federal_only, seasons=parse_seasons(seasons), gender=gender
    )


@router.get("/club/best-times", response_model=list[ClubBestTime])
def get_club_best_times(
    season: int | None = Query(
        None,
        ge=SEASON_MIN,
        le=SEASON_MAX,
        description="Année de début de la saison (bascule au 1er septembre) ; absente, toutes saisons.",
    ),
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    db: Session = Depends(get_db),
):
    """Meilleur temps du club par format calibré (XS à XL) et par genre (#1588)."""
    return club_service.get_club_best_times(db, season=season, federal_only=federal_only)


@router.get("/club/last-outing", response_model=ClubLastOuting | None)
def get_club_last_outing(
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    seasons: str | None = Query(None, description="Saisons (années de début, CSV) ; absentes, la saison en cours."),
    db: Session = Depends(get_db),
):
    """Dernière sortie du club dans les saisons demandées (la courante par défaut), `null` sans course TCN (#1619)."""
    return stats_service.get_last_outing(db, federal_only=federal_only, seasons=parse_seasons(seasons))


@router.get("/club/roster/rank/{athlete_id}", response_model=ClubRosterRank)
def get_club_roster_rank(
    athlete_id: DbId,
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    seasons: str | None = Query(None, description="Saisons (années de début, CSV) ; absentes, toutes saisons."),
    gender: Literal["M", "F"] | None = Query(
        None, description="Sexe de l'athlète ; absent, classement sur les deux sexes."
    ),
    db: Session = Depends(get_db),
):
    """Rang exact de l'athlète dans le roster club, au-delà de l'aperçu de 12 (#504, #641)."""
    result = athlete_repository.club_rank(
        db, athlete_id, federal_only=federal_only, seasons=parse_seasons(seasons), gender=gender
    )
    if result is None:
        raise NotFoundError("Athlète hors du roster club")
    rank, total = result
    return ClubRosterRank(rank=rank, total=total)


@router.get("/club/split-medians", response_model=ClubSplitMedians)
def get_club_split_medians(
    event_type: str = Query(..., description="Format (`triathlon-m`, `duathlon-s`…) dont on veut la médiane des splits."),
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    seasons: str | None = Query(None, description="Saisons (années de début, CSV) ; absentes, toutes saisons."),
    db: Session = Depends(get_db),
):
    """Médiane club de la natation, du vélo et de la course d'un format, splits fiables seuls (#1699)."""
    return club_service.get_club_split_medians(
        db, event_type=event_type, federal_only=federal_only, seasons=parse_seasons(seasons)
    )
