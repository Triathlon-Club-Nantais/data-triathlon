"""Un heat Challenge devient un `Challenge`, pas une épreuve de plus (#1008)."""
from datetime import date

from app.models.challenge import Challenge, ChallengeResult
from app.models.course import Course
from app.scrapers.base import ScrapedResult
from app.services import import_service, stats_service

URL = "https://www.klikego.com/resultats/medoc-atlantique-frenchman-triathlon-carcans-2026/1354050643080-23"
DAY = date(2026, 5, 13)
EVENT = "MEDOC ATLANTIQUE FRENCHMAN 2026"
CHALLENGE_HEAT = "START CHALLENGE (XS - M - L)"


def _row(heat: str, nom: str, bib: str, *, time="02:00:00", rank=1) -> ScrapedResult:
    return ScrapedResult(
        source_url=f"{URL}?heat={heat}", provider="klikego", athlete_name=nom,
        athlete_firstname="Jean", bib_number=bib, event_name=f"{EVENT} - {heat}",
        event_date=DAY, event_type="triathlon-m", total_time=time, rank_overall=rank,
    )


def _batch(names, *, challenge_heat=CHALLENGE_HEAT):
    rows = []
    for i, nom in enumerate(names):
        rows.append(_row("XS", nom, f"xs{i}", rank=i + 1))
        rows.append(_row("M", nom, f"m{i}", rank=i + 1))
    for i, nom in enumerate(names):
        rows.append(_row(challenge_heat, nom, f"c{i}", time="06:50:33", rank=i + 1))
    return rows


def test_challenge_heat_is_stored_as_a_challenge(db_session):
    names = [f"NOM{i}" for i in range(5)]
    outcome = import_service.persist_results(db_session, URL, _batch(names))

    courses = db_session.query(Course).all()
    assert sorted(c.name.rsplit(" - ", 1)[1] for c in courses) == ["M", "XS"]
    assert all(c.participation_count == 5 for c in courses)
    challenge = db_session.query(Challenge).one()
    assert challenge.name == f"{EVENT} - {CHALLENGE_HEAT}"
    assert sorted(link.course_id for link in challenge.links) == sorted(c.id for c in courses)
    assert db_session.query(ChallengeResult).count() == 5
    assert outcome["challenges"] == 1


def test_stats_are_identical_with_or_without_the_challenge_heat(db_session):
    names = [f"NOM{i}" for i in range(5)]
    without = [r for r in _batch(names) if "CHALLENGE" not in r.event_name]
    import_service.persist_results(db_session, URL, without)
    before = stats_service.get_stats(db_session)
    import_service.persist_results(db_session, URL, _batch(names))
    assert db_session.query(Challenge).count() == 1
    assert stats_service.get_stats(db_session) == before


def test_isolated_challenge_heat_stays_a_course(db_session):
    rows = [_row("La Baule - Challenge", f"SOLO{i}", f"b{i}") for i in range(4)]
    outcome = import_service.persist_results(db_session, URL, rows)
    assert db_session.query(Challenge).count() == 0
    assert db_session.query(Course).one().participation_count == 4
    assert outcome["challenges"] == 0
    assert outcome["imported"] == 4


def test_reimport_is_idempotent(db_session):
    names = [f"NOM{i}" for i in range(5)]
    import_service.persist_results(db_session, URL, _batch(names))
    import_service.persist_results(db_session, URL, _batch(names))
    assert db_session.query(Challenge).count() == 1
    assert db_session.query(ChallengeResult).count() == 5
    assert db_session.query(Course).count() == 2
