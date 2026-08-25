"""`allow-email` : la voie d'amorçage de la liste d'autorisation (#170, FR-014).

Sur une installation neuve, la liste est vide : personne ne peut ouvrir de
session, donc personne ne peut ouvrir le back-office pour autoriser quelqu'un.
Cette commande rompt le cercle. Elle contourne délibérément la garde de pouvoir,
comme `grant-role` — sans session, il n'y a pas d'acteur dont comparer les
pouvoirs, et l'accès au serveur *est* le privilège.
"""

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import allow_email as cmd
from app.repositories import allowed_email_repository, user_repository

runner = CliRunner()


def _lancer(*arguments):
    return runner.invoke(app, ["allow-email", *arguments])


def test_inscrire_une_adresse_sort_en_0_et_le_dit(brancher_session, db_session):
    brancher_session(cmd)

    resultat = _lancer("--email", " Vous@Exemple.FR ")

    assert resultat.exit_code == 0
    assert "vous@exemple.fr" in resultat.stdout
    assert allowed_email_repository.exists(db_session, "vous@exemple.fr")


def test_reinscrire_sort_en_0_sans_doublon(brancher_session, db_session):
    brancher_session(cmd)
    _lancer("--email", "vous@exemple.fr")

    resultat = _lancer("--email", "VOUS@EXEMPLE.FR")

    assert resultat.exit_code == 0
    assert "rien à faire" in resultat.stdout.lower()
    assert len(allowed_email_repository.list_all(db_session)) == 1


def test_une_adresse_mal_formee_sort_en_2_sans_rien_ecrire(brancher_session, db_session):
    brancher_session(cmd)

    resultat = _lancer("--email", "pas-une-adresse")

    assert resultat.exit_code == 2
    assert allowed_email_repository.list_all(db_session) == []


def test_reinscrire_rouvre_les_comptes_et_le_dit(brancher_session, db_session):
    """La symétrie de l'écran vaut pour la CLI : elles passent par le même service."""
    brancher_session(cmd)
    cible = user_repository.create(db_session, email="cible@exemple.fr")
    cible.is_active = False
    db_session.flush()

    resultat = _lancer("--email", "cible@exemple.fr")

    assert resultat.exit_code == 0
    assert "1" in resultat.stdout and "réactivé" in resultat.stdout
    assert cible.is_active is True
