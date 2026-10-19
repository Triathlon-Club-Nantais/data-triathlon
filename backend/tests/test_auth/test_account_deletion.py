"""Physical deletion of an account (#1326, US1).

Runs on `db_session_fk` so that foreign keys are checked as in PostgreSQL.
"""
import pytest

from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.group import Group
from app.models.identity import Identity
from app.models.organisation import Organisation
from app.models.role import Role
from app.models.season_validation import SeasonValidation
from app.models.user import SYSTEM_USER_EMAIL, User
from app.models.user_group import UserGroup
from app.models.user_role import UserRole
from app.models.user_session import UserSession
from app.models.volunteer_action import VolunteerAction
from app.repositories import user_repository, user_role_repository
from app.services.auth import accounts, provisioning
from app.services.auth import session as session_service
from app.services.auth.authorization import LastAdministratorError
from app.services.auth.idp.base import ExternalIdentity


@pytest.fixture
def db(db_session_fk):
    return db_session_fk


@pytest.fixture
def system_user(db):
    return user_repository.create(db, email=SYSTEM_USER_EMAIL, display_name="Bénévoles (accès partagé)")


@pytest.fixture
def organisation(db):
    ligne = Organisation(slug="tcn", name="Triathlon Club Nantais")
    db.add(ligne)
    db.flush()
    return ligne


def _identity(subject="sub-1") -> ExternalIdentity:
    return ExternalIdentity(
        provider="github", subject=subject, email="alix@exemple.fr", email_verified=True, display_name="Alix",
    )


@pytest.fixture
def alix(db, system_user):
    user = provisioning.resolve_user(db, _identity())
    session_service.open_for(db, user)
    session_service.open_for(db, user)
    db.flush()
    return user


def _athlete(db):
    athlete = Athlete(nom="Martin", prenom="Alix")
    db.add(athlete)
    db.flush()
    return athlete


def test_deletion_removes_the_account_and_everything_it_owns(db, alix, organisation):
    role = Role(slug="lecteur", name="Lecteur")
    group = Group(organisation_id=organisation.id, slug="bureau", name="Bureau")
    db.add_all([role, group])
    db.flush()
    user_role_repository.grant(db, user_id=alix.id, role_id=role.id, organisation_id=organisation.id)
    db.add(UserGroup(user_id=alix.id, group_id=group.id))
    db.flush()
    user_id = alix.id

    accounts.delete_account(db, alix, origin="request")
    db.commit()

    assert db.get(User, user_id) is None
    for model in (Identity, UserSession, UserRole, UserGroup):
        assert db.query(model).filter_by(user_id=user_id).count() == 0
    assert db.get(Role, role.id) is not None
    assert db.get(Group, group.id) is not None


def test_the_linked_athlete_stays_and_optional_references_are_detached(db, alix):
    athlete = _athlete(db)
    alix.athlete_id = athlete.id
    action = VolunteerAction(athlete_id=athlete.id, season=2026, declared_by_user_id=alix.id)
    db.add(action)
    db.flush()

    accounts.delete_account(db, alix, origin="request")
    db.commit()

    assert db.get(Athlete, athlete.id) is not None
    db.refresh(action)
    assert action.declared_by_user_id is None


def test_deletion_is_logged_by_the_system_account_without_personal_data(db, alix, system_user):
    user_id = alix.id

    accounts.delete_account(db, alix, origin="request")
    db.commit()

    line = db.query(AdminActionLog).one()
    assert (line.action, line.entity_type, line.entity_id) == ("account.delete", "user", user_id)
    assert line.user_id == system_user.id
    assert line.payload == {"origin": "request", "entra_oids": []}


def test_the_entra_oids_are_logged_to_finish_the_deletion_in_the_directory(db, alix):
    db.add_all([
        Identity(user_id=alix.id, provider="entra", subject="oid-1", email="alix@exemple.fr"),
        Identity(user_id=alix.id, provider="entra", subject="oid-2", email="alix@exemple.fr"),
    ])
    db.flush()
    db.refresh(alix)

    accounts.delete_account(db, alix, origin="request")
    db.commit()

    line = db.query(AdminActionLog).one()
    assert sorted(line.payload["entra_oids"]) == ["oid-1", "oid-2"]
    assert "alix" not in str(line.payload)


def test_an_account_cited_by_a_required_reference_is_refused_and_kept(db, alix):
    db.add(SeasonValidation(athlete_id=_athlete(db).id, season=2026, validated_by_user_id=alix.id))
    db.flush()

    with pytest.raises(accounts.AccountStillReferencedError) as refusal:
        accounts.delete_account(db, alix, origin="request")

    assert refusal.value.status_code == 409
    assert "Contactez le club" in refusal.value.message
    assert db.get(User, alix.id) is not None
    assert db.query(Identity).filter_by(user_id=alix.id).count() == 1


def _cited(db, alix, system_user):
    """An account cited by a season validation and a log line it authored (#1634)."""
    validation = SeasonValidation(athlete_id=_athlete(db).id, season=2026, validated_by_user_id=alix.id)
    log = AdminActionLog(user_id=alix.id, action="course.update", entity_type="course", entity_id=1)
    db.add_all([validation, log])
    db.flush()
    return validation, log


def test_the_operator_dry_run_counts_the_required_references_and_changes_nothing(db, alix, system_user):
    _cited(db, alix, system_user)

    counts = accounts.force_delete_account(db, alix, dry_run=True)

    assert counts == {"admin_action_log.user_id": 1, "season_validations.validated_by_user_id": 1}
    assert db.get(User, alix.id) is not None


def test_the_operator_hands_the_references_to_the_club_then_deletes(db, alix, system_user):
    validation, log = _cited(db, alix, system_user)
    user_id = alix.id

    accounts.force_delete_account(db, alix, dry_run=False)
    db.commit()

    assert db.get(User, user_id) is None
    db.refresh(validation)
    db.refresh(log)
    assert (validation.validated_by_user_id, log.user_id) == (system_user.id, system_user.id)
    deletion = db.query(AdminActionLog).filter_by(action="account.delete").one()
    assert (deletion.entity_id, deletion.payload["origin"]) == (user_id, "operator")


def test_the_operator_never_deletes_the_system_account(db, system_user):
    with pytest.raises(accounts.SystemAccountDeletionError):
        accounts.force_delete_account(db, system_user, dry_run=False)


def test_the_operator_keeps_the_last_administrator(db, alix, system_user, organisation):
    admin = Role(slug="admin", name="Administrateur", is_system=True, is_superuser=True)
    db.add(admin)
    db.flush()
    user_role_repository.grant(db, user_id=alix.id, role_id=admin.id, organisation_id=organisation.id)
    _cited(db, alix, system_user)
    db.commit()

    with pytest.raises(LastAdministratorError):
        accounts.force_delete_account(db, alix, dry_run=False)
    db.rollback()

    assert db.get(User, alix.id) is not None
    assert db.query(SeasonValidation).one().validated_by_user_id == alix.id


def test_pending_entra_deletions_since_a_date_skip_empty_and_older_ones(db, system_user):
    """#1635: what is left to erase in the Entra directory, oldest first."""
    from datetime import datetime

    def deleted(when, oids, entity_id):
        db.add(AdminActionLog(user_id=system_user.id, action="account.delete", entity_type="user",
                              entity_id=entity_id, payload={"origin": "request", "entra_oids": oids},
                              created_at=when))

    deleted(datetime(2026, 9, 1), ["old-oid"], 1)
    deleted(datetime(2026, 10, 12), ["oid-b"], 3)
    deleted(datetime(2026, 10, 10), ["oid-a1", "oid-a2"], 2)
    deleted(datetime(2026, 10, 11), [], 4)
    db.flush()

    pending = accounts.pending_entra_deletions(db, since=datetime(2026, 10, 1))

    assert [(p.user_id, p.oids) for p in pending] == [(2, ["oid-a1", "oid-a2"]), (3, ["oid-b"])]


def test_the_last_administrator_is_refused_and_kept(db, alix, organisation):
    admin = Role(slug="admin", name="Administrateur", is_system=True, is_superuser=True)
    db.add(admin)
    db.flush()
    user_role_repository.grant(db, user_id=alix.id, role_id=admin.id, organisation_id=organisation.id)
    db.commit()

    with pytest.raises(LastAdministratorError):
        accounts.delete_account(db, alix, origin="request")
    db.rollback()

    assert db.get(User, alix.id) is not None


def test_an_administrator_who_is_not_the_last_may_delete_his_account(db, alix, organisation):
    admin = Role(slug="admin", name="Administrateur", is_system=True, is_superuser=True)
    other = user_repository.create(db, email="autre@exemple.fr")
    db.add(admin)
    db.flush()
    for user in (alix, other):
        user_role_repository.grant(db, user_id=user.id, role_id=admin.id, organisation_id=organisation.id)
    db.commit()

    accounts.delete_account(db, alix, origin="request")
    db.commit()

    assert db.get(User, other.id) is not None


def test_the_system_account_is_never_deleted(db, system_user):
    with pytest.raises(accounts.SystemAccountDeletionError) as refusal:
        accounts.delete_account(db, system_user, origin="request")

    assert refusal.value.status_code == 409
    assert db.get(User, system_user.id) is not None


def test_signing_in_again_creates_a_fresh_account_without_role_or_group(db, alix, organisation):
    role = Role(slug="lecteur", name="Lecteur")
    db.add(role)
    db.flush()
    user_role_repository.grant(db, user_id=alix.id, role_id=role.id, organisation_id=organisation.id)
    accounts.delete_account(db, alix, origin="request")
    db.commit()

    fresh = provisioning.resolve_user(db, _identity())
    db.commit()

    # SQLite may hand the same rowid out again; PostgreSQL never does. What matters is a blank account.
    assert db.query(User).filter(User.email != SYSTEM_USER_EMAIL).count() == 1
    assert user_role_repository.list_for_user(db, fresh.id) == []
    assert db.query(UserGroup).filter_by(user_id=fresh.id).count() == 0


def test_a_claim_is_owned_and_goes_with_the_account(db, alix):
    """#1325: `athlete_claims` belongs to the account, it never blocks its deletion."""
    from app.models.athlete_claim import AthleteClaim

    db.add(AthleteClaim(user_id=alix.id, athlete_id=_athlete(db).id, status="pending"))
    db.flush()
    user_id = alix.id

    accounts.delete_account(db, alix, origin="request")
    db.commit()

    assert db.query(AthleteClaim).filter_by(user_id=user_id).count() == 0
