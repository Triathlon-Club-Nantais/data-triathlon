from datetime import date, timedelta

import pytest

from app.core.config import Settings
from app.core.time import utcnow
from app.repositories import athlete_repository, course_repository, participation_repository
from app.services import cache


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _course_with_participation(db, total_time, *, status="finisher", event_date=date(2026, 5, 16)):
    athlete = athlete_repository.get_or_create(db, nom="DUPONT", prenom="Jean")
    course = course_repository.get_or_create(
        db, name="Tri", event_date=event_date, event_type="triathlon-m"
    )
    participation_repository.create(
        db, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        total_time=total_time, status=status,
    )
    db.flush()
    return course


def test_in_progress_when_missing_total_time(db_session):
    course = _course_with_participation(db_session, total_time=None)
    assert cache.is_in_progress(db_session, course) is True


def test_in_progress_when_time_is_zero(db_session):
    """`00:00:00` est un temps « placeholder » publié en attendant le temps réel —
    même sémantique que `quality._ZERO_TIMES` et
    `participation_repository._TEMPS_ABSENT` : ce n'est pas un temps final.
    """
    course = _course_with_participation(db_session, total_time="00:00:00")
    assert cache.is_in_progress(db_session, course) is True


def test_finished_when_all_have_time(db_session):
    course = _course_with_participation(db_session, total_time="01:59:00")
    assert cache.is_in_progress(db_session, course) is False


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


@pytest.mark.parametrize("status", ["DNF", "DNS", "DSQ"])
def test_a_past_race_with_only_non_finishers_untimed_is_finished(db_session, status):
    """#913 : un non-finisher n'a jamais de temps final, il ne dit pas « en cours »."""
    course = _course_with_participation(db_session, total_time=None, status=status)
    assert cache.is_in_progress(db_session, course) is False


@pytest.mark.parametrize("days_ago", [0, 1])
def test_a_recent_race_with_an_untimed_dnf_stays_in_progress(db_session, days_ago):
    """#913 : un coureur encore en course, publié sans statut ni temps, est rangé
    DNF par `mapping.derive_status`. Le jour de l'épreuve et le lendemain, il
    garde donc l'épreuve au TTL court."""
    recent = utcnow().date() - timedelta(days=days_ago)
    course = _course_with_participation(db_session, total_time=None, status="DNF", event_date=recent)
    assert cache.is_in_progress(db_session, course) is True


def test_a_race_two_days_old_with_an_untimed_dnf_is_finished(db_session):
    old = utcnow().date() - timedelta(days=2)
    course = _course_with_participation(db_session, total_time=None, status="DNF", event_date=old)
    assert cache.is_in_progress(db_session, course) is False
