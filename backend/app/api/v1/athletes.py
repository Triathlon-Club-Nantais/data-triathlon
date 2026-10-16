"""Router Athletes : recherche et fiche athlète avec ses participations."""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import MAX_PAGE, require_permission
from app.core.club import is_club_scope
from app.core.database import get_db
from app.core.permissions import P
from app.core.season import parse_seasons, season_quota_met
from app.models.user import User
from app.repositories import (
    athlete_repository,
    participation_repository,
    season_validation_repository,
    volunteer_action_repository,
)
from app.schemas.athlete import AthleteBrief, AthleteSearchResult, AthleteSeasonActivity
from app.schemas.ids import DbId
from app.schemas.participation import AthleteDetail, AthleteParticipationOut
from app.services import athlete_csv, challenge_service, not_found

router = APIRouter(tags=["athletes"])


@router.get("/athletes", response_model=list[AthleteBrief])
def list_athletes(
    name: str | None = Query(None),
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    page: int = Query(1, ge=1, le=MAX_PAGE),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return athlete_repository.search(
        db, name=name, club_only=is_club_scope(scope), page=page, page_size=page_size
    )


# Déclarée avant `/athletes/{athlete_id}` : sinon FastAPI matche "season-activity"
# comme un `athlete_id` (int) et rend 422 au lieu de résoudre cette route (#274).
@router.get("/athletes/season-activity", response_model=list[AthleteSeasonActivity])
def list_athletes_season_activity(
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    seasons: str | None = Query(None),
    federal_only: bool = Query(False, description="Retire trail, course à pied et cyclisme."),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.PAGES_PREVIEW)),
):
    """Athlètes ayant ≥1 participation sur `seasons`, avec leurs compteurs (#274, #382, #709)."""
    parsed_seasons = parse_seasons(seasons)
    rows = athlete_repository.list_with_season_participation_count(
        db,
        seasons=parsed_seasons,
        club_only=is_club_scope(scope),
        federal_only=federal_only,
    )
    # Le statut de validation est mono-saison (research.md D9) : `null` dès que
    # `seasons` n'en désigne pas exactement une, sinon la carte des validés.
    # Le quota (#1542) suit la même règle.
    single_season = len(parsed_seasons) == 1
    validations: dict[int, bool] = {}
    volunteers: set[int] = set()
    if single_season:
        athlete_ids = [a.id for a, *_ in rows]
        validations = season_validation_repository.map_by_athlete(
            db, athlete_ids=athlete_ids, season=parsed_seasons[0]
        )
        volunteers = volunteer_action_repository.athlete_ids_with_validated_action(
            db, athlete_ids=athlete_ids, season=parsed_seasons[0]
        )
    return [
        AthleteSeasonActivity(
            id=a.id,
            nom=a.nom,
            prenom=a.prenom,
            participation_count=club_affiliated,
            total_count=total,
            validated_count=validated,
            club_affiliated_count=club_affiliated,
            season_validated=validations.get(a.id, False) if single_season else None,
            quota_met=season_quota_met(federal_validated, a.id in volunteers) if single_season else None,
        )
        for a, total, validated, club_affiliated, federal_validated in rows
    ]


# Déclarée avant `/athletes/{athlete_id}`, même raison que
# `/athletes/season-activity` ci-dessus (#484).
@router.get("/athletes/search", response_model=list[AthleteSearchResult])
def search_athletes(
    q: str = Query(..., min_length=2),
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Recherche classée par pertinence pour la palette `⌘K` (#484, NAV-8).

    Distincte de `GET /athletes` : celle-ci trie par pertinence (préfixe
    exact, début de mot, sous-chaîne) puis volume, et rend le compte de
    participations — deux choses que `GET /athletes` ne fait pas et n'a pas à
    faire pour ses propres appelants.
    """
    rows = athlete_repository.search_by_relevance(
        db, term=q, club_only=is_club_scope(scope), limit=limit
    )
    return [
        AthleteSearchResult(
            **AthleteBrief.model_validate(athlete).model_dump(), participation_count=count
        )
        for athlete, count in rows
    ]


@router.get("/athletes/{athlete_id}", response_model=AthleteDetail)
def get_athlete(
    athlete_id: DbId,
    seasons: str | None = Query(None),
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    db: Session = Depends(get_db),
):
    """Fiche athlète et ses participations.

    Les deux filtres sont **optionnels et neutres par défaut** (#502) : sans
    eux, la route rend la carrière entière, comme depuis toujours. Ils servent
    la bande « Ma saison » du tableau de bord, qui doit compter sur la même
    base que les compteurs club affichés juste dessous — mêmes noms et mêmes
    sémantiques que sur `/stats` et `/athletes/season-activity`.
    """
    athlete = not_found.athlete_or_404(db, athlete_id, message="Athlète introuvable")
    participations = participation_repository.list_for_athlete(
        db, athlete_id, seasons=parse_seasons(seasons), federal_only=federal_only
    )
    counts = participation_repository.finishers_count_by_group(
        db, [p.course_id for p in participations]
    )
    items = []
    for p in participations:
        item = AthleteParticipationOut.model_validate(p)
        item.course_finishers = counts.get((p.course_id, bool(p.is_relay)))
        items.append(item)
    return {
        "athlete": AthleteBrief.model_validate(athlete),
        "participations": items,
        "challenges": challenge_service.for_athlete(db, athlete_id),
    }


@router.get(
    "/athletes/{athlete_id}/participations.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
def get_athlete_participations_csv(athlete_id: DbId, db: Session = Depends(get_db)):
    """Les résultats de la fiche athlète en CSV pour Excel (#1375) : mêmes lignes
    que `GET /athletes/{id}` sans filtre, en attente et refusées comprises."""
    athlete = not_found.athlete_or_404(db, athlete_id, message="Athlète introuvable")
    participations = participation_repository.list_for_athlete(db, athlete_id)
    finishers = participation_repository.finishers_count_by_group(
        db, [p.course_id for p in participations]
    )
    return Response(
        athlete_csv.render(participations, finishers),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{athlete_csv.filename(athlete)}"'},
    )
