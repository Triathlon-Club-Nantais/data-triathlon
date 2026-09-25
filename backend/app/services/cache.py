"""
Cache TTL dynamique (PRD F1).

Une course « en cours » (au moins un finisher sans temps final) est re-scrapée
fréquemment ; une course « terminée » est considérée stable longtemps.

**La fraîcheur est celle de l'épreuve, pas d'une URL** (#281). Depuis que N
sources peuvent désigner la même épreuve, la question se pose : une URL passive
porte-t-elle un cache ? Non. Le TTL protège du re-scraping inutile de ce qu'on
**affiche**, et une passive n'alimente aucun affichage — elle n'est même jamais
scrapée (#282). Son `last_scraped_at` n'entre donc pas dans le calcul : la
fraîcheur se lit sur `Course.scraped_at`, alimenté par le seul scraping qui ait
lieu, celui de l'active.

Conséquence côté recherche, et c'est le sens du filtre `is_active` des trois
recherches par URL de `course_repository` : coller la seconde publication d'une
épreuve fraîche ne trouve rien en cache, donc ne renvoie pas le classement de
l'**autre** chronométreur sous l'URL qu'on vient de coller.
"""
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.time import utcnow
from app.models.course import Course
from app.repositories import participation_repository
from app.services.quality import _ZERO_TIMES

#: Jours après l'épreuve pendant lesquels un non-finisher sans temps la dit
#: encore en cours (#913) : un coureur pas encore arrivé, publié sans statut ni
#: temps, est rangé DNF par `mapping.derive_status`.
_RECENT_RACE_DAYS = 1


def is_in_progress(db: Session, course: Course) -> bool:
    """Vrai si au moins une participation n'a pas de temps final (course en cours).

    Un temps « zéro » (`00:00:00`, `0:00`…) vaut temps absent — même définition
    que `quality._ZERO_TIMES`, réutilisée ici plutôt que dupliquée : un
    chronométreur qui publie ce placeholder en attendant les temps réels ne doit
    pas faire passer l'épreuve au TTL long (#566).

    Seul un **finisher** sans temps compte (#913) : un DNF, DNS ou DSQ n'a
    jamais de temps final, et le compter figeait au TTL court toute épreuve
    terminée qui en portait un. Exception bornée : le jour de l'épreuve et le
    lendemain (ou sans date connue), tout résultat sans temps compte encore,
    puisqu'un coureur en course sans statut publié est persisté en DNF.
    """
    recent = course.event_date is None or course.event_date >= utcnow().date() - timedelta(
        days=_RECENT_RACE_DAYS
    )
    return participation_repository.has_untimed(
        db, course.id, placeholder_times=_ZERO_TIMES, finishers_only=not recent
    )


def ttl_seconds(db: Session, course: Course, settings: Settings) -> int:
    if is_in_progress(db, course):
        return settings.cache_ttl_in_progress_seconds
    return settings.cache_ttl_finished_seconds


def is_fresh(db: Session, course: Course, settings: Settings) -> bool:
    """Vrai si la course a été scrapée plus récemment que son TTL."""
    if course.scraped_at is None:
        return False
    age = (utcnow() - course.scraped_at).total_seconds()
    return age < ttl_seconds(db, course, settings)
