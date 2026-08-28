"""Bascule de la source active d'une épreuve — décision D2 de #275 (#285, #624).

**Ce fichier n'éprouve que le contrat HTTP/SSE** (garde, en-têtes, format des
frames) — jamais la mécanique de scrape/remplacement/purge, couverte par
`test_services/test_admin_actions.py`. Patron de `test_admin_course_rescrape.py` :
la route monte sa propre session (`SessionLocal()`, dédiée — voir la docstring
de `admin_course_sources.py`), qui n'est **pas** substituable par
`app.dependency_overrides[get_db]` — la faire tourner ici pour de vrai
frapperait la base de dev réelle, pas la base de test. On mocke donc
`admin_actions.iter_switch_course_source` lui-même, exactement comme
`test_admin_course_rescrape.py` mocke `admin_actions.iter_rescrape_course`.

**Flux SSE depuis #624** — la bascule était bloquante (#285) : #275 renvoyait
alors au SSE d'administration comme un chantier propre à #118, sans aucun
critère d'acceptation sur la progression. #624 referme ce renvoi : une bascule
sur une épreuve fan-out (Klikego, 30-40 s) dépassait le délai du proxy et
rendait un 502 avant même le premier octet.
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
    """Le club, créé par le conftest du dossier — les sessions à pouvoirs
    mesurés de `connecte` s'y rattachent."""
    return db_session.query(Organisation).filter_by(slug="tcn").one()


def connecte(client, db_session, organisation, *codes, email="arbitre@exemple.fr"):
    """Ouvre une session portant **exactement** ces pouvoirs — patron de
    `test_admin_course_rescrape.py`."""
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


def _url(course_id: int, source_id: int) -> str:
    return f"/api/v1/admin/courses/{course_id}/sources/{source_id}"


def _frames(body: str) -> list[dict]:
    return [
        json.loads(line[len("data: "):])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


def test_the_route_is_closed_to_anonymous_visitors(client):
    client.cookies.clear()

    reponse = client.patch(_url(1, 1), json={"is_active": True})

    assert reponse.status_code == 401


def test_a_holder_of_courses_write_alone_is_refused(client, db_session, organisation):
    """`courses:write` (le pouvoir voisin, borné à l'identité) ne suffit pas."""
    connecte(client, db_session, organisation, P.COURSES_WRITE.code)

    reponse = client.patch(_url(1, 1), json={"is_active": True})

    assert reponse.status_code == 403


def test_deactivating_a_source_is_refused_before_any_session(
    client, db_session, organisation
):
    """`{"is_active": false}` reste un refus synchrone (400), avant même
    l'ouverture de la session dédiée — jamais un event `error` dans un flux
    déjà ouvert à 200."""
    connecte(client, db_session, organisation, P.COURSES_SOURCES.code)

    reponse = client.patch(_url(1, 1), json={"is_active": False})

    assert reponse.status_code == 400


def test_a_holder_of_courses_sources_streams_the_switch(
    client, db_session, organisation, monkeypatch
):
    """Contrat SSE : padding, en-têtes, et au moins un `scraping`, un `saving`,
    un `done` portant `participations_deleted`/`participations_imported`/
    `athletes_purged`/`sources` — la même forme que `GET /courses/{id}/sources`
    (#284), pour que l'écran se réaffiche sans second appel."""
    connecte(client, db_session, organisation, P.COURSES_SOURCES.code)

    def fake_iter_switch_course_source(db, *, course_id, source_id, user_id, settings):
        yield {"phase": "scraping", "message": "Récupération des participants…"}
        yield {"phase": "saving", "total": 1}
        yield {
            "phase": "done",
            "participations_deleted": 2,
            "participations_imported": 1,
            "athletes_purged": 1,
            "sources": [
                {
                    "id": 2, "url": "https://b/x", "provider": "breizhchrono",
                    "is_active": True, "last_scraped_at": None,
                },
                {
                    "id": 1, "url": "https://k/x", "provider": "klikego",
                    "is_active": False, "last_scraped_at": None,
                },
            ],
        }

    monkeypatch.setattr(
        admin_actions, "iter_switch_course_source", fake_iter_switch_course_source
    )

    with client.stream("PATCH", _url(1, 2), json={"is_active": True}) as reponse:
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
    assert {
        "participations_deleted", "participations_imported", "athletes_purged", "sources",
    } <= set(done)
    assert [(s["url"], s["is_active"]) for s in done["sources"]] == [
        ("https://b/x", True),
        ("https://k/x", False),
    ]


def test_a_heartbeat_marker_becomes_a_comment_frame_not_a_data_frame(
    client, db_session, organisation, monkeypatch
):
    """#731 — la sentinelle `admin_actions.SSE_HEARTBEAT` (émise par
    `_stream_switch_course_source` sur une phase longue) doit devenir une
    ligne de commentaire SSE `: heartbeat`, jamais un `data:` JSON — même
    contrat que `scrape.py::generate()` (#705)."""
    connecte(client, db_session, organisation, P.COURSES_SOURCES.code)

    def fake_iter_switch_course_source(db, *, course_id, source_id, user_id, settings):
        yield {"phase": "scraping", "message": "Récupération des participants…"}
        yield admin_actions.SSE_HEARTBEAT
        yield {
            "phase": "done", "participations_deleted": 0,
            "participations_imported": 0, "athletes_purged": 0, "sources": [],
        }

    monkeypatch.setattr(
        admin_actions, "iter_switch_course_source", fake_iter_switch_course_source
    )

    with client.stream("PATCH", _url(1, 2), json={"is_active": True}) as reponse:
        assert reponse.status_code == 200
        body = "".join(reponse.iter_text())

    frames = body.split("\n\n")
    heartbeats = [f for f in frames if f.strip() == ": heartbeat"]
    assert heartbeats, "aucun battement émis"
    assert _frames(body)[-1]["phase"] == "done"


def test_a_switch_already_running_is_refused_before_any_byte(
    client, db_session, organisation, monkeypatch
):
    """FR-007 (verrou partagé avec le re-scrape, #624) : 409 (`{"detail": ...}`),
    pas un event `error` dans un flux déjà ouvert."""
    connecte(client, db_session, organisation, P.COURSES_SOURCES.code)

    # Fonction **ordinaire**, pas un générateur (patron réel
    # d'`admin_actions.iter_switch_course_source` — cf. sa docstring) : un
    # `yield` ici différerait la levée au premier `next()`, donc *après* que
    # `StreamingResponse` ait déjà envoyé un statut 200.
    def fake_iter_switch_course_source(db, *, course_id, source_id, user_id, settings):
        raise admin_actions.CourseRescrapeAlreadyRunningError()

    monkeypatch.setattr(
        admin_actions, "iter_switch_course_source", fake_iter_switch_course_source
    )

    reponse = client.patch(_url(1, 2), json={"is_active": True})

    assert reponse.status_code == 409
    assert "detail" in reponse.json()


def test_an_unknown_course_is_a_not_found(client, db_session, organisation, monkeypatch):
    connecte(client, db_session, organisation, P.COURSES_SOURCES.code)

    def fake_iter_switch_course_source(db, *, course_id, source_id, user_id, settings):
        raise NotFoundError("Épreuve introuvable.")

    monkeypatch.setattr(
        admin_actions, "iter_switch_course_source", fake_iter_switch_course_source
    )

    assert client.patch(_url(999999, 1), json={"is_active": True}).status_code == 404


def test_a_source_of_another_course_is_a_not_found(
    client, db_session, organisation, monkeypatch
):
    """AC5 — 404, ni 403 ni 500 : l'adresse ne désigne rien, elle n'est pas
    interdite."""
    connecte(client, db_session, organisation, P.COURSES_SOURCES.code)

    def fake_iter_switch_course_source(db, *, course_id, source_id, user_id, settings):
        raise NotFoundError("Source introuvable pour cette épreuve.")

    monkeypatch.setattr(
        admin_actions, "iter_switch_course_source", fake_iter_switch_course_source
    )

    reponse = client.patch(_url(1, 999999), json={"is_active": True})

    assert reponse.status_code == 404


def test_the_new_power_is_its_own_entry_in_the_catalogue():
    """Un membre de plus dans `P`, pas un élargissement de `courses:write`.

    Indépendant du transport (SSE ou non) : le pouvoir vit en Python,
    l'attribution en base.
    """
    from app.core import permissions

    assert P.COURSES_SOURCES.code == "courses:sources"
    assert P.COURSES_SOURCES in permissions.ALL
    assert P.COURSES_SOURCES.feature == permissions.FEATURE_COURSES
    assert "réécrit" in P.COURSES_SOURCES.description
