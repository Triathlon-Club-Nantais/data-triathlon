"""Each write that can change a verdict recomputes it (#1206)."""
from datetime import date

import pytest

from app.core import counter_scope
from app.core.config import Settings
from app.repositories import (
    athlete_repository,
    course_repository,
    participation_repository,
    tcn_count_repository,
    user_repository,
)
from app.scrapers.base import ScrapedResult
from app.services import admin_actions, athlete_merge, import_service


@pytest.fixture(autouse=True)
def _tcn_is_ambiguous():
    counter_scope.load(
        disciplines=counter_scope.non_federal_disciplines(),
        club_labels=counter_scope.tcn_club_labels(),
        ambiguous_club_labels={"tcn"},
    )


@pytest.fixture
def admin(db_session):
    user = user_repository.create(db_session, email="admin@exemple.fr")
    db_session.flush()
    return user


def _course(db, name, day):
    return course_repository.get_or_create(
        db, name=name, event_date=date(2026, 5, day), event_type="triathlon-m"
    )


def _result(db, athlete, course, bib, club, *, pending=False):
    return participation_repository.create(
        db, athlete_id=athlete.id, course_id=course.id, bib_number=bib, club=club,
        is_pending_validation=pending,
    )


def _verdict(db, participation_id):
    db.expire_all()
    return participation_repository.get(db, participation_id).counts_for_tcn


def test_reassigning_a_bare_tcn_result_to_a_club_athlete_counts_it(db_session, admin):
    stranger = athlete_repository.get_or_create(db_session, nom="SUD", prenom="Leo")
    member = athlete_repository.get_or_create(db_session, nom="OUEST", prenom="Lea")
    bare_course = _course(db_session, "A", 1)
    bare = _result(db_session, stranger, bare_course, "1", "TCN")
    _result(db_session, member, _course(db_session, "B", 2), "1", "Triathlon Club Nantais")

    admin_actions.reassign_participation(
        db_session, participation_id=bare.id, athlete_id=member.id, user_id=admin.id
    )

    assert _verdict(db_session, bare.id) is True
    assert course_repository.get(db_session, bare_course.id).tcn_count == 1


def test_merging_athletes_counts_the_absorbed_club_result_for_the_bare_tcn(db_session, admin):
    kept = athlete_repository.get_or_create(db_session, nom="OUEST", prenom="Lea")
    absorbed = athlete_repository.get_or_create(db_session, nom="OUESTE", prenom="Lea")
    bare = _result(db_session, kept, _course(db_session, "A", 1), "1", "TCN")
    _result(db_session, absorbed, _course(db_session, "B", 2), "1", "Triathlon Club Nantais")

    athlete_merge.merge_athletes(db_session, kept_id=kept.id, absorbed_id=absorbed.id, user_id=admin.id)

    assert _verdict(db_session, bare.id) is True


def test_deleting_the_only_club_result_uncounts_the_bare_tcn(db_session, admin):
    member = athlete_repository.get_or_create(db_session, nom="OUEST", prenom="Lea")
    bare_course = _course(db_session, "A", 1)
    bare = _result(db_session, member, bare_course, "1", "TCN")
    clear_course = _course(db_session, "B", 2)
    clear = _result(db_session, member, clear_course, "1", "Triathlon Club Nantais")
    tcn_count_repository.recompute_counts_for_tcn(db_session)
    assert _verdict(db_session, bare.id) is True

    admin_actions.delete_participation(db_session, participation_id=clear.id, user_id=admin.id)

    assert _verdict(db_session, bare.id) is False
    assert course_repository.get(db_session, bare_course.id).tcn_count == 0
    assert course_repository.get(db_session, clear_course.id).tcn_count == 0


def test_validating_a_club_result_confirms_the_bare_tcn(db_session, admin):
    member = athlete_repository.get_or_create(db_session, nom="OUEST", prenom="Lea")
    bare = _result(db_session, member, _course(db_session, "A", 1), "1", "TCN")
    clear_course = _course(db_session, "B", 2)
    pending = _result(db_session, member, clear_course, "1", "Triathlon Club Nantais", pending=True)

    admin_actions.validate_participation(db_session, participation_id=pending.id, user_id=admin.id)

    assert _verdict(db_session, bare.id) is True
    assert course_repository.get(db_session, clear_course.id).tcn_count == 1


def test_correcting_the_club_of_a_pending_result_recomputes_its_athlete(db_session, admin):
    member = athlete_repository.get_or_create(db_session, nom="OUEST", prenom="Lea")
    bare = _result(db_session, member, _course(db_session, "A", 1), "1", "TCN", pending=True)
    _result(db_session, member, _course(db_session, "B", 2), "1", "Triathlon Club Nantais")

    admin_actions.update_participation_fields(
        db_session, participation_id=bare.id, champs={"club": "tcn "}, user_id=admin.id
    )

    assert _verdict(db_session, bare.id) is True


def test_an_import_confirms_an_older_bare_tcn_of_the_same_athlete(db_session, patch_scraper):
    member = athlete_repository.get_or_create(db_session, nom="OUEST", prenom="Lea")
    old_course = _course(db_session, "Ancienne", 1)
    bare = _result(db_session, member, old_course, "1", "TCN")
    db_session.commit()
    url = "https://www.klikego.com/resultats/event/456"
    patch_scraper([
        ScrapedResult(
            source_url=url, provider="klikego", athlete_name="OUEST", athlete_firstname="Lea",
            bib_number="7", club="Triathlon Club Nantais", event_name="Tri neuf",
            event_date=date(2026, 6, 1), event_type="triathlon-m", total_time="01:59:00",
        )
    ])

    import_service.import_event(
        db_session, url,
        Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000),
    )

    assert _verdict(db_session, bare.id) is True
    assert course_repository.get(db_session, old_course.id).tcn_count == 1


def _member_with_bare_elsewhere(db, clear_course):
    """Un athlète dont le « TCN » nu d'une autre épreuve compte grâce à `clear_course`."""
    member = athlete_repository.get_or_create(db, nom="OUEST", prenom="Lea")
    bare_course = _course(db, "Nue", 20)
    bare = _result(db, member, bare_course, "1", "TCN")
    clear = _result(db, member, clear_course, "1", "Triathlon Club Nantais")
    tcn_count_repository.recompute_counts_for_tcn(db)
    assert _verdict(db, bare.id) is True
    return member, bare, bare_course, clear


def test_deleting_a_course_uncounts_the_bare_tcn_it_was_confirming(db_session, admin):
    clear_course = _course(db_session, "Claire", 2)
    _member, bare, bare_course, _clear = _member_with_bare_elsewhere(db_session, clear_course)

    admin_actions.delete_course(db_session, course_id=clear_course.id, user_id=admin.id)

    assert _verdict(db_session, bare.id) is False
    assert course_repository.get(db_session, bare_course.id).tcn_count == 0


def test_merging_courses_uncounts_the_bare_tcn_the_absorbed_one_confirmed(db_session, admin):
    from app.services import course_merge

    clear_course = _course(db_session, "Claire", 2)
    target = _course(db_session, "Cible", 2)
    _member, bare, _bare_course, _clear = _member_with_bare_elsewhere(db_session, clear_course)

    course_merge.merge_courses(
        db_session, course_id=target.id, absorbed_id=clear_course.id, user_id=admin.id
    )

    assert _verdict(db_session, bare.id) is False


def test_an_import_that_repoints_a_row_recomputes_the_previous_athlete(db_session, patch_scraper):
    old = athlete_repository.get_or_create(db_session, nom="OUEST", prenom="Lea")
    event_course = course_repository.get_or_create(
        db_session, name="Tri neuf", event_date=date(2026, 6, 1), event_type="triathlon-m"
    )
    clear = participation_repository.create(
        db_session, athlete_id=old.id, course_id=event_course.id, bib_number="7",
        club="Triathlon Club Nantais", source_identity_key="OUEST|Lea",
    )
    bare = _result(db_session, old, _course(db_session, "Nue", 20), "1", "TCN")
    tcn_count_repository.recompute_counts_for_tcn(db_session)
    assert _verdict(db_session, bare.id) is True
    db_session.commit()
    url = "https://www.klikego.com/resultats/event/456"
    patch_scraper([
        ScrapedResult(
            source_url=url, provider="klikego", athlete_name="SUDEST", athlete_firstname="Marc",
            bib_number="7", club="Triathlon Club Nantais", event_name="Tri neuf",
            event_date=date(2026, 6, 1), event_type="triathlon-m", total_time="01:59:00",
        )
    ])

    import_service.import_event(
        db_session, url,
        Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000),
    )

    assert participation_repository.get(db_session, clear.id).athlete_id != old.id
    assert _verdict(db_session, bare.id) is False
