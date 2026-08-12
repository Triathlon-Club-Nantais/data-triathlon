"""Router Courses : liste, détail paginé avec participants, épreuves agrégées."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from app.core.club import is_club_scope
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.season import parse_date as _parse_date
from app.core.season import parse_seasons
from app.repositories import (
    course_repository,
    course_source_repository,
    participation_repository,
)
from app.schemas.course import (
    CourseBrief,
    CourseCount,
    CourseSourceOut,
    CourseSummary,
    EventPage,
)
from app.schemas.participation import CourseParticipationPage, ParticipationOut
from app.services import stats_service

router = APIRouter(tags=["courses"])


@router.get("/courses/events", response_model=EventPage)
def list_events(
    name: str | None = Query(None),
    event_type: str | None = Query(None),
    event_name: str | None = Query(None),
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    seasons: str | None = Query(None),
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    sort: str = Query("date_desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Page d'épreuves distinctes (scroll infini) avec compteurs participants + TCN."""
    return stats_service.list_events(
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club_only=is_club_scope(scope),
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
        seasons=parse_seasons(seasons),
        federal_only=federal_only,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/courses", response_model=list[CourseBrief])
def list_courses(
    name: str | None = Query(None, description="Recherche partielle sur le nom de l'épreuve."),
    event_type: str | None = Query(None),
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return course_repository.list_all(
        db,
        name=name,
        event_type=event_type,
        club_only=is_club_scope(scope),
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
        page=page,
        page_size=page_size,
    )


@router.get("/courses/count", response_model=CourseCount)
def count_courses(
    name: str | None = Query(None, description="Recherche partielle sur le nom de l'épreuve."),
    event_type: str | None = Query(None),
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Combien d'épreuves `GET /courses` rendrait aux mêmes filtres.

    Une route à part plutôt qu'un `total` ajouté à `GET /courses` : cette
    dernière rend une **liste**, l'envelopper serait un changement de contrat de
    v1 que le Principe IV réserve à une v2. Comptée séparément, la donnée est
    aussi mieux cachée côté front — elle ne dépend pas de `page`, donc feuilleter
    ne la recalcule pas.
    """
    return CourseCount(
        total=course_repository.count_all(
            db,
            name=name,
            event_type=event_type,
            club_only=is_club_scope(scope),
            date_from=_parse_date(date_from),
            date_to=_parse_date(date_to),
        )
    )


#: Plafond de la taille de tranche demandable, aligné sur `/courses/events`.
_MAX_PAGE_SIZE = 200

#: Valeur de `page_size` demandant le classement entier en une page.
_PAGE_SIZE_ALL = "all"


def _resolve_page_size(page_size: int | Literal["all"]) -> int | None:
    """Traduit `page_size` en taille de tranche, `None` valant « pas de découpage ».

    Le plafond ne peut pas être porté par `Query(ge=…, le=…)` : le paramètre est
    une union, et les bornes ne s'appliqueraient pas à la branche littérale.
    """
    if page_size == _PAGE_SIZE_ALL:
        return None
    if not 1 <= page_size <= _MAX_PAGE_SIZE:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "page_size"),
                    "msg": (
                        f"page_size doit être compris entre 1 et {_MAX_PAGE_SIZE}, "
                        f"ou valoir « {_PAGE_SIZE_ALL} »."
                    ),
                    "input": page_size,
                }
            ]
        )
    return page_size


@router.get("/courses/{course_id}/summary", response_model=CourseSummary)
def get_course_summary(course_id: int, db: Session = Depends(get_db)):
    """Synthèse d'une épreuve **entière** (#163).

    N'accepte aucun paramètre, et c'est structurant : les agrégats ne dépendent
    ni de la recherche ni de la portée club en cours, sans quoi chercher un nom
    ferait tomber l'histogramme à une barre.
    """
    if not course_repository.get(db, course_id):
        raise NotFoundError("Course introuvable")
    return stats_service.course_summary(db, course_id)


@router.get("/courses/{course_id}/sources", response_model=list[CourseSourceOut])
def list_course_sources(course_id: int, db: Session = Depends(get_db)):
    """Les sources de chronométrage de l'épreuve, **non authentifié** (#284, D4).

    Ouverte comme le reste de l'API de lecture : savoir qu'une épreuve a deux
    chronométreurs et laquelle des deux alimente le classement affiché est une
    information de lecture, pas d'exploitation. Ce qui reste fermé, c'est
    l'écriture (soumettre, basculer l'active) et le nom du soumetteur, absent du
    schéma.

    **Le 404 précède la liste vide**, et les deux sont distincts : une épreuve
    inconnue est une erreur d'adresse, une épreuve sans source est une réponse
    valide (`[]`) — c'est l'état d'une épreuve saisie à la main. D'où la lecture
    préalable de l'épreuve, sur le patron des deux routes voisines ; sans elle,
    un identifiant inventé rendrait `[]` et se lirait comme « aucune source ».
    """
    if not course_repository.get(db, course_id):
        raise NotFoundError("Course introuvable")
    return course_source_repository.list_for_course(db, course_id)


@router.get("/courses/{course_id}", response_model=CourseParticipationPage)
def get_course(
    course_id: int,
    page: int = Query(1, ge=1),
    page_size: int | Literal["all"] = Query(
        20, description="Taille de tranche, ou « all » pour le classement entier."
    ),
    q: str | None = Query(None, description="Recherche sur le nom ou le prénom de l'athlète."),
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    db: Session = Depends(get_db),
):
    """Classement d'une épreuve, **paginé par défaut**.

    C'est un changement de comportement de cette route, assumé (#163) : elle
    rendait l'intégralité des participations, soit plus de 2500 lignes sur les
    grosses épreuves. `page_size=all` laisse ce comportement atteignable à qui
    le demande explicitement.
    """
    course = course_repository.get(db, course_id)
    if not course:
        raise NotFoundError("Course introuvable")
    taille = _resolve_page_size(page_size)
    participations, total = participation_repository.list_page_for_course(
        db, course_id, page=page, page_size=taille, q=q, club_only=is_club_scope(scope)
    )
    return {
        "course": CourseBrief.model_validate(course),
        "participations": [ParticipationOut.model_validate(p) for p in participations],
        "total": total,
        "page": page,
        "page_size": taille,
    }
