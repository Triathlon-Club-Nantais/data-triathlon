"""Socle OpenTelemetry — traces seules, éteint par défaut (issue #89).

Aucun collecteur n'est hébergé à ce jour : ce module est posé pour que le
branchement futur tienne en deux variables d'environnement et zéro code. Il ne
remplace pas `sql_observability` — OTel exporte, il n'alerte pas ; le seuil de
lenteur reste l'affaire des listeners.

Les imports `opentelemetry.*` vivent **dans** les fonctions : éteint, aucun
paquet OTel n'est chargé.

Configuration par les variables standard. `OTEL_SERVICE_NAME` est lu par
`Resource.create()` et `OTEL_EXPORTER_OTLP_ENDPOINT` par l'exporter OTLP :
rien à écrire pour elles. `OTEL_TRACES_EXPORTER`, en revanche, n'est interprété
que par le lanceur `opentelemetry-instrument`, que nous n'utilisons pas — c'est
donc `_build_exporter` qui la lit, en respectant la sémantique standard.
"""
import logging
import os
import sys

logger = logging.getLogger(__name__)

_provider = None


def current_provider():
    """Le `TracerProvider` du module, ou `None` s'il n'est pas allumé.

    Les instrumentations le reçoivent explicitement : les spans ne dépendent
    donc jamais du provider global, dont `set_tracer_provider()` n'accepte
    qu'un seul réglage par process.
    """
    return _provider


def _build_exporter(name: str):
    """Exporter correspondant à `OTEL_TRACES_EXPORTER` — `None` pour « none »."""
    if name == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        # Sur stderr, jamais stdout : la CLI y réserve le rapport et la ligne
        # `--json`, qu'un span imprimé casserait (`… --json | jq`).
        return ConsoleSpanExporter(out=sys.stderr)
    if name == "otlp":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        # Lit OTEL_EXPORTER_OTLP_ENDPOINT lui-même.
        return OTLPSpanExporter()
    return None


def setup_tracing(*, enabled: bool, app=None, engine=None) -> None:
    """Construit le provider et pose les instrumentations demandées.

    No-op si `enabled` est faux, et idempotent : un second appel ne reconstruit
    rien. `app` et `engine` sont facultatifs — la CLI n'a pas d'app.
    """
    global _provider
    if not enabled or _provider is not None:
        return

    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create())
    exporter = _build_exporter(os.getenv("OTEL_TRACES_EXPORTER", "none").strip().lower())
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    _provider = provider

    if engine is not None:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)
    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

    logger.info("Traçage OpenTelemetry actif (exporter=%s)", exporter or "none")


def shutdown_tracing() -> None:
    """Vide les spans en attente.

    Indispensable en CLI : un batch est un process court et le
    `BatchSpanProcessor` exporte de façon différée — sans cet appel, les spans
    du dernier import sont perdus.
    """
    global _provider
    if _provider is not None:
        _provider.shutdown()
        _provider = None
