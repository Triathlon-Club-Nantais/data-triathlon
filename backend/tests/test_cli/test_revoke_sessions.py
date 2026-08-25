"""`revoke-sessions` : la révocation d'urgence (#169).

Le geste que la procédure SQL rendait impraticable — ouvrir `psql` sur Supabase
à la main, sous stress, en production. Comme `allow-email` et `grant-role`, elle
contourne délibérément la garde de pouvoir : sans session, il n'y a pas d'acteur
dont comparer les pouvoirs, et l'accès au serveur *est* le privilège.
"""

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import revoke_sessions as cmd
from app.cli.commands.revoke_sessions import USAGE
from app.repositories import user_repository
from app.services.auth import session as session_service

runner = CliRunner()


def _compte(db, email):
    user = user_repository.create(db, email=email, display_name="Prénom Nom")
    db.flush()
    return user, session_service.open_for(db, user)


def _lancer(*arguments, entree=None):
    return runner.invoke(app, ["revoke-sessions", *arguments], input=entree)


def test_revoquer_une_adresse_sort_en_0_et_compte_les_deux_unites(brancher_session, db_session):
    brancher_session(cmd)
    _, jeton = _compte(db_session, "fuite@exemple.fr")

    resultat = _lancer("--email", "fuite@exemple.fr")

    assert resultat.exit_code == 0
    assert "1 session" in resultat.stdout
    assert "1 compte" in resultat.stdout
    assert session_service.resolve(db_session, jeton) is None


def test_revoquer_une_adresse_ne_demande_aucune_confirmation(brancher_session, db_session):
    """`--yes` ne garde que `--all`.

    Fermer les sessions d'une personne se répare par une reconnexion ; fermer
    celles de tout le club, non — et c'est le seul des deux gestes qui déconnecte
    aussi celui qui le lance.
    """
    brancher_session(cmd)
    _compte(db_session, "fuite@exemple.fr")

    resultat = _lancer("--email", "fuite@exemple.fr")

    assert resultat.exit_code == 0
    assert "?" not in resultat.stdout


def test_revoquer_tout_avec_yes_ferme_toutes_les_sessions(brancher_session, db_session):
    brancher_session(cmd)
    _, une = _compte(db_session, "une@exemple.fr")
    _, deux = _compte(db_session, "deux@exemple.fr")

    resultat = _lancer("--all", "--yes")

    assert resultat.exit_code == 0
    assert "2 session" in resultat.stdout
    assert "2 compte" in resultat.stdout
    assert session_service.resolve(db_session, une) is None
    assert session_service.resolve(db_session, deux) is None


def test_revoquer_tout_demande_confirmation_et_un_refus_ne_ferme_rien(brancher_session, db_session):
    """Annuler n'est pas une panne : code 0, comme `reset_db.py`."""
    brancher_session(cmd)
    _, jeton = _compte(db_session, "une@exemple.fr")

    resultat = _lancer("--all", entree="n\n")

    assert resultat.exit_code == 0
    assert "Annulé" in resultat.stdout
    assert session_service.resolve(db_session, jeton) is not None


def test_revoquer_tout_confirme_interactivement_ferme_bien(brancher_session, db_session):
    brancher_session(cmd)
    _, jeton = _compte(db_session, "une@exemple.fr")

    resultat = _lancer("--all", entree="y\n")

    assert resultat.exit_code == 0
    assert session_service.resolve(db_session, jeton) is None


def test_sans_cible_est_une_erreur_d_usage(brancher_session, db_session):
    """Un `revoke-sessions` nu ne doit pas retomber sur `--all` par défaut."""
    brancher_session(cmd)
    _, jeton = _compte(db_session, "une@exemple.fr")

    resultat = _lancer()

    assert resultat.exit_code == 2
    assert session_service.resolve(db_session, jeton) is not None


def test_les_deux_cibles_a_la_fois_est_une_erreur_d_usage(brancher_session, db_session):
    """Deux modes, pas des filtres à composer — même parti pris que `rescrape-db`."""
    brancher_session(cmd)
    _, jeton = _compte(db_session, "une@exemple.fr")

    resultat = _lancer("--all", "--email", "une@exemple.fr", "--yes")

    assert resultat.exit_code == 2
    assert session_service.resolve(db_session, jeton) is not None


def test_une_adresse_sans_compte_le_dit_au_lieu_de_compter_zero(brancher_session, db_session):
    """« 0 session fermée » vaut pour `--all`, jamais pour une adresse.

    Ce compte rendu confond « l'adresse est bonne, aucune session ouverte » et
    « vous avez mal tapé » — précisément la confusion que `grant-role` refuse,
    sur la même liste rendue par `find_by_email`. Sous stress, l'exploitant lit
    une ligne verte et croit le jeton fuité mort.
    """
    brancher_session(cmd)
    _compte(db_session, "existe@exemple.fr")

    resultat = _lancer("--email", "faute-de-frappe@exemple.fr")

    assert resultat.exit_code == USAGE
    assert "aucun compte" in resultat.stdout.lower()


def test_une_adresse_vide_est_une_erreur_d_usage(brancher_session):
    """`--email ""` ne doit pas se faufiler en cible valide."""
    brancher_session(cmd)

    assert _lancer("--email", "  ").exit_code == USAGE


def test_une_adresse_connue_sans_session_ouverte_reste_un_succes(brancher_session, db_session):
    """Là, « 0 session » est bien un compte rendu : le compte existe."""
    brancher_session(cmd)
    user = user_repository.create(db_session, email="dort@exemple.fr")
    db_session.flush()

    resultat = _lancer("--email", "dort@exemple.fr")

    assert user.id is not None
    assert resultat.exit_code == 0
    assert "0 session" in resultat.stdout


def test_rien_a_fermer_avec_all_le_dit_sans_echouer(brancher_session):
    """« 0 session » est un compte rendu, pas un échec — l'exploitant doit
    pouvoir distinguer un geste utile d'un geste dans le vide."""
    brancher_session(cmd)

    resultat = _lancer("--all", "--yes")

    assert resultat.exit_code == 0
    assert "0 session" in resultat.stdout
