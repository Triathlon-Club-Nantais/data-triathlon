"""
Service de persistance d'un résultat saisi à la main.

`save_public_entry` sert la saisie manuelle (`POST /participations`) : l'import
d'épreuve complète persiste par `import_service`, sans passer par lui.
"""
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.core.club import is_tcn
from app.core.exceptions import DomainError, DuplicateError
from app.core.youth import is_youth
from app.models.course import Course
from app.repositories import participation_repository
from app.schemas.participation import ParticipationOut
from app.scrapers.base import ScrapedResult
from app.services import mapping, opposition_service

logger = logging.getLogger(__name__)


class YouthResultError(DomainError):
    status_code = 422
    message = (
        "Les résultats des catégories jeunes (jusqu'à Minime) ne sont pas enregistrés, "
        "sauf pour un membre du club."
    )


def ensure_not_youth(
    event_name: str | None, event_date: date | None, category: str | None, club: str | None
) -> None:
    """Refuse une ligne saisie ou corrigée à la main que l'import écarterait (#1280).

    Règle de l'import (#881) et son exception TCN (#1221) : une ligne seule est
    son propre heat, gardé s'il porte un TCN.
    """
    event_year = event_date.year if event_date else None
    if is_youth(event_name, category, event_year=event_year) and not is_tcn(club):
        raise YouthResultError()


def ensure_rename_keeps_rows_adult(db: Session, course: Course, new_name: str) -> None:
    """Refuse le renommage bénévole qui rend jeune une ligne non TCN (#1287).

    Seul compte ce que le renommage change : une ligne non TCN déjà jeune sous
    l'ancien nom (par sa catégorie, dans un heat gardé pour son jeune TCN,
    #1221, ou parce que l'épreuve s'appelait déjà jeune) ne bloque pas une
    correction de libellé. Toutes les lignes comptent, quel que soit leur statut.
    """
    event_year = course.event_date.year if course.event_date else None
    for category, club in participation_repository.categories_and_clubs_for_course(db, course.id):
        if (
            not is_tcn(club)
            and is_youth(new_name, category, event_year=event_year)
            and not is_youth(course.name, category, event_year=event_year)
        ):
            raise YouthResultError()


def save_public_entry(db: Session, scraped: ScrapedResult) -> ParticipationOut:
    """Saisie publique (`POST /participations`) : une identité opposée passe par les mêmes
    contrôles et reçoit la même réponse qu'une autre, puis rien n'est gardé (#1514).

    Un refus distinct dirait à n'importe qui qu'une personne s'est opposée. Pour la
    même raison, un dossard déjà pris par une saisie en attente ne rend pas `409` :
    renvoyer la même saisie trahirait qu'elle a été gardée (#1519). La seconde
    reçoit la réponse d'une saisie acceptée, et rien n'est gardé. Deux saisies
    simultanées franchissent la lecture : la contrainte les départage, sans 500.
    """
    opposed = opposition_service.names_opposed(
        db, scraped.athlete_name, scraped.athlete_firstname, scraped.team_name
    )
    ensure_not_youth(scraped.event_name, scraped.event_date, scraped.category, scraped.club)
    course = mapping.get_or_create_course(db, scraped, "").course
    holder = participation_repository.get_by_bib(db, course.id, scraped.bib_number) if scraped.bib_number else None
    if holder is not None and not holder.is_pending_validation:
        raise DuplicateError(
            f"Ce résultat existe déjà (dossard {scraped.bib_number} — "
            f"{scraped.event_name} / {scraped.event_type})."
        )
    athlete = mapping.get_or_create_athlete(db, scraped, event_date=course.event_date)
    fields = mapping.participation_fields(scraped, athlete_id=athlete.id, course_id=course.id)
    # shortcut: the answer only feeds tests/conftest.py::save_entry; once epic #1704 frees conftest, return None and drop the bib-less insert and the bib_number patch.
    participation = None if holder else participation_repository.create_unless_bib_taken(db, **fields)
    taken = participation is None
    if taken:
        # Sans dossard le temps d'écrire la réponse : il heurterait `uq_participation_bib`.
        participation = participation_repository.create(db, **fields | {"bib_number": None})
    answer = ParticipationOut.model_validate(participation_repository.get(db, participation.id))
    answer.bib_number = fields["bib_number"]
    if opposed or taken:
        db.rollback()
    else:
        db.commit()
    return answer
