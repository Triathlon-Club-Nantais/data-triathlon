from datetime import date, timedelta

from app.core.config import Settings
from app.core.time import utcnow
from app.repositories import athlete_repo, course_repo, participation_repo
from app.services import cache


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _course_with_participation(db, total_time):
    athlete = athlete_repo.get_or_create(db, nom="DUPONT", prenom="Jean")
    course = course_repo.get_or_create(
        db, name="Tri", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repo.create(
        db, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        total_time=total_time,
    )
    db.flush()
    return course


def test_in_progress_when_missing_total_time(db_session):
    course = _course_with_participation(db_session, total_time=None)
    assert cache.is_in_progress(db_session, course.id) is True


def test_finished_when_all_have_time(db_session):
    course = _course_with_participation(db_session, total_time="01:59:00")
    assert cache.is_in_progress(db_session, course.id) is False


def test_is_fresh_within_ttl(db_session):
    course = _course_with_participation(db_session, total_time="01:59:00")
    course.scraped_at = utcnow()
    assert cache.is_fresh(db_session, course, _settings()) is True


def test_not_fresh_after_ttl(db_session):
    course = _course_with_participation(db_session, total_time="01:59:00")
    # Scrapée il y a 31 jours → au-delà du TTL « terminée » (30 j)
    course.scraped_at = utcnow() - timedelta(days=31)
    assert cache.is_fresh(db_session, course, _settings()) is False


def test_in_progress_short_ttl(db_session):
    course = _course_with_participation(db_session, total_time=None)
    # En cours, scrapée il y a 20 min → au-delà du TTL « en cours » (10 min)
    course.scraped_at = utcnow() - timedelta(minutes=20)
    assert cache.is_fresh(db_session, course, _settings()) is False
