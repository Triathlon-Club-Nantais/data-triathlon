"""Rapports de violation CSP envoyés par les navigateurs (#1168).

Deux formats coexistent : `report-uri` (`application/csp-report`, un objet
`{"csp-report": {...}}` par violation, le seul que Firefox envoie) et
`report-to` (`application/reports+json`, une liste de rapports de tous types,
regroupés par le navigateur). Seules les violations CSP sont retenues, et
elles ne vont que dans les logs : la phase d'observation de #570 n'a besoin de
rien d'autre.

Le contenu vient d'une route anonyme, donc de n'importe qui : chaque valeur est
tronquée et ramenée sur une ligne avant d'être journalisée, pour qu'un rapport
forgé ne puisse ni inonder les logs ni y fabriquer de fausses lignes.
"""
import json
import logging
import re

from app.core.exceptions import CspReportTooLargeError, InvalidCspReportError

logger = logging.getLogger(__name__)

#: Un lot `report-to` regroupe plusieurs rapports ; 64 Kio en laisse passer des
#: dizaines, et borne ce qu'un appel peut faire lire au serveur.
MAX_REPORT_BYTES = 64 * 1024

_MAX_VALUE_CHARS = 200
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]+")


def log_reports(raw: bytes) -> int:
    """Journalise les violations CSP de `raw` et renvoie leur nombre."""
    if len(raw) > MAX_REPORT_BYTES:
        raise CspReportTooLargeError()
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidCspReportError() from exc

    violations = _violations(payload)
    for violation in violations:
        logger.warning(
            "CSP violation directive=%s blocked=%s document=%s source=%s:%s disposition=%s",
            *(_clean(value) for value in violation),
        )
    return len(violations)


def _violations(payload: object) -> list[tuple[object, ...]]:
    if isinstance(payload, dict) and isinstance(payload.get("csp-report"), dict):
        report = payload["csp-report"]
        return [(
            report.get("effective-directive") or report.get("violated-directive"),
            report.get("blocked-uri"),
            report.get("document-uri"),
            report.get("source-file"),
            report.get("line-number"),
            report.get("disposition"),
        )]
    if isinstance(payload, list):
        return [
            (
                body.get("effectiveDirective"),
                body.get("blockedURL"),
                body.get("documentURL"),
                body.get("sourceFile"),
                body.get("lineNumber"),
                body.get("disposition"),
            )
            for item in payload
            if isinstance(item, dict)
            and item.get("type") == "csp-violation"
            and isinstance(body := item.get("body"), dict)
        ]
    return []


def _clean(value: object) -> str:
    return _CONTROL_CHARS.sub(" ", str(value if value is not None else "-"))[:_MAX_VALUE_CHARS]
