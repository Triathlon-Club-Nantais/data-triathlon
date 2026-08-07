"""`grant-role` : la voie d'amorçage hors ligne (#115, FR-027 à FR-030, FR-033).

Sur une installation neuve, aucun administrateur n'existe et les ressources qui
distribuent les rôles exigent elles-mêmes un pouvoir. C'est aussi **le seul
rattrapage** si l'installation se retrouve sans administrateur par un chemin que
l'application ne contrôle pas.
"""
import logging
from contextlib import contextmanager

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import grant_role as cmd
from app.models.organisation import Organisation
from app.models.role import Role
from app.repositories import user_repository, user_role_repository

runner = CliRunner()


def _brancher_session(monkeypatch, db_session):
    @contextmanager
    def _session():
        yield db_session

    monkeypatch.setattr(cmd, "session_scope", _session)


def _installation(db_session, *, organisations=("tcn",)):
    """Le semis de la migration, rejoué à la main : une organisation, trois rôles."""
    for slug in organisations:
        db_session.add(Organisation(slug=slug, name=slug.upper()))
    db_session.add_all(
        [
            Role(slug="admin", name="Administrateur", is_system=True, is_superuser=True),
            Role(slug="validator", name="Validateur", is_system=True),
            Role(slug="moderator", name="Modérateur", is_system=True),
        ]
    )
    db_session.flush()


def _utilisateur(db_session, email="contributeur@exemple.fr", nom="Prénom Nom"):
    user = user_repository.create(db_session, email=email, display_name=nom)
    db_session.flush()
    return user


def _lancer(*arguments):
    return runner.invoke(app, ["grant-role", *arguments])


def test_attribuer_un_role_sort_en_0_et_le_dit(monkeypatch, db_session):
    _installation(db_session)
    user = _utilisateur(db_session)
    _brancher_session(monkeypatch, db_session)

    resultat = _lancer("--email", "contributeur@exemple.fr", "--role", "admin")

    assert resultat.exit_code == 0
    assert "Administrateur" in resultat.stdout
    assert "Prénom Nom" in resultat.stdout
    assert "Triathlon" in resultat.stdout or "TCN" in resultat.stdout
    assert len(user_role_repository.list_for_user(db_session, user.id)) == 1


def test_reattribuer_est_un_succes_qui_ne_fait_rien(monkeypatch, db_session):
    """FR-029 — « rien à faire » et **0**, jamais une erreur.

    La commande est le rattrapage d'urgence : la relancer par acquit de
    conscience ne doit pas ressembler à un échec.
    """
    _installation(db_session)
    user = _utilisateur(db_session)
    _brancher_session(monkeypatch, db_session)
    _lancer("--email", "contributeur@exemple.fr", "--role", "admin")

    resultat = _lancer("--email", "contributeur@exemple.fr", "--role", "admin")

    assert resultat.exit_code == 0
    assert "Rien à faire" in resultat.stdout
    assert len(user_role_repository.list_for_user(db_session, user.id)) == 1


def test_une_adresse_inconnue_sort_en_2_et_explique(monkeypatch, db_session):
    """FR-028 — elle **ne crée pas d'utilisateur**.

    Un utilisateur naît d'une connexion réussie et autorisée, son identité venant
    du fournisseur. Une adresse inconnue est une erreur d'usage, pas une
    invitation à fabriquer un compte fantôme que rien ne pourra rattacher.
    """
    _installation(db_session)
    _brancher_session(monkeypatch, db_session)

    resultat = _lancer("--email", "inconnu@exemple.fr", "--role", "admin")

    assert resultat.exit_code == 2
    sortie = resultat.stdout + (resultat.stderr or "")
    assert "connexion" in sortie
    assert "allow-email" in sortie
    assert user_repository.list_all(db_session) == []


def test_un_slug_de_role_inconnu_sort_en_2_en_nommant_les_roles(monkeypatch, db_session):
    _installation(db_session)
    _utilisateur(db_session)
    _brancher_session(monkeypatch, db_session)

    resultat = _lancer("--email", "contributeur@exemple.fr", "--role", "archiviste")

    assert resultat.exit_code == 2
    sortie = resultat.stdout + (resultat.stderr or "")
    for slug in ("admin", "validator", "moderator"):
        assert slug in sortie


def test_un_role_d_une_autre_organisation_sort_en_2_en_la_nommant(
    monkeypatch, db_session
):
    """FR-008 — la règle que le SQL portable ne peut pas exprimer.

    Elle croise deux tables ; c'est un contrôle de service, et la CLI le subit
    comme l'API.
    """
    _installation(db_session, organisations=("tcn", "autre"))
    autre = db_session.query(Organisation).filter_by(slug="autre").one()
    db_session.add(
        Role(slug="archiviste", name="Archiviste", organisation_id=autre.id)
    )
    _utilisateur(db_session)
    db_session.flush()
    _brancher_session(monkeypatch, db_session)

    resultat = _lancer(
        "--email", "contributeur@exemple.fr", "--role", "archiviste",
        "--organisation", "tcn",
    )

    assert resultat.exit_code == 2
    assert "AUTRE" in resultat.stdout + (resultat.stderr or "")


def test_une_adresse_ambigue_sort_en_2_avec_les_candidats(monkeypatch, db_session):
    """FR-030 — et **ce n'est pas un cas d'école**.

    `users.email` n'est pas unique, délibérément (#114) : deux identités externes
    portant la même adresse donnent deux utilisateurs distincts. Apparier sur
    l'adresse rouvrirait la prise de contrôle par pré-inscription ; agir au
    hasard reviendrait au même en pire.
    """
    _installation(db_session)
    premier = _utilisateur(db_session, nom="Premier")
    second = _utilisateur(db_session, nom="Second")
    _brancher_session(monkeypatch, db_session)

    resultat = _lancer("--email", "contributeur@exemple.fr", "--role", "admin")

    assert resultat.exit_code == 2
    sortie = resultat.stdout + (resultat.stderr or "")
    assert str(premier.id) in sortie and str(second.id) in sortie
    assert "Premier" in sortie and "Second" in sortie
    assert user_role_repository.list_for_user(db_session, premier.id) == []


def test_une_organisation_inconnue_sort_en_2(monkeypatch, db_session):
    _installation(db_session)
    _utilisateur(db_session)
    _brancher_session(monkeypatch, db_session)

    resultat = _lancer(
        "--email", "contributeur@exemple.fr", "--role", "admin",
        "--organisation", "inexistante",
    )

    assert resultat.exit_code == 2


def test_le_rapport_sort_sur_stdout_et_les_journaux_sur_stderr(
    monkeypatch, db_session, caplog
):
    """SC-010 — contrainte dure de la CLI : **stdout reste parsable**.

    `configure_cli_logging()` envoie les journaux sur stderr ; un `logger.info`
    qui atterrirait sur stdout casserait `… | jq` de toutes les commandes du
    dépôt, celle-ci n'ayant pourtant pas de `--json`.
    """
    _installation(db_session)
    _utilisateur(db_session)
    _brancher_session(monkeypatch, db_session)

    with caplog.at_level(logging.INFO, logger="app.cli.commands.grant_role"):
        resultat = _lancer("--email", "contributeur@exemple.fr", "--role", "admin")

    assert "Rôle" in resultat.stdout
    journal = "\n".join(ligne.getMessage() for ligne in caplog.records)
    assert journal not in ("", resultat.stdout)
    assert journal not in resultat.stdout


def test_l_attribution_est_journalisee_avec_acteur_cible_role_et_sens(
    monkeypatch, db_session, caplog
):
    """FR-033 — même trace que côté API, l'acteur étant ici la ligne de commande."""
    _installation(db_session)
    user = _utilisateur(db_session)
    _brancher_session(monkeypatch, db_session)

    with caplog.at_level(logging.INFO, logger="app.cli.commands.grant_role"):
        _lancer("--email", "contributeur@exemple.fr", "--role", "admin")

    journal = "\n".join(ligne.getMessage() for ligne in caplog.records)
    assert "cli" in journal.lower()
    assert str(user.id) in journal
    assert "admin" in journal
    assert "grant" in journal.lower()


def test_la_commande_est_enregistree_dans_la_cli(monkeypatch, db_session):
    """Une commande écrite et non branchée est une commande qui n'existe pas."""
    aide = runner.invoke(app, ["--help"])

    assert "grant-role" in aide.stdout
