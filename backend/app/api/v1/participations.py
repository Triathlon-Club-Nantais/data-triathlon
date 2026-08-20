"""Router Participations : création manuelle, liste filtrée, détail, suppression."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import optional_user, public_write_rate_limit, require_permission
from app.core.analytics import ANONYMOUS_DISTINCT_ID, capture_event
from app.core.club import is_club_scope
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.permissions import P
from app.core.season import parse_date as _parse_date
from app.core.season import parse_seasons
from app.models.user import User
from app.repositories import participation_repository
from app.schemas.participation import ParticipationCreate, ParticipationOut
from app.scrapers.base import ScrapedResult
from app.services import admin_actions, participation_stats_service, scrape_service

router = APIRouter(tags=["participations"])


def _to_scraped(body: ParticipationCreate) -> ScrapedResult:
    return ScrapedResult(
        source_url=body.source_url,
        provider=body.provider,
        athlete_name=body.athlete_name,
        athlete_firstname=body.athlete_firstname,
        club=body.club,
        category=body.category,
        gender=body.gender,
        bib_number=body.bib_number,
        event_name=body.event_name,
        event_date=_parse_date(body.event_date),
        event_type=body.event_type,
        format_label=body.format_label,
        distance_km=body.distance_km,
        rank_overall=body.rank_overall,
        rank_category=body.rank_category,
        rank_gender=body.rank_gender,
        total_time=body.total_time,
        swim_time=body.swim_time,
        t1_time=body.t1_time,
        bike_time=body.bike_time,
        t2_time=body.t2_time,
        run_time=body.run_time,
        segments=body.segments,
        is_relay=body.is_relay,
        status=body.status,
        team_name=body.team_name,
        evidence_url=body.evidence_url,
        raw_data=body.raw_data,
        # Forcé, jamais lu depuis `body` : une saisie manuelle par ce point
        # d'entrée est toujours non vérifiée (FR-016). `ParticipationCreate`
        # ne porte délibérément pas ce champ en entrée.
        is_pending_validation=True,
    )


@router.post(
    "/participations",
    response_model=ParticipationOut,
    status_code=201,
    dependencies=[Depends(public_write_rate_limit)],
)
def create_participation(
    body: ParticipationCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(optional_user),
):
    """Crée un résultat (athlète + course + participation) — **ouverte au public** (#270).

    Fermée un temps par #115 (« n'importe qui pouvait injecter un résultat
    dans la base du club »), rouverte ici : c'est tout l'objet du formulaire
    de saisie manuelle, utilisable par un membre sans qu'il ait de compte.
    Ce qui protège désormais l'intégrité des données publiées n'est plus une
    session mais la mise en quarantaine du résultat créé
    (`is_pending_validation=True`, forcé ci-dessous) — invisible de tout
    agrégat public jusqu'à la validation d'un bénévole (#271). `DELETE`,
    destructif, reste gardé.
    """
    participation = scrape_service.save_one(db, _to_scraped(body))
    capture_event(
        "participation_created",
        distinct_id=str(user.id) if user else ANONYMOUS_DISTINCT_ID,
        properties={
            "event_type": body.event_type,
            "is_relay": body.is_relay,
        },
    )
    return participation_repository.get(db, participation.id)


@router.get("/participations", response_model=list[ParticipationOut])
def list_participations(
    name: str | None = Query(None),
    event_type: str | None = Query(None),
    event_name: str | None = Query(None),
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    seasons: str | None = Query(None),
    course_id: int | None = Query(None),
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    return participation_repository.list_participations(
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club_only=is_club_scope(scope),
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
        seasons=parse_seasons(seasons),
        course_id=course_id,
        federal_only=federal_only,
        page=page,
        page_size=page_size,
    )


@router.get("/participations/{participation_id}", response_model=ParticipationOut)
def get_participation(participation_id: int, db: Session = Depends(get_db)):
    row = participation_repository.get(db, participation_id)
    if not row:
        raise NotFoundError("Résultat introuvable")
    out = ParticipationOut.model_validate(row)
    out.stats = participation_stats_service.build(db, row)
    return out


@router.delete("/participations/{participation_id}", status_code=204)
def delete_participation(
    participation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.PARTICIPATIONS_DELETE)),
):
    """Supprime définitivement un résultat.

    **L'anomalie la plus nette de la base de code avant #115** : `db.delete()`
    puis `db.commit()`, sans aucune authentification. Un pouvoir distinct de
    l'écriture — créer et détruire ne sont pas le même geste.

    Depuis #439, le geste passe par le service et laisse une entrée au journal :
    c'est la seule trace qui survit à ce qu'elle décrit. Chemin, verbe et `204`
    sont inchangés — le contrat publié ne bouge pas (Principe IV).
    """
    admin_actions.delete_participation(db, participation_id=participation_id, user_id=user.id)
    db.commit()
    capture_event(
        "participation_deleted",
        distinct_id=str(user.id),
        properties={"participation_id": participation_id},
    )
