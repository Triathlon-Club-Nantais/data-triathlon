"""Un rescrape ne ressuscite pas une épreuve fusionnée dont l'URL est partagée (#983).

L'URL de l'absorbée repointée en passive ne suffit pas quand d'autres épreuves la
portent en active (manches Breizh Chrono, variantes wiclax/timepulse) : le cron
re-scrape l'URL pour elles, et la ligne de la manche absorbée, qui n'apparie plus
aucune épreuve par identité, la recréait sous un nouvel id.
"""
from datetime import date

from app.models.course import Course
from app.models.participation import Participation
from app.repositories import course_repository, user_repository
from app.scrapers.base import ScrapedResult
from app.services import course_merge, import_service

SHARED = "https://www.wiclax-results.com/mesquer-2026/resultats.clax"
OTHER = "https://www.klikego.com/resultats/triathlon-de-mesquer-2026/1706667557931-4"
JOUR = date(2026, 6, 14)


def _row(bib: str, event_name: str, url: str, provider: str, nom: str) -> ScrapedResult:
    return ScrapedResult(
        source_url=url, provider=provider, athlete_name=nom, athlete_firstname="Jean",
        bib_number=bib, event_name=event_name, event_date=JOUR, event_type="triathlon-s",
        total_time="01:10:00",
    )


def _shared_url_scrape() -> list[ScrapedResult]:
    return [
        _row("7", "Tri Mesquer S vague 1", SHARED, "wiclax", "VAGUEUN"),
        _row("2", "Tri Mesquer S vague 2", SHARED, "wiclax", "VAGUEDEUX"),
    ]


def _names(db_session) -> list[str]:
    return sorted(c.name for c in db_session.query(Course).all())


def _setup(db_session):
    import_service.persist_results(db_session, SHARED, _shared_url_scrape())
    import_service.persist_results(
        db_session, OTHER, [_row("1", "Triathlon de Mesquer S", OTHER, "klikego", "CIBLE")]
    )
    db_session.flush()
    vague1 = course_repository.get_by_identity(
        db_session, "Tri Mesquer S vague 1", JOUR, "triathlon-s", False
    )
    target = course_repository.get_by_identity(
        db_session, "Triathlon de Mesquer S", JOUR, "triathlon-s", False
    )
    user = user_repository.create(db_session, email="admin@exemple.fr", display_name="admin")
    db_session.flush()
    return vague1, target, user


def test_a_rescrape_of_the_shared_url_does_not_recreate_the_absorbed_course(db_session):
    vague1, target, user = _setup(db_session)

    course_merge.merge_courses(db_session, course_id=target.id, absorbed_id=vague1.id, user_id=user.id)
    import_service.persist_results(db_session, SHARED, _shared_url_scrape())

    assert _names(db_session) == ["Tri Mesquer S vague 2", "Triathlon de Mesquer S"]


def test_the_absorbed_rows_are_redirected_to_the_target(db_session):
    vague1, target, user = _setup(db_session)

    course_merge.merge_courses(db_session, course_id=target.id, absorbed_id=vague1.id, user_id=user.id)
    import_service.persist_results(db_session, SHARED, _shared_url_scrape())

    rows = db_session.query(Participation).filter(Participation.course_id == target.id).all()
    assert sorted((r.bib_number, r.athlete.nom) for r in rows) == [("1", "CIBLE"), ("7", "VAGUEUN")]


def test_a_second_merge_carries_the_remembered_identity_along(db_session):
    """Fusionner la cible elle-même ailleurs ne doit pas perdre la mémoire de la première."""
    vague1, target, user = _setup(db_session)
    final = course_repository.get_or_create(
        db_session, name="Mesquer S", event_date=JOUR, event_type="triathlon-s",
        source_url="https://www.klikego.com/resultats/mesquer/1", provider="klikego",
    )
    db_session.flush()

    course_merge.merge_courses(db_session, course_id=target.id, absorbed_id=vague1.id, user_id=user.id)
    course_merge.merge_courses(db_session, course_id=final.id, absorbed_id=target.id, user_id=user.id)
    import_service.persist_results(db_session, SHARED, _shared_url_scrape())

    assert _names(db_session) == ["Mesquer S", "Tri Mesquer S vague 2"]


def test_deleting_the_target_forgets_the_absorbed_identity(db_session):
    vague1, target, user = _setup(db_session)
    course_merge.merge_courses(db_session, course_id=target.id, absorbed_id=vague1.id, user_id=user.id)

    course_repository.delete(db_session, target)
    db_session.flush()
    import_service.persist_results(db_session, SHARED, _shared_url_scrape())

    assert _names(db_session) == ["Tri Mesquer S vague 1", "Tri Mesquer S vague 2"]
