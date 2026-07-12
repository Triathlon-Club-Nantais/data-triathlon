"""Le logging de la CLI ne doit JAMAIS toucher stdout.

Contrainte dure du projet : stdout ne porte que le rapport final — et, avec
`--json`, rien d'autre que la ligne JSON (`… --json | jq`). Jusqu'ici elle tenait
par omission (la CLI n'appelait pas `setup_logging()`, les logs partaient au
`lastResort`, soit stderr). Ajouter `setup_logging()` — dont le défaut est stdout —
au point d'entrée aurait suffi à la casser dès la première épreuve en échec
(`batch.logger.warning`), sans qu'aucun test ne l'attrape. D'où ces tests.
"""
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app import cli
from app.core import logging as app_logging

BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture
def logging_isole(monkeypatch):
    """Ces tests reconfigurent le root logger : ils doivent le rendre intact."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    monkeypatch.setattr(app_logging, "_CONFIGURED", False)
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def test_les_logs_de_la_cli_ne_partent_pas_sur_stdout(logging_isole, capsys):
    cli.configure_cli_logging()

    # Le log qu'émettrait `batch.run_batch` sur une épreuve en échec, en plein batch.
    logging.getLogger("app.services.batch").warning("Échec import https://exemple.test : boum")

    out, err = capsys.readouterr()
    assert "boum" not in out  # stdout doit rester parsable
    assert "boum" in err  # …mais l'opérateur voit quand même l'échec, horodaté
    assert logging.getLogger().handlers[0].stream is sys.stderr


def test_setup_logging_ecrit_toujours_sur_stdout_par_defaut(logging_isole, capsys):
    """Le défaut ne change pas : l'API web (`create_app`) garde son comportement."""
    app_logging.setup_logging()

    logging.getLogger("app.main").info("Application initialisée")

    out, _ = capsys.readouterr()
    assert "Application initialisée" in out


def test_json_reste_parsable_sur_le_vrai_point_d_entree(tmp_path):
    """Pin de bout en bout, sur le vrai point d'entrée `python -m app.cli`.

    Le process configure bien le logging (LOG_LEVEL=DEBUG, le plus bavard), et
    stdout ne porte malgré tout QUE la ligne JSON : rapport texte et logs sont
    sur stderr. C'est la contrainte `… --json | jq`, vérifiée sur le binaire réel.
    """
    import app.models  # noqa: F401 — enregistre les tables sur Base.metadata
    from app.core.database import Base

    db = tmp_path / "cli.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(bind=engine)
    engine.dispose()

    proc = subprocess.run(
        [sys.executable, "-m", "app.cli", "rescrape-db", "--dry-run", "--json"],
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db}", "LOG_LEVEL": "DEBUG"},
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 0, proc.stderr
    charge = json.loads(proc.stdout)  # tout stdout, pas seulement sa fin
    assert charge["total"] == 0  # base vierge : aucune épreuve à re-scraper
    assert "RESCRAPE DB" in proc.stderr  # le rapport humain, lui, reste visible
