"""`geocode-courses` : le seul point d'écriture des coordonnées d'une épreuve (#579).

Sort Nominatim du chemin de requête — `GET /stats/events-geo` ne fait plus
qu'un `SELECT` — en déplaçant le géocodage dans cette commande hors ligne.
`geocode_service.geocode` est monkeypatché partout ici : ces tests couvrent le
câblage CLI (stdout parsable, codes de sortie), pas Nominatim lui-même
(`tests/test_geocode_service.py`).
"""
import json
from contextlib import contextmanager
from datetime import date, timedelta

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import geocode_courses as cmd
from app.core.time import utcnow
from app.repositories import course_repository

runner = CliRunner()


def _brancher_session(monkeypatch, db_session):
    @contextmanager
    def _session():
        yield db_session

    monkeypatch.setattr(cmd, "session_scope", _session)


def _course(db_session, nom, *, geocoded_at=None):
    course = course_repository.get_or_create(
        db_session, name=nom, event_date=date(2026, 5, 1), event_type="triathlon-m"
    )
    course.geocoded_at = geocoded_at
    db_session.flush()
    return course


def _lancer(*arguments):
    return runner.invoke(app, ["geocode-courses", *arguments])


def test_geocode_toutes_les_epreuves_cibles_sort_en_0(monkeypatch, db_session):
    course = _course(db_session, "Triathlon de Nantes")
    _brancher_session(monkeypatch, db_session)
    monkeypatch.setattr(
        "app.services.geocode_service.geocode", lambda nom: (47.2181, -1.5528)
    )

    resultat = _lancer()

    assert resultat.exit_code == 0
    assert "Épreuves géocodées" in resultat.stdout
    db_session.refresh(course)
    assert course.latitude == 47.2181


def test_echec_pose_geocoded_at_sans_coordonnees(monkeypatch, db_session):
    course = _course(db_session, "Triathlon Improbable")
    _brancher_session(monkeypatch, db_session)
    monkeypatch.setattr("app.services.geocode_service.geocode", lambda nom: None)

    resultat = _lancer()

    assert resultat.exit_code == 1  # échec total : la seule épreuve ciblée a échoué
    db_session.refresh(course)
    assert course.latitude is None
    assert course.geocoded_at is not None


def test_un_echec_recent_n_est_pas_retente(monkeypatch, db_session):
    """Le cooldown (#579) : une épreuve tentée il y a une heure n'est pas reciblée."""
    _course(db_session, "Triathlon Déjà Tenté", geocoded_at=utcnow() - timedelta(hours=1))
    _brancher_session(monkeypatch, db_session)

    def _echoue_si_appele(nom):
        raise AssertionError("une épreuve en cooldown ne doit pas être retentée")

    monkeypatch.setattr("app.services.geocode_service.geocode", _echoue_si_appele)

    resultat = _lancer()

    assert resultat.exit_code == 0  # zéro cible : succès, pas échec total
    assert "Épreuves ciblées" in resultat.stdout


def test_retry_after_days_reduit_le_cooldown(monkeypatch, db_session):
    course = _course(db_session, "Triathlon Ancien Échec", geocoded_at=utcnow() - timedelta(days=2))
    _brancher_session(monkeypatch, db_session)
    monkeypatch.setattr("app.services.geocode_service.geocode", lambda nom: (1.0, 1.0))

    resultat = _lancer("--retry-after-days", "1")

    assert resultat.exit_code == 0
    db_session.refresh(course)
    assert course.latitude == 1.0


def test_dry_run_ne_persiste_rien_et_sort_en_0(monkeypatch, db_session):
    course = _course(db_session, "Triathlon Aperçu")
    _brancher_session(monkeypatch, db_session)

    def _echoue_si_appele(nom):
        raise AssertionError("--dry-run ne doit jamais appeler Nominatim")

    monkeypatch.setattr("app.services.geocode_service.geocode", _echoue_si_appele)

    resultat = _lancer("--dry-run")

    assert resultat.exit_code == 0
    assert "Triathlon Aperçu" in resultat.stdout
    db_session.refresh(course)
    assert course.latitude is None
    assert course.geocoded_at is None


def test_json_ne_met_que_le_json_sur_stdout(monkeypatch, db_session):
    _course(db_session, "Triathlon de Nantes")
    _brancher_session(monkeypatch, db_session)
    monkeypatch.setattr(
        "app.services.geocode_service.geocode", lambda nom: (47.2181, -1.5528)
    )

    resultat = _lancer("--json")

    assert resultat.exit_code == 0
    charge = json.loads(resultat.stdout.strip())
    assert charge["total"] == 1
    assert charge["geocoded"] == 1
    assert charge["errors"] == 0


def test_limit_borne_le_nombre_d_epreuves_ciblees(monkeypatch, db_session):
    for index in range(3):
        _course(db_session, f"Triathlon {index}")
    _brancher_session(monkeypatch, db_session)
    appels = []
    monkeypatch.setattr(
        "app.services.geocode_service.geocode",
        lambda nom: appels.append(nom) or (1.0, 1.0),
    )

    resultat = _lancer("--limit", "2")

    assert resultat.exit_code == 0
    assert len(appels) == 2


def test_aucune_epreuve_a_geocoder_sort_en_0(monkeypatch, db_session):
    _brancher_session(monkeypatch, db_session)

    resultat = _lancer()

    assert resultat.exit_code == 0
    assert "Épreuves ciblées" in resultat.stdout
