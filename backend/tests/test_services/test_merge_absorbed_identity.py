"""Un rescrape ne ressuscite pas une épreuve fusionnée dont l'URL est partagée (#983).

L'URL de l'absorbée repointée en passive ne suffit pas quand d'autres épreuves la
portent en active (manches Breizh Chrono, variantes wiclax/timepulse) : le cron
re-scrape l'URL pour elles, et la ligne de la manche absorbée, qui n'apparie plus
aucune épreuve par identité, la recréait sous un nouvel id.

Précision du 29/09 : ces lignes sont **ignorées**, jamais redirigées vers la
cible. La redirection passait par l'upsert ordinaire, qui écrasait les temps et
rangs de la cible et y ajoutait des doublons d'athlètes (revue de #1145).
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
VAGUE1 = "Tri Mesquer S vague 1"
VAGUE2 = "Tri Mesquer S vague 2"
CIBLE = "Triathlon de Mesquer S"


def _row(
    bib: str, event_name: str, url: str, provider: str, nom: str, *,
    total_time: str = "01:10:00", rank: int | None = None,
) -> ScrapedResult:
    return ScrapedResult(
        source_url=url, provider=provider, athlete_name=nom, athlete_firstname="Jean",
        bib_number=bib, event_name=event_name, event_date=JOUR, event_type="triathlon-s",
        total_time=total_time, rank_overall=rank,
    )


def _shared_url_scrape() -> list[ScrapedResult]:
    return [
        _row("7", VAGUE1, SHARED, "wiclax", "VAGUEUN"),
        _row("2", VAGUE2, SHARED, "wiclax", "VAGUEDEUX"),
    ]


def _names(db_session) -> list[str]:
    return sorted(c.name for c in db_session.query(Course).all())


def _course(db_session, name: str) -> Course:
    return course_repository.get_by_identity(db_session, name, JOUR, "triathlon-s", False)


def _rows(db_session, course: Course) -> list[tuple]:
    return sorted(
        (p.bib_number, p.athlete.nom, p.total_time, p.rank_overall)
        for p in db_session.query(Participation).filter(Participation.course_id == course.id)
    )


def _merge(db_session, *, target: Course, absorbed: Course) -> None:
    user = user_repository.create(db_session, email="admin@exemple.fr", display_name="admin")
    db_session.flush()
    course_merge.merge_courses(
        db_session, course_id=target.id, absorbed_id=absorbed.id, user_id=user.id
    )


def _setup(db_session, *, absorbed_rows=None, target_rows=None):
    """Deux vagues sous l'URL partagée, la cible chez un autre chronométreur."""
    import_service.persist_results(db_session, SHARED, absorbed_rows or _shared_url_scrape())
    import_service.persist_results(
        db_session, OTHER, target_rows or [_row("1", CIBLE, OTHER, "klikego", "CIBLE")]
    )
    db_session.flush()
    return _course(db_session, VAGUE1), _course(db_session, CIBLE)


def test_a_rescrape_of_the_shared_url_does_not_recreate_the_absorbed_course(db_session):
    vague1, target = _setup(db_session)
    _merge(db_session, target=target, absorbed=vague1)

    import_service.persist_results(db_session, SHARED, _shared_url_scrape())

    assert _names(db_session) == [VAGUE2, CIBLE]


def test_the_absorbed_rows_are_ignored_and_counted_as_skipped(db_session):
    vague1, target = _setup(db_session)
    _merge(db_session, target=target, absorbed=vague1)
    avant = _rows(db_session, target)

    bilan = import_service.persist_results(db_session, SHARED, _shared_url_scrape())

    assert _rows(db_session, target) == avant
    # La ligne ignorée, plus celle de la vague 2, inchangée.
    assert (bilan["imported"], bilan["updated"], bilan["skipped"]) == (0, 0, 2)
    assert bilan["passive_sources"] == []


def test_an_absorbed_row_never_overwrites_the_target_times_and_ranks(db_session):
    """Revue de #1145 : DUPONT dossard 7 passait de 01:10:00, rang 5, à 01:20:00, rang 1."""
    vague1, target = _setup(
        db_session,
        absorbed_rows=[
            _row("7", VAGUE1, SHARED, "wiclax", "DUPONT", total_time="01:20:00", rank=1),
            _row("2", VAGUE2, SHARED, "wiclax", "VAGUEDEUX"),
        ],
        target_rows=[_row("7", CIBLE, OTHER, "klikego", "DUPONT", total_time="01:10:00", rank=5)],
    )
    _merge(db_session, target=target, absorbed=vague1)

    import_service.persist_results(
        db_session, SHARED,
        [
            _row("7", VAGUE1, SHARED, "wiclax", "DUPONT", total_time="01:20:00", rank=1),
            _row("2", VAGUE2, SHARED, "wiclax", "VAGUEDEUX"),
        ],
    )

    assert _rows(db_session, target) == [("7", "DUPONT", "01:10:00", 5)]


def test_an_absorbed_row_never_adds_a_second_line_for_the_same_athlete(db_session):
    """Revue de #1145 : MARTIN figurait deux fois, dossards 108 (klikego) et 8 (wiclax)."""
    vague1, target = _setup(
        db_session,
        absorbed_rows=[
            _row("8", VAGUE1, SHARED, "wiclax", "MARTIN"),
            _row("2", VAGUE2, SHARED, "wiclax", "VAGUEDEUX"),
        ],
        target_rows=[_row("108", CIBLE, OTHER, "klikego", "MARTIN")],
    )
    _merge(db_session, target=target, absorbed=vague1)

    import_service.persist_results(
        db_session, SHARED,
        [_row("8", VAGUE1, SHARED, "wiclax", "MARTIN"), _row("2", VAGUE2, SHARED, "wiclax", "VAGUEDEUX")],
    )

    assert _rows(db_session, target) == [("108", "MARTIN", "01:10:00", None)]


def test_a_same_url_merge_keeps_the_target_list_alone_and_reliable(db_session):
    """Revue de #1145 : l'URL déjà connue de la cible y versait les deux listes,
    d'où `duplicate_bib` et `is_reliable_computed=False` à chaque rescrape."""
    both = [
        _row("1", CIBLE, SHARED, "wiclax", "CIBLEUN", rank=1),
        _row("2", CIBLE, SHARED, "wiclax", "CIBLEDEUX", rank=2),
        _row("1", VAGUE1, SHARED, "wiclax", "AUTREUN", rank=1),
        _row("2", VAGUE1, SHARED, "wiclax", "AUTREDEUX", rank=2),
    ]
    import_service.persist_results(db_session, SHARED, both)
    db_session.flush()
    target, vague1 = _course(db_session, CIBLE), _course(db_session, VAGUE1)
    _merge(db_session, target=target, absorbed=vague1)
    avant = _rows(db_session, target)

    import_service.persist_results(db_session, SHARED, both)
    db_session.flush()

    assert _names(db_session) == [CIBLE]
    assert _rows(db_session, target) == avant
    assert target.is_reliable_computed is not False
    assert "duplicate_bib" not in (target.quality_issues or {})


def test_a_second_merge_carries_the_remembered_identity_along(db_session):
    """Fusionner la cible elle-même ailleurs ne doit pas perdre la mémoire de la première."""
    vague1, target = _setup(db_session)
    final = course_repository.get_or_create(
        db_session, name="Mesquer S", event_date=JOUR, event_type="triathlon-s",
        source_url="https://www.klikego.com/resultats/mesquer/1", provider="klikego",
    )
    db_session.flush()
    _merge(db_session, target=target, absorbed=vague1)
    user = user_repository.create(db_session, email="admin2@exemple.fr", display_name="admin2")
    db_session.flush()
    course_merge.merge_courses(db_session, course_id=final.id, absorbed_id=target.id, user_id=user.id)

    import_service.persist_results(db_session, SHARED, _shared_url_scrape())

    assert _names(db_session) == ["Mesquer S", VAGUE2]


def test_deleting_the_target_forgets_the_absorbed_identity(db_session):
    vague1, target = _setup(db_session)
    _merge(db_session, target=target, absorbed=vague1)

    course_repository.delete(db_session, target)
    db_session.flush()
    import_service.persist_results(db_session, SHARED, _shared_url_scrape())

    assert _names(db_session) == [VAGUE1, VAGUE2]
