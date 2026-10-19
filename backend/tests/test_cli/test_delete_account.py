"""`delete-account`: the operator honours an erasure request refused with 409 (#1634)."""
from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import delete_account as cmd
from app.cli.commands.delete_account import USAGE
from app.models.athlete import Athlete
from app.models.season_validation import SeasonValidation
from app.models.user import SYSTEM_USER_EMAIL, User
from app.repositories import user_repository

runner = CliRunner()


def _cited(db):
    user_repository.create(db, email=SYSTEM_USER_EMAIL, display_name="Bénévoles")
    user = user_repository.create(db, email="alix@exemple.fr", display_name="Alix")
    athlete = Athlete(nom="Martin", prenom="Alix")
    db.add(athlete)
    db.flush()
    db.add(SeasonValidation(athlete_id=athlete.id, season=2026, validated_by_user_id=user.id))
    db.flush()
    return user


def _run(*arguments):
    return runner.invoke(app, ["delete-account", *arguments])


def test_without_yes_it_only_reports(brancher_session, db_session):
    brancher_session(cmd)
    user = _cited(db_session)

    result = _run("--user-id", str(user.id))

    assert result.exit_code == 0
    assert "season_validations.validated_by_user_id : 1" in result.stdout
    assert "passe à blanc" in result.stdout
    assert db_session.get(User, user.id) is not None


def test_with_yes_it_deletes_by_address(brancher_session, db_session):
    brancher_session(cmd)
    user = _cited(db_session)
    user_id = user.id

    result = _run("--email", "alix@exemple.fr", "--yes")

    assert result.exit_code == 0
    assert "supprimé" in result.stdout
    db_session.expire_all()
    assert db_session.get(User, user_id) is None


def test_exactly_one_target_is_required(brancher_session, db_session):
    brancher_session(cmd)

    assert _run().exit_code == USAGE
    assert _run("--user-id", "1", "--email", "a@exemple.fr").exit_code == USAGE


def test_an_unknown_or_ambiguous_target_is_a_usage_error(brancher_session, db_session):
    brancher_session(cmd)
    user_repository.create(db_session, email="double@exemple.fr", display_name="")
    user_repository.create(db_session, email="double@exemple.fr", display_name="")

    assert _run("--user-id", "999999").exit_code == USAGE
    assert _run("--email", "personne@exemple.fr").exit_code == USAGE
    ambiguous = _run("--email", "double@exemple.fr")
    assert ambiguous.exit_code == USAGE
    assert "--user-id" in ambiguous.stdout
