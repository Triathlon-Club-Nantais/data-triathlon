"""Verrou d'épreuve des gestes d'administration (#982).

Partagé par tout geste qui écrit ce qu'un import ou un re-scrape écrit aussi :
re-scrape, bascule et suppression de source, suppression, correction et fusion
d'épreuve, gestes sur un résultat, et les purges `wipe_*`. L'avis humain de
fiabilité (`course_review.set_override`) n'en a pas besoin : l'import n'écrit
jamais `reliability_override`, les deux chemins ne se croisent pas (FR-037).

Il remplace un `dict` en mémoire d'un seul process, qui ne voyait ni la CLI
`rescrape-db`, ni les imports publics, ni un second worker.
C'est un verrou consultatif PostgreSQL de **transaction**
(`repositories/lock_repository`) : relâché au `commit`/`rollback`, donc jamais
oublié par un geste qui lève. Sans effet sous SQLite.
"""
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.repositories import lock_repository


class CourseRescrapeAlreadyRunningError(DomainError):
    """Une autre opération écrit déjà cette épreuve (FR-007, #118 ; partagé avec
    la bascule de source depuis #624, et avec tout geste d'écriture depuis #982)."""

    status_code = 409
    message = "Une opération de scraping est déjà en cours sur cette épreuve."


def lock_courses_or_409(db: Session, *course_ids: int) -> None:
    """Verrouille ces épreuves pour la transaction en cours, ou 409.

    Dans l'ordre de leurs ids : deux fusions croisées ne s'attendent pas l'une
    l'autre.
    """
    for course_id in sorted(set(course_ids)):
        if not lock_repository.try_lock_course(db, course_id):
            raise CourseRescrapeAlreadyRunningError()


def lock_all_courses_or_409(db: Session) -> None:
    """Verrouille toutes les épreuves (purges `wipe_*`), ou 409."""
    if not lock_repository.try_lock_all_courses(db):
        raise CourseRescrapeAlreadyRunningError()
