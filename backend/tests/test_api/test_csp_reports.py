"""CSP violation reports sent by browsers (#1168)."""
import json
import logging

import pytest

from app.api.deps import CSP_REPORT_RATE_LIMIT_MAX_PER_WINDOW, require_site_access
from app.main import app
from app.services.csp_report import MAX_REPORT_BYTES

URL = "/api/v1/csp-reports"

REPORT_URI_BODY = {
    "csp-report": {
        "document-uri": "https://data.triathlon-club-nantais.com/ajouter",
        "violated-directive": "script-src-elem",
        "effective-directive": "script-src",
        "blocked-uri": "eval",
        "source-file": "https://data.triathlon-club-nantais.com/_next/static/chunks/a.js",
        "line-number": 1,
        "disposition": "report",
    }
}

REPORT_TO_BODY = [
    {
        "type": "csp-violation",
        "age": 10,
        "url": "https://data.triathlon-club-nantais.com/resultats",
        "body": {
            "documentURL": "https://data.triathlon-club-nantais.com/resultats",
            "effectiveDirective": "style-src-elem",
            "blockedURL": "inline",
            "sourceFile": "https://data.triathlon-club-nantais.com/_next/static/chunks/b.js",
            "lineNumber": 31,
            "disposition": "enforce",
        },
    },
    {"type": "deprecation", "url": "https://data.triathlon-club-nantais.com/", "body": {"id": "x"}},
]


def _post(client, body, content_type):
    return client.post(URL, content=json.dumps(body), headers={"Content-Type": content_type})


def _csp_logs(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "app.services.csp_report"]


def test_report_uri_format_is_logged(client, caplog):
    caplog.set_level(logging.WARNING, logger="app.services.csp_report")

    response = _post(client, REPORT_URI_BODY, "application/csp-report")

    assert response.status_code == 204
    [message] = _csp_logs(caplog)
    assert "directive=script-src" in message
    assert "blocked=eval" in message
    assert "document=https://data.triathlon-club-nantais.com/ajouter" in message
    assert "source=https://data.triathlon-club-nantais.com/_next/static/chunks/a.js:1" in message
    assert "disposition=report" in message


def test_report_to_format_logs_only_csp_violations(client, caplog):
    caplog.set_level(logging.WARNING, logger="app.services.csp_report")

    response = _post(client, REPORT_TO_BODY, "application/reports+json")

    assert response.status_code == 204
    [message] = _csp_logs(caplog)
    assert "directive=style-src-elem" in message
    assert "blocked=inline" in message
    assert "source=https://data.triathlon-club-nantais.com/_next/static/chunks/b.js:31" in message
    assert "disposition=enforce" in message


def test_invalid_json_is_rejected(client):
    response = client.post(URL, content=b"{not json", headers={"Content-Type": "application/csp-report"})

    assert response.status_code == 400


def test_oversized_body_is_rejected_without_logging(client, caplog):
    caplog.set_level(logging.WARNING, logger="app.services.csp_report")
    padding = "x" * MAX_REPORT_BYTES
    body = {"csp-report": {**REPORT_URI_BODY["csp-report"], "script-sample": padding}}

    response = _post(client, body, "application/csp-report")

    assert response.status_code == 413
    assert _csp_logs(caplog) == []


def test_logged_values_are_truncated_and_single_line(client, caplog):
    """A report is attacker-controlled: it must not forge extra log lines."""
    caplog.set_level(logging.WARNING, logger="app.services.csp_report")
    body = {"csp-report": {**REPORT_URI_BODY["csp-report"], "blocked-uri": "evil\nFAKE LOG LINE" + "y" * 1000}}

    _post(client, body, "application/csp-report")

    [message] = _csp_logs(caplog)
    assert "\n" not in message
    assert len(message) < 1500


def test_reports_are_rate_limited_per_ip(client):
    for _ in range(CSP_REPORT_RATE_LIMIT_MAX_PER_WINDOW):
        assert _post(client, REPORT_URI_BODY, "application/csp-report").status_code == 204

    assert _post(client, REPORT_URI_BODY, "application/csp-report").status_code == 429


@pytest.fixture
def real_site_gate(client):
    app.dependency_overrides.pop(require_site_access, None)
    yield


def test_reports_are_accepted_without_the_site_cookie(client, real_site_gate):
    """The Reporting API sends reports without credentials: a gated endpoint
    would only ever receive 401s."""
    assert _post(client, REPORT_URI_BODY, "application/csp-report").status_code == 204
