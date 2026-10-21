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
from app.models.member_email import SOURCE_IMPORT, MemberEmail
from app.models.organisation import Organisation
from app.models.personal_profile import PersonalProfile
from app.models.profile_log_entry import ProfileLogEntry
from app.models.profile_measurement import ProfileMeasurement
from app.models.role import Role
from app.models.season_validation import SeasonValidation
from app.models.training_group import TrainingGroup, TrainingGroupMember
from app.models.training_participant import TrainingParticipant
from app.models.user import SYSTEM_USER_EMAIL, User
from app.models.user_feedback import UserFeedback
from app.repositories import (
    admin_action_log_repository,
    club_member_repository,
    feedback_repository,
    member_email_repository,
    profile_repository,
    training_group_repository,
    training_session_repository,
    user_repository,
    user_role_repository,
)
from app.services import retention_service
from app.services.auth import accounts

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


def test_purging_a_profile_takes_its_measurements_with_it(db_session, organisation):
    profile = _profile(db_session, organisation, date(2025, 6, 30))
    measurement = profile_repository.add_measurement(
        db_session, profile_id=profile.id, measured_on=date(2025, 5, 3), event="1000 m", duration_tenths=3000
    )

    retention_service.purge_expired(db_session, now=NOW)

    assert db_session.get(ProfileMeasurement, measurement.id) is None


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


def test_member_emails_older_than_the_previous_season_are_purged(db_session):
    db_session.add_all([
        MemberEmail(email="old@exemple.fr", season=2024, source=SOURCE_IMPORT),
        MemberEmail(email="prev@exemple.fr", season=2025, source=SOURCE_IMPORT),
        MemberEmail(email="now@exemple.fr", season=2026, source=SOURCE_IMPORT),
    ])
    db_session.flush()

    dry = retention_service.purge_expired(db_session, now=datetime(2026, 10, 6), dry_run=True)
    assert dry.member_emails == 1
    assert member_email_repository.seasons(db_session) == [2026, 2025, 2024]

    outcome = retention_service.purge_expired(db_session, now=datetime(2026, 10, 6))
    assert outcome.member_emails == 1
    assert member_email_repository.seasons(db_session) == [2026, 2025]


# --- Accounts inactive for 5 years (#1326) ----------------------------------

LONG_AGO = NOW - timedelta(days=4000)
#: Same calendar date five years before NOW (2027-09-15 12:00), not 5 x 365 days.
CUTOFF = datetime(2022, 9, 15, 12, 0)


def _account(db, email, last_seen_at):
    user = user_repository.create(db, email=email)
    user.last_seen_at = last_seen_at
    db.flush()
    return user


@pytest.fixture
def system_user(db_session):
    return _account(db_session, SYSTEM_USER_EMAIL, LONG_AGO)


def test_an_account_without_role_inactive_for_five_years_is_deleted(db_session, system_user):
    stale = _account(db_session, "ancien@exemple.fr", CUTOFF - timedelta(minutes=1))
    recent = _account(db_session, "recent@exemple.fr", CUTOFF)
    stale_id = stale.id

    outcome = retention_service.purge_expired(db_session, now=NOW)

    assert (outcome.accounts_deleted, outcome.accounts_skipped) == (1, 0)
    assert db_session.get(User, stale_id) is None
    assert db_session.get(User, recent.id) is not None
    line = db_session.query(AdminActionLog).filter_by(action="account.delete").one()
    assert (line.entity_id, line.payload, line.user_id) == (stale_id, {"origin": "inactivity", "entra_oids": []}, system_user.id)


def test_an_account_with_a_role_never_expires(db_session, system_user, organisation):
    holder = _account(db_session, "benevole@exemple.fr", LONG_AGO)
    role = Role(slug="lecteur", name="Lecteur")
    db_session.add(role)
    db_session.flush()
    user_role_repository.grant(db_session, user_id=holder.id, role_id=role.id, organisation_id=organisation.id)

    outcome = retention_service.purge_expired(db_session, now=NOW)

    assert outcome.accounts_deleted == 0
    assert db_session.get(User, holder.id) is not None


def test_the_system_account_never_expires(db_session, system_user):
    retention_service.purge_expired(db_session, now=NOW)

    assert db_session.get(User, system_user.id) is not None


def test_an_eligible_account_cited_by_a_required_reference_is_skipped(db_session, system_user):
    cited = _account(db_session, "valideur@exemple.fr", LONG_AGO)
    athlete = Athlete(nom="Martin", prenom="Alix")
    db_session.add(athlete)
    db_session.flush()
    db_session.add(SeasonValidation(athlete_id=athlete.id, season=2020, validated_by_user_id=cited.id))
    db_session.flush()

    outcome = retention_service.purge_expired(db_session, now=NOW)

    assert (outcome.accounts_deleted, outcome.accounts_skipped) == (0, 1)
    assert db_session.get(User, cited.id) is not None


def test_dry_run_counts_accounts_without_deleting(db_session, system_user):
    stale = _account(db_session, "ancien@exemple.fr", LONG_AGO)

    outcome = retention_service.purge_expired(db_session, now=NOW, dry_run=True)

    assert (outcome.accounts_deleted, outcome.accounts_skipped) == (1, 0)
    assert db_session.get(User, stale.id) is not None


def test_an_account_cited_only_by_expired_log_lines_is_deleted(db_session, system_user):
    """The admin log is purged first, so 12-month-old lines no longer block."""
    stale = _account(db_session, "ancien-admin@exemple.fr", LONG_AGO)
    _admin_log(db_session, stale, NOW - timedelta(days=400))
    stale_id = stale.id

    outcome = retention_service.purge_expired(db_session, now=NOW)

    assert outcome.accounts_deleted == 1
    assert db_session.get(User, stale_id) is None


@pytest.mark.parametrize(
    ("now", "cutoff"),
    [
        (datetime(2027, 9, 15, 12, 0), datetime(2022, 9, 15, 12, 0)),
        (datetime(2028, 2, 29, 8, 30), datetime(2023, 2, 28, 8, 30)),
        (datetime(2029, 3, 1), datetime(2024, 3, 1)),
        (datetime(2029, 2, 28), datetime(2024, 2, 28)),
    ],
)
def test_the_inactivity_cutoff_is_the_same_calendar_date_five_years_earlier(now, cutoff):
    assert accounts.inactivity_cutoff(now) == cutoff


def test_a_deactivated_account_without_role_expires_too(db_session, system_user):
    """Deactivation (allow-list removal) does not stop the clock: no role, 5 years, gone."""
    closed = _account(db_session, "ferme@exemple.fr", LONG_AGO)
    closed.is_active = False
    db_session.flush()
    closed_id = closed.id

    outcome = retention_service.purge_expired(db_session, now=NOW)

    assert outcome.accounts_deleted == 1
    assert db_session.get(User, closed_id) is None
