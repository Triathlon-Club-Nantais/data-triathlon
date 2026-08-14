"""Re-scrape à la demande d'une course depuis le back-office (#118).

**Ce fichier n'éprouve que le contrat HTTP/SSE** (garde, en-têtes, format des
frames) — jamais la mécanique de scrape/upsert/purge, couverte par
`test_services/test_admin_actions.py`. Patron de `test_scrape_api.py` : la
route mono
te sa propre session (`SessionLocal()`, dédiée — voir la docstring
de `admin_course_rescrape.py`), qui n'est **pas** substituable par
`app.dependency_overrides[get_db]` — la faire tourner ici pour de vrai
frapperait la base de dev réelle, pas la base de test. On mocke donc
`admin_actions.iter_rescrape_course` lui-même, exactement comme
`test_scrape_api.py` mocke `import_service.iter_import_event`.
"""
import json

import pytest

from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.permissions import P
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.repositories import role_repository, user_repository, user_role_repository
from app.services import admin_actions
from app.services.auth import session as session_service


@pytest.fixture
def organisation(db_session) -> Organisation:
    return db_session.query(Organisation).filter_by(slug="tcn").one()


def connecte(client, db_session, organisation, *codes, email="arbitre@exemple.fr"):
    """Session à pouvoirs mesurés — patron de `test_course_source_switch_api.py`."""
    user = user_repository.create(db_session, email=email)
    db_session.flush()
    role = role_repository.create(db_session, slug="arbitre", name="Arbitre de test")
    for code in codes:
        role.permissions.append(RolePermission(permission_code=code))
    db_session.flush()
    user_role_repository.grant(
        db_session, user_id=user.id, role_id=role.id, organisation_id=organisation.id
    )
    jeton = session_service.open_for(db_session, user)
    db_session.commit()
    client.cookies.set(session_cookie_name(get_settings()), jeton)
    return user


def _url(course_id: int) -> str:
    return f"/api/v1/admin/courses/{course_id}/rescrape"


def _frames(body: str) -> list[dict]:
    return [
        json.loads(line[len("data: "):])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


def test_the_route_is_closed_to_anonymous_visitors(client):
    client.cookies.clear()

    reponse = client.post(_url(1))

    assert reponse.status_code == 401


def test_a_holder_of_courses_write_alone_is_refused(client, db_session, organisation):
    """`courses:write` (le pouvoir voisin, borné à l'identité) ne suffit pas."""
    connecte(client, db_session, organisation, P.COURSES_WRITE.code)

    reponse = client.post(_url(1))

    assert reponse.status_code == 403


def test_a_holder_of_courses_sources_streams_the_rescrape(client, monkeypatch):
    """T004 — contrat SSE : padding, en-têtes, et au moins un `scraping`, un
    `saving`, un `done` portant `imported`/`updated`/`total`/`orphans_removed`."""

    def fake_iter_rescrape_course(db, *, course_id, user_id, settings):
        yield {"phase": "scraping", "message": "Récupération des participants…"}
        yield {"phase": "saving", "total": 1, "imported": 0, "updated": 0, "skipped": 0, "progress": 0}
        yield {
            "phase": "done", "imported": 1, "updated": 0, "skipped": 0,
            "reconciled": 0, "total": 1, "orphans_removed": 0,
        }

    monkeypatch.setattr(admin_actions, "iter_rescrape_course", fake_iter_rescrape_course)

    with client.stream("POST", _url(1)) as reponse:
        assert reponse.status_code == 200
        assert reponse.headers.get("content-type", "").startswith("text/event-stream")
        assert reponse.headers.get("content-encoding") == "identity"
        body = "".join(reponse.iter_text())

    # Padding initial : la première ligne est un commentaire SSE d'au moins 2 Ko.
    premiere_ligne = body.splitlines()[0]
    assert premiere_ligne.startswith(":")
    assert len(premiere_ligne) >= 2048

    frames = _frames(body)
    phases = [f["phase"] for f in frames]
    assert "scraping" in phases
    assert "saving" in phases
    done = frames[-1]
    assert done["phase"] == "done"
    assert {"imported", "updated", "total", "orphans_removed"} <= set(done)


def test_a_rescrape_already_running_is_refused_before_any_byte(client, monkeypatch):
    """T018/T020 — FR-007 : 409 (`{"detail": ...}`), pas un event `error` dans un
    flux déjà ouvert."""

    # Fonction **ordinaire**, pas un générateur (patron réel de
    # `admin_actions.iter_rescrape_course` — cf. sa docstring) : un `yield`
    # ici différerait la levée au premier `next()`, donc *après* que
    # `StreamingResponse` ait déjà envoyé un statut 200.
    def fake_iter_rescrape_course(db, *, course_id, user_id, settings):
        raise admin_actions.CourseRescrapeAlreadyRunningError()

    monkeypatch.setattr(admin_actions, "iter_rescrape_course", fake_iter_rescrape_course)

    reponse = client.post(_url(1))

    assert reponse.status_code == 409
    assert "detail" in reponse.json()


def test_an_unknown_course_is_a_not_found(client, monkeypatch):
    def fake_iter_rescrape_course(db, *, course_id, user_id, settings):
        raise NotFoundError("Épreuve introuvable.")

    monkeypatch.setattr(admin_actions, "iter_rescrape_course", fake_iter_rescrape_course)

    assert client.post(_url(999999)).status_code == 404


def test_a_course_without_active_source_is_a_not_found(client, monkeypatch):
    """G4 — saisie manuelle : rien à re-scraper."""

    def fake_iter_rescrape_course(db, *, course_id, user_id, settings):
        raise NotFoundError("Cette épreuve n'a aucune source active à re-scraper.")

    monkeypatch.setattr(admin_actions, "iter_rescrape_course", fake_iter_rescrape_course)

    reponse = client.post(_url(1))

    assert reponse.status_code == 404
    assert "source active" in reponse.json()["detail"]
