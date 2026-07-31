"""Tests de l'observabilité SQL (issue #89)."""
import logging

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture(autouse=True)
def _etat_propre():
    """Le drapeau de bilan est un état de module : on le remet à zéro entre
    deux tests, sinon l'ordre d'exécution devient significatif."""
    from app.core import sql_observability

    sql_observability.reset_for_tests()
    yield
    sql_observability.reset_for_tests()


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


def test_bilan_agrege_rend_un_n_plus_un_visible(engine, caplog):
    """Le test qui vaut la feature : trois exécutions de la même requête
    ressortent en une seule entrée « x3 »."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0, collect_stats=True)

    with caplog.at_level(logging.INFO, logger="app.sql"):
        with sql_observability.measure_queries("import epreuve=Test"):
            with engine.connect() as conn:
                for _ in range(3):
                    conn.execute(text("SELECT 1"))

    messages = [r.getMessage() for r in caplog.records]
    assert any("import epreuve=Test" in m and "3 requêtes" in m for m in messages)
    assert any("x3" in m and "SELECT 1" in m for m in messages)


def test_bilan_emis_meme_si_le_bloc_leve(engine, caplog):
    """Une épreuve qui plante est justement celle qu'on veut mesurer."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0, collect_stats=True)

    with caplog.at_level(logging.INFO, logger="app.sql"):
        with pytest.raises(RuntimeError):
            with sql_observability.measure_queries("import epreuve=Boom"):
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                raise RuntimeError("boom")

    assert any("import epreuve=Boom" in r.getMessage() for r in caplog.records)


def test_bilan_eteint_est_un_no_op(engine, caplog):
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0, collect_stats=False)

    with caplog.at_level(logging.DEBUG, logger="app.sql"):
        with sql_observability.measure_queries("rien") as stats:
            assert stats is None
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

    assert caplog.records == []


def test_unite_sans_requete_n_emet_pas_de_bilan(engine, caplog):
    """Une requête HTTP qui ne touche pas la base ne doit pas polluer les logs."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0, collect_stats=True)

    with caplog.at_level(logging.DEBUG, logger="app.sql"):
        with sql_observability.measure_queries("GET /health"):
            pass

    assert caplog.records == []


def test_imbrication_la_plus_proche_gagne(engine, caplog):
    """Règle écrite plutôt que découverte : aucune sommation vers l'englobante."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0, collect_stats=True)

    with caplog.at_level(logging.INFO, logger="app.sql"):
        with sql_observability.measure_queries("externe") as dehors:
            with sql_observability.measure_queries("interne"):
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
            assert dehors.count == 0


def test_bilan_ne_contient_ni_valeur_liee_ni_retour_a_la_ligne(engine, caplog):
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0, collect_stats=True)

    with caplog.at_level(logging.INFO, logger="app.sql"):
        with sql_observability.measure_queries("fuite"):
            with engine.connect() as conn:
                conn.execute(text("SELECT :valeur"), {"valeur": "LEMÉE"})

    assert caplog.records
    assert all("LEMÉE" not in r.getMessage() for r in caplog.records)
    assert all("\n" not in r.getMessage() for r in caplog.records)


def test_label_avec_retour_a_la_ligne_normalise(engine, caplog):
    """Le label, qui vient de la base, peut contenir un retour à la ligne.
    Il est normalisé avant journalisation pour ne pas casser le JSON."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0, collect_stats=True)

    with caplog.at_level(logging.INFO, logger="app.sql"):
        with sql_observability.measure_queries("TRIATHLON\nOléron 2024"):
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

    assert caplog.records
    # Le label normalisé remplace le \n par un espace
    assert any("TRIATHLON Oléron 2024" in r.getMessage() for r in caplog.records)
    # Aucun \n dans aucun enregistrement
    assert all("\n" not in r.getMessage() for r in caplog.records)


def test_engine_applicatif_est_instrumente():
    """`database.py` doit appeler `install()` sur son engine : sans ce
    branchement, tout le reste ne mesure rien en production.

    On interroge `is_installed` et non le registre d'événements de SQLAlchemy :
    `event.contains()` réclame la fonction écoutante exacte, qu'on n'expose pas,
    et inspecter son registre interne serait se lier à un détail privé.

    Le seuil par défaut étant de 100 ms, on ne peut pas vérifier le branchement
    par un `SELECT 1` sur SQLite : il ne le franchira jamais. Et recharger
    `database` avec un seuil forcé bas reconstruirait `Base`, laissant les
    modèles liés à l'ancienne — ce qui casserait la suite entière.
    """
    from app.core.database import engine
    from app.core.sql_observability import is_installed

    assert is_installed(engine) is True
