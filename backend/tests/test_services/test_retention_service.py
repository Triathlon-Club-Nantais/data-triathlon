"""Les durées de conservation annoncées par la politique de confidentialité (#1158).

Décision : `docs/superpowers/specs/2026-10-01-base-legale-decision.md` (#332).
Signalements et journal d'administration : 12 mois. Profils de l'école de
triathlon : durée de l'adhésion, plus une saison.
"""
from datetime import date, datetime, timedelta

import pytest

from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.club_member import LINK_AUTO, LINK_UNLINKED, SOURCE_FFTRI, ClubMember
from app.models.organisation import Organisation
from app.models.personal_profile import PersonalProfile
from app.models.profile_log_entry import ProfileLogEntry
from app.models.training_group import TrainingGroup, TrainingGroupMember
from app.models.training_participant import TrainingParticipant
from app.models.user_feedback import UserFeedback
from app.repositories import (
    admin_action_log_repository,
    club_member_repository,
    feedback_repository,
    profile_repository,
    training_group_repository,
    training_session_repository,
    user_repository,
)
from app.services import retention_service

NOW = datetime(2027, 9, 15, 12, 0)


@pytest.fixture
def organisation(db_session):
    ligne = Organisation(slug="tcn", name="Triathlon Club Nantais")
    db_session.add(ligne)
    db_session.flush()
    return ligne


def _feedback(db, created_at):
    entry = feedback_repository.create(db, type="bug", title="t", body="b", ip_address="203.0.113.7")
    entry.created_at = created_at
    db.flush()
    return entry


def _admin_log(db, user, created_at):
    entry = admin_action_log_repository.create(
        db, user_id=user.id, action="course_deleted", entity_type="course", entity_id=1
    )
    entry.created_at = created_at
    db.flush()
    return entry


def _profile(db, organisation, membership_ended_on):
    profile = profile_repository.create(
        db, organisation_id=organisation.id, first_name="Alix", last_name="Martin"
    )
    profile.membership_ended_on = membership_ended_on
    db.flush()
    return profile


def test_feedback_older_than_twelve_months_is_deleted_the_rest_stays(db_session):
    ancien = _feedback(db_session, NOW - timedelta(days=366))
    recent = _feedback(db_session, NOW - timedelta(days=364))

    outcome = retention_service.purge_expired(db_session, now=NOW)

    assert outcome.feedback == 1
    assert db_session.get(UserFeedback, ancien.id) is None
    assert db_session.get(UserFeedback, recent.id) is not None


def test_admin_log_older_than_twelve_months_is_deleted_the_rest_stays(db_session):
    user = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    ancien = _admin_log(db_session, user, NOW - timedelta(days=366))
    recent = _admin_log(db_session, user, NOW - timedelta(days=364))

    outcome = retention_service.purge_expired(db_session, now=NOW)

    assert outcome.admin_log == 1
    assert db_session.get(AdminActionLog, ancien.id) is None
    assert db_session.get(AdminActionLog, recent.id) is not None


def test_youth_profile_is_kept_through_the_season_after_its_membership_ended(db_session, organisation):
    # Saison 2027 en cours (15 septembre 2027) : une adhésion close pendant la
    # saison 2025 a eu sa saison de grâce (2026), une close en saison 2026 la vit.
    expire = _profile(db_session, organisation, date(2026, 8, 31))
    en_grace = _profile(db_session, organisation, date(2026, 9, 1))
    adherent = _profile(db_session, organisation, None)

    outcome = retention_service.purge_expired(db_session, now=NOW)

    assert outcome.profiles == 1
    assert db_session.get(PersonalProfile, expire.id) is None
    assert db_session.get(PersonalProfile, en_grace.id) is not None
    assert db_session.get(PersonalProfile, adherent.id) is not None


def test_purging_a_profile_takes_its_log_and_attendance_with_it(db_session, organisation):
    profile = _profile(db_session, organisation, date(2025, 6, 30))
    entry = profile_repository.add_log_entry(db_session, profile_id=profile.id, text="Nage : progrès")
    seance = training_session_repository.create(db_session, date=date(2025, 5, 3))
    inscription, _ = training_session_repository.add_participant(
        db_session, training_session_id=seance.id, profile_id=profile.id, present=True
    )

    retention_service.purge_expired(db_session, now=NOW)

    assert db_session.get(ProfileLogEntry, entry.id) is None
    assert db_session.get(TrainingParticipant, inscription.id) is None


def test_purging_a_profile_removes_its_group_memberships(db_session, organisation):
    profile = _profile(db_session, organisation, date(2025, 6, 30))
    group = training_group_repository.create(db_session, organisation_id=organisation.id, name="Benjamins")
    training_group_repository.add_member(db_session, training_group_id=group.id, profile_id=profile.id)

    retention_service.purge_expired(db_session, now=NOW)

    assert db_session.query(TrainingGroupMember).count() == 0
    assert db_session.get(TrainingGroup, group.id) is not None


def test_dry_run_counts_without_deleting(db_session, organisation):
    ancien = _feedback(db_session, NOW - timedelta(days=400))
    profile = _profile(db_session, organisation, date(2024, 6, 30))

    outcome = retention_service.purge_expired(db_session, now=NOW, dry_run=True)

    assert (outcome.feedback, outcome.profiles, outcome.dry_run) == (1, 1, True)
    assert db_session.get(UserFeedback, ancien.id) is not None
    assert db_session.get(PersonalProfile, profile.id) is not None


@pytest.mark.parametrize(
    ("today", "cutoff"),
    [
        (date(2027, 8, 31), date(2025, 9, 1)),
        (date(2027, 9, 1), date(2026, 9, 1)),
    ],
)
def test_youth_profile_cutoff_moves_on_september_first(today, cutoff):
    assert retention_service.youth_profile_cutoff(today) == cutoff


def test_an_entry_exactly_twelve_months_old_is_kept(db_session):
    juste = _feedback(db_session, NOW - timedelta(days=365))

    outcome = retention_service.purge_expired(db_session, now=NOW)

    assert outcome.feedback == 0
    assert db_session.get(UserFeedback, juste.id) is not None


@pytest.mark.parametrize(
    ("today", "first_kept"),
    [(date(2026, 10, 6), 2025), (date(2026, 8, 31), 2024), (date(2026, 9, 1), 2025)],
)
def test_club_members_are_kept_for_the_current_and_previous_season(today, first_kept):
    assert retention_service.club_members_cutoff(today) == first_kept


def test_purge_handles_old_member_seasons(db_session):
    athlete = Athlete(nom="MARTIN", prenom="Anne")
    db_session.add(athlete)
    db_session.flush()
    club_member_repository.replace_season(db_session, 2023, [
        ClubMember(season=2023, nom="MARTIN", prenom="Anne", licence_id="C1", athlete_id=athlete.id,
                   link_status=LINK_AUTO, source=SOURCE_FFTRI),
        ClubMember(season=2023, nom="X", prenom="Y", licence_id="C2",
                   link_status=LINK_UNLINKED, source=SOURCE_FFTRI),
    ])

    outcome = retention_service.purge_expired(db_session, now=datetime(2026, 10, 6))

    assert outcome.club_members == 2
    (kept,) = club_member_repository.list_season(db_session, 2023)
    assert (kept.athlete_id, kept.licence_id) == (athlete.id, None)
