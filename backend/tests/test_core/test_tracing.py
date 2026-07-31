"""Tests du socle OpenTelemetry (issue #89)."""
import builtins

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture(autouse=True)
def _etat_propre():
    from app.core import tracing

    tracing.shutdown_tracing()
    yield
    tracing.shutdown_tracing()


def test_eteint_ne_charge_aucun_paquet_otel(monkeypatch):
    """Éteint, le coût doit être strictement nul — pas même un import.

    On rend l'import fatal plutôt que d'inspecter `sys.modules`, qu'un autre
    test aurait déjà peuplé.
    """
    from app.core import tracing

    vrai_import = builtins.__import__

    def _interdit(name, *args, **kwargs):
        if name.startswith("opentelemetry"):
            raise AssertionError(f"import OTel interdit quand éteint : {name}")
        return vrai_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _interdit)

    tracing.setup_tracing(enabled=False, engine=None)

    assert tracing.current_provider() is None


def test_allume_produit_un_span_sql(monkeypatch):
    """Allumé, une requête doit produire un span. On lit le provider du module,
    jamais le provider global : `trace.set_tracer_provider()` n'accepte qu'un
    seul appel par process, ce qui rendrait le test dépendant de son ordre.
    """
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from app.core import tracing

    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    eng = create_engine("sqlite://")
    tracing.setup_tracing(enabled=True, engine=eng)
    try:
        exporter = InMemorySpanExporter()
        tracing.current_provider().add_span_processor(SimpleSpanProcessor(exporter))

        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))

        assert exporter.get_finished_spans(), "aucun span SQL produit"
    finally:
        # Le désarmement de l'instrumentation SQLAlchemy est désormais à la
        # charge de `shutdown_tracing`, rappelé par la fixture `_etat_propre`
        # en teardown — plus besoin de le faire à la main ici.
        eng.dispose()


def test_cycle_complet_reinstrumente_apres_shutdown(monkeypatch):
    """`shutdown_tracing` doit désinstrumenter, pas seulement fermer le provider.

    `BaseInstrumentor` est un singleton par classe : sans désinstrumentation
    symétrique, un second `setup_tracing` (nouvel engine) redevient un no-op
    muet et perd tous ses spans, en silence — c'est exactement le cas d'un
    process CLI qui enchaînerait deux batches.
    """
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from app.core import tracing

    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")

    eng1 = create_engine("sqlite://")
    tracing.setup_tracing(enabled=True, engine=eng1)
    try:
        exporter1 = InMemorySpanExporter()
        tracing.current_provider().add_span_processor(SimpleSpanProcessor(exporter1))
        with eng1.connect() as conn:
            conn.execute(text("SELECT 1"))
        assert exporter1.get_finished_spans(), "aucun span SQL produit (premier cycle)"
    finally:
        tracing.shutdown_tracing()
        eng1.dispose()

    eng2 = create_engine("sqlite://")
    tracing.setup_tracing(enabled=True, engine=eng2)
    try:
        exporter2 = InMemorySpanExporter()
        tracing.current_provider().add_span_processor(SimpleSpanProcessor(exporter2))
        with eng2.connect() as conn:
            conn.execute(text("SELECT 1"))
        assert exporter2.get_finished_spans(), "aucun span SQL produit (second cycle)"
    finally:
        eng2.dispose()


def test_exporter_console_ecrit_sur_stderr():
    """Contrainte dure de la CLI : stdout ne porte que le rapport et la ligne
    `--json`. `ConsoleSpanExporter` écrit sur **stdout** par défaut — le socle
    doit donc le construire avec `out=sys.stderr`, faute de quoi un span imprimé
    casserait `… --json | jq`.
    """
    import sys

    from app.core import tracing

    exporter = tracing._build_exporter("console")
    assert exporter.out is sys.stderr


def test_exporter_none_ne_rend_rien():
    from app.core import tracing

    assert tracing._build_exporter("none") is None


def test_cli_expose_demarrage_et_arret_du_tracage():
    """Un batch est un process court : sans arrêt explicite, les spans du
    dernier import ne sont jamais exportés."""
    from app import cli

    assert callable(cli.configure_cli_tracing)
    assert callable(cli.shutdown_cli_tracing)


def test_cli_eteint_ne_pose_rien(monkeypatch):
    from app import cli
    from app.core import tracing
    from app.core.config import get_settings

    monkeypatch.setenv("OTEL_ENABLED", "false")
    get_settings.cache_clear()
    try:
        cli.configure_cli_tracing()
        assert tracing.current_provider() is None
    finally:
        get_settings.cache_clear()


def test_requete_http_produit_un_span_fastapi(monkeypatch):
    """Vérifie la branche FastAPI, jusqu'ici jamais exercée : `instrument_app`
    doit effectivement produire un span **d'origine FastAPI** pour une requête
    HTTP réelle, contre les versions de FastAPI et
    d'opentelemetry-instrumentation-fastapi réellement installées.

    L'assertion porte sur la provenance du span (`instrumentation_scope.name`),
    pas seulement sur son existence : `setup_tracing(app=…, engine=…)`
    instrumente aussi l'engine, et la route interrogée exécute toujours un
    `SELECT` — un simple `get_finished_spans()` non vide resterait donc vert
    même si `instrument_app` ne faisait plus rien.

    L'application se branche sur un engine SQLite **en mémoire**, jamais sur
    le fichier `triathlon.db` de développement (absent d'un checkout CI
    propre) : même motif que
    `test_sql_observability.test_middleware_compte_les_requetes_d_un_appel_http`.

    `app.main` porte un `app = create_app()` **de module**, exécuté à son tout
    premier import. `setup_tracing` est idempotent par process
    (`_provider is not None` court-circuite tout appel suivant) : si cet
    import survenait pendant la fenêtre où OTel est activé, il consommerait
    l'unique cycle d'instrumentation au profit de l'`app` de module — invisible
    ici — et notre `application` de test n'en recevrait aucune, sans qu'aucune
    assertion ne le révèle autrement que par ce test lui-même échouant à tort.
    D'où l'import de `create_app` **avant** d'activer `OTEL_ENABLED` : le tout
    premier import (s'il a lieu ici) s'exécute donc à froid, et notre appel
    explicite plus bas reste le seul consommateur du cycle.
    """
    from fastapi.testclient import TestClient
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import app.models  # noqa: F401 — enregistre les tables sur Base.metadata
    from app.core import tracing
    from app.core.config import get_settings
    from app.core.database import Base, get_db
    from app.main import create_app  # voir docstring : importé avant l'activation d'OTel

    # `create_app()` appelle `setup_logging()`, qui vide les handlers du root
    # logger. Sans conséquence ici : ce test n'inspecte que des spans en
    # mémoire, jamais `caplog`.
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    get_settings.cache_clear()

    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    try:
        Base.metadata.create_all(bind=eng)
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=eng)

        application = create_app()

        def _override_get_db():
            db = session_factory()
            try:
                yield db
            finally:
                db.close()

        application.dependency_overrides[get_db] = _override_get_db

        exporter = InMemorySpanExporter()
        tracing.current_provider().add_span_processor(SimpleSpanProcessor(exporter))

        with TestClient(application) as client:
            reponse = client.get("/api/v1/athletes?page_size=1")

        assert reponse.status_code == 200
        spans_fastapi = [
            s
            for s in exporter.get_finished_spans()
            if s.instrumentation_scope.name == "opentelemetry.instrumentation.fastapi"
        ]
        assert spans_fastapi, "aucun span d'origine FastAPI produit"
    finally:
        tracing.shutdown_tracing()
        Base.metadata.drop_all(bind=eng)
        eng.dispose()
        get_settings.cache_clear()
