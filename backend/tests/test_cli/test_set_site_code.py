"""`set-site-code` : poser le code d'accès au site sans session (#929).

Sur une installation neuve, aucune ligne `site_access_config` n'existe : la garde
fail-closed ferme toutes les pages, et le seul écran qui pose le code exige une
session admin, donc une application OAuth. Cette commande rompt le cercle, sur le
patron d'`allow-email` et `grant-role`.
"""

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import set_site_code as cmd
from app.repositories import site_access_config_repository
from app.services import shared_password

runner = CliRunner()


def _lancer(*arguments):
    return runner.invoke(app, ["set-site-code", *arguments])


def _verifie(db_session, code: str) -> bool:
    config = site_access_config_repository.get_config(db_session)
    return shared_password.verify_password(
        code, password_hash=config.password_hash, password_salt=config.password_salt
    )


def test_poser_un_code_saisi_sur_une_base_neuve(brancher_session, db_session):
    brancher_session(cmd)

    resultat = _lancer("--code", "un-code-de-demo")

    assert resultat.exit_code == 0
    assert _verifie(db_session, "un-code-de-demo")
    config = site_access_config_repository.get_config(db_session)
    assert config.updated_by_user_id is None


def test_sans_code_un_code_est_genere_et_affiche(brancher_session, db_session):
    brancher_session(cmd)

    resultat = _lancer()

    assert resultat.exit_code == 0
    code = resultat.stdout.strip().splitlines()[-1].strip()
    assert _verifie(db_session, code)


def test_un_code_trop_court_sort_en_2_sans_rien_ecrire(brancher_session, db_session):
    brancher_session(cmd)

    resultat = _lancer("--code", "court")

    assert resultat.exit_code == 2
    assert site_access_config_repository.get_config(db_session) is None


def test_remplacer_le_code_invalide_les_sessions_ouvertes(brancher_session, db_session):
    brancher_session(cmd)
    _lancer("--code", "premier-code-local")
    ancien_secret = site_access_config_repository.get_config(db_session).session_secret

    _lancer("--code", "second-code-local")

    config = site_access_config_repository.get_config(db_session)
    assert config.session_secret != ancien_secret
    assert _verifie(db_session, "second-code-local")
