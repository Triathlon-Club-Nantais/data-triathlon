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
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        # Les instrumentations OTel sont globales et rémanentes : sans ce
        # désarmement, ce test contamine toute la suite.
        SQLAlchemyInstrumentor().uninstrument()
        eng.dispose()


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
