"""Tests de l'observabilité SQL (issue #89)."""
import logging

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture
def engine():
    """Engine SQLite jetable — `install()` prend l'engine en argument, donc
    instrumenter celui-ci n'affecte aucun autre test."""
    eng = create_engine("sqlite://")
    yield eng
    eng.dispose()


def test_requete_au_dessus_du_seuil_sort_en_warning(engine, caplog):
    """Seuil à 0 ms : toute requête est « lente », donc journalisée."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0.0001, collect_stats=False)

    with caplog.at_level(logging.WARNING, logger="app.sql"):
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    assert any("SELECT 1" in r.message for r in caplog.records)
    assert all(r.levelno == logging.WARNING for r in caplog.records)


def test_requete_sous_le_seuil_ne_journalise_rien(engine, caplog):
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=60_000, collect_stats=False)

    with caplog.at_level(logging.DEBUG, logger="app.sql"):
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    assert caplog.records == []


def test_seuil_nul_et_bilan_eteint_ne_pose_aucun_listener(engine, caplog):
    """L'échappatoire « coût strictement nul » : rien n'est posé du tout."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0, collect_stats=False)

    assert sql_observability.is_installed(engine) is False
    with caplog.at_level(logging.DEBUG, logger="app.sql"):
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    assert caplog.records == []


def test_install_est_idempotent(engine, caplog):
    """Deux appels ne doivent pas doubler les listeners — sinon chaque requête
    serait comptée et journalisée deux fois."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0.0001, collect_stats=False)
    sql_observability.install(engine, slow_query_ms=0.0001, collect_stats=False)

    assert sql_observability.is_installed(engine) is True
    with caplog.at_level(logging.WARNING, logger="app.sql"):
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    lentes = [r for r in caplog.records if "SELECT 1" in r.getMessage()]
    assert len(lentes) == 1


def test_aucun_parametre_lie_ne_fuit_dans_les_logs(engine, caplog):
    """Garde de données personnelles : les valeurs liées portent des noms
    d'athlètes et des libellés de club. Seule la forme paramétrée est journalisée.

    Test de non-régression à part entière : c'est la seule chose qui empêche des
    noms de membres du club de partir dans les logs Render.
    """
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0.0001, collect_stats=False)

    with caplog.at_level(logging.WARNING, logger="app.sql"):
        with engine.connect() as conn:
            conn.execute(text("SELECT :valeur"), {"valeur": "LEMÉE"})

    assert caplog.records, "la requête aurait dû être journalisée"
    assert all("LEMÉE" not in r.getMessage() for r in caplog.records)


def test_aucun_message_ne_contient_de_retour_a_la_ligne(engine, caplog):
    """Le formateur JSON d'app.core.logging construit son objet à la main :
    un retour à la ligne dans le message casserait le JSON."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0.0001, collect_stats=False)

    with caplog.at_level(logging.WARNING, logger="app.sql"):
        with engine.connect() as conn:
            conn.execute(text("SELECT 1\n  UNION SELECT 2"))

    assert caplog.records
    assert all("\n" not in r.getMessage() for r in caplog.records)


def test_normalize_sql_compacte_et_tronque():
    from app.core.sql_observability import normalize_sql

    assert normalize_sql("SELECT   1\n  FROM t") == "SELECT 1 FROM t"
    long = "SELECT " + "x" * 500
    assert len(normalize_sql(long)) == 201  # 200 caractères + l'ellipse
    assert normalize_sql(long).endswith("…")
