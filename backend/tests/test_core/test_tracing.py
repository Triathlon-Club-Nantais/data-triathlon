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


def test_requete_http_produit_un_span(monkeypatch):
    """Vérifie la branche FastAPI, jusqu'ici jamais exercée : `instrument_app`
    doit effectivement produire un span pour une requête HTTP réelle, contre
    les versions de FastAPI et d'opentelemetry-instrumentation-fastapi
    réellement installées.
    """
    from fastapi.testclient import TestClient
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from app.core import tracing

    # `create_app()` appelle `setup_logging()`, qui vide les handlers du root
    # logger — dont celui que `caplog` y a posé. Sans conséquence ici, ce test
    # n'inspecte que des spans en mémoire, jamais `caplog` : la précaution de
    # `test_middleware_compte_les_requetes_d_un_appel_http` ne s'applique pas.
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")

    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        from app.main import create_app

        application = create_app()

        exporter = InMemorySpanExporter()
        tracing.current_provider().add_span_processor(SimpleSpanProcessor(exporter))

        with TestClient(application) as client:
            reponse = client.get("/api/v1/athletes?page_size=1")

        assert reponse.status_code == 200
        assert exporter.get_finished_spans(), "aucun span HTTP produit"
    finally:
        tracing.shutdown_tracing()
        get_settings.cache_clear()
