"""La commande `club-labels` : le filet contre l'oubli silencieux d'une variante (#76)."""
import json
from contextlib import contextmanager
from datetime import date

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import club_labels as cmd
from app.repositories import athlete_repository, course_repository, participation_repository

runner = CliRunner()


def _peupler(db):
    course = course_repository.get_or_create(
        db, name="Tri Z", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    libelles = [
        "TRI CLUB NANTAIS", "TRI CLUB NANTAIS", "TRI CLUB NANTAIS",
        "RACING CLUB NANTAIS *", "RACING CLUB NANTAIS *",
        "ASPTT RENNES",
    ]
    for index, libelle in enumerate(libelles):
        athlete = athlete_repository.get_or_create(db, nom=f"NOM{index}", prenom="Test")
        participation_repository.create(
            db, athlete_id=athlete.id, course_id=course.id,
            bib_number=str(index), club=libelle,
        )
    db.flush()


def _brancher_session(monkeypatch, db_session):
    _peupler(db_session)

    @contextmanager
    def _session():
        yield db_session

    monkeypatch.setattr(cmd, "session_scope", _session)


def test_rapport_texte_trie_et_marque_les_libelles(monkeypatch, db_session):
    _brancher_session(monkeypatch, db_session)

    result = runner.invoke(app, ["club-labels"])

    assert result.exit_code == 0
    lignes = [ligne for ligne in result.stdout.splitlines() if "NANTAIS" in ligne or "RENNES" in ligne]
    assert "3  ✓  TRI CLUB NANTAIS" in lignes[0]
    assert "2  ✗  RACING CLUB NANTAIS *" in lignes[1]
    assert "1  ✗  ASPTT RENNES" in lignes[2]


def test_like_restreint_aux_libelles_contenant_le_fragment(monkeypatch, db_session):
    _brancher_session(monkeypatch, db_session)

    result = runner.invoke(app, ["club-labels", "--like", "rennes"])

    assert result.exit_code == 0
    assert "ASPTT RENNES" in result.stdout
    assert "NANTAIS" not in result.stdout


def test_json_ne_met_que_le_json_sur_stdout(monkeypatch, db_session):
    _brancher_session(monkeypatch, db_session)

    result = runner.invoke(app, ["club-labels", "--json"])

    assert result.exit_code == 0
    charge = json.loads(result.stdout.strip())
    assert charge["total_labels"] == 3
    assert charge["tcn_labels"] == 1
    assert charge["tcn_participations"] == 3
    assert charge["labels"][0] == {
        "club": "TRI CLUB NANTAIS", "participations": 3, "is_tcn": True
    }
