from datetime import date

from app.repositories import athlete_repo, course_repo, participation_repo
from app.services import stats_service


def _seed(db):
    a1 = athlete_repo.get_or_create(db, nom="DUPONT", prenom="Jean", club="TCN")
    a2 = athlete_repo.get_or_create(db, nom="MARTIN", prenom="Paul", club="ASPTT")
    c = course_repo.get_or_create(
        db, name="Tri de Nantes", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repo.create(db, athlete_id=a1.id, course_id=c.id, bib_number="1", club="TCN")
    participation_repo.create(db, athlete_id=a2.id, course_id=c.id, bib_number="2", club="ASPTT")
    db.flush()


def test_get_stats_global(db_session):
    _seed(db_session)
    stats = stats_service.get_stats(db_session)
    assert stats["total"] == 2
    assert stats["athletes"] == 2
    assert stats["events"] == 1
    assert stats["by_type"] == {"triathlon-m": 2}
    assert stats["by_month"] == {"2026-05": 2}
    assert len(stats["recent"]) == 2


def test_get_stats_filtered_by_club(db_session):
    _seed(db_session)
    stats = stats_service.get_stats(db_session, club="nantais|tcn")
    assert stats["total"] == 1
    assert stats["athletes"] == 1


def test_list_events_counts_tcn(db_session):
    _seed(db_session)
    events = stats_service.list_events(db_session)
    assert len(events) == 1
    assert events[0]["total"] == 2
    assert events[0]["tcn_count"] == 1
