"""References to `users.id` outside the account's own tables (#1326, research D1)."""
from app.models.admin_action_log import AdminActionLog
from app.models.allowed_email import AllowedEmail
from app.models.athlete import Athlete
from app.models.ignored_identity_case import IgnoredIdentityCase
from app.models.season_validation import SeasonValidation
from app.models.user_feedback import UserFeedback
from app.models.volunteer_action import VolunteerAction
from app.repositories import user_repository


def _user(db, email="compte@exemple.fr"):
    return user_repository.create(db, email=email)


def _athlete(db):
    athlete = Athlete(nom="Martin", prenom="Alix")
    db.add(athlete)
    db.flush()
    return athlete


def test_required_references_are_the_five_measured_columns():
    """Frozen on purpose: a nullability change must show up in review."""
    assert {f"{column.table.name}.{column.name}" for column in user_repository.required_references()} == {
        "admin_action_log.user_id",
        "season_validations.validated_by_user_id",
        "ignored_course_duplicates.ignored_by_user_id",
        "ignored_identity_cases.ignored_by_user_id",
        "benevole_access_config.updated_by_user_id",
    }


def test_owned_tables_are_neither_required_nor_optional_references():
    tables = {
        column.table.name
        for column in user_repository.required_references() + user_repository.optional_references()
    }
    assert not tables & {"identities", "user_sessions", "user_roles", "user_groups", "users"}


def test_has_required_reference_is_false_for_an_uncited_account(db_session):
    user = _user(db_session)

    assert user_repository.has_required_reference(db_session, user.id) is False


def test_an_admin_log_line_is_a_required_reference(db_session):
    user = _user(db_session)
    db_session.add(AdminActionLog(user_id=user.id, action="course.delete", entity_type="course", entity_id=1))
    db_session.flush()

    assert user_repository.has_required_reference(db_session, user.id) is True


def test_a_season_validation_is_a_required_reference(db_session):
    user = _user(db_session)
    db_session.add(SeasonValidation(athlete_id=_athlete(db_session).id, season=2026, validated_by_user_id=user.id))
    db_session.flush()

    assert user_repository.has_required_reference(db_session, user.id) is True


def test_an_ignored_identity_case_is_a_required_reference(db_session):
    user = _user(db_session)
    db_session.add(IgnoredIdentityCase(
        athlete_id=_athlete(db_session).id, reason="same_course_bibs", fingerprint="1", ignored_by_user_id=user.id,
    ))
    db_session.flush()

    assert user_repository.has_required_reference(db_session, user.id) is True


def test_another_account_reference_does_not_count(db_session):
    user, other = _user(db_session), _user(db_session, "autre@exemple.fr")
    db_session.add(AdminActionLog(user_id=other.id, action="course.delete", entity_type="course", entity_id=1))
    db_session.flush()

    assert user_repository.has_required_reference(db_session, user.id) is False


def test_detach_optional_references_nulls_only_this_account(db_session):
    user, other = _user(db_session), _user(db_session, "autre@exemple.fr")
    athlete = _athlete(db_session)
    action = VolunteerAction(athlete_id=athlete.id, season=2026, declared_by_user_id=user.id)
    allowed = AllowedEmail(email="x@exemple.fr", created_by_user_id=user.id)
    feedback = UserFeedback(type="bug", title="t", body="b", user_id=user.id)
    kept = UserFeedback(type="bug", title="t", body="b", user_id=other.id)
    db_session.add_all([action, allowed, feedback, kept])
    db_session.flush()

    user_repository.detach_optional_references(db_session, user.id)
    db_session.expire_all()

    assert action.declared_by_user_id is None
    assert allowed.created_by_user_id is None
    assert feedback.user_id is None
    assert kept.user_id == other.id
