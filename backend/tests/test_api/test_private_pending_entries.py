"""Une saisie en attente n'est lisible que des bénévoles (#1519).

Publique depuis #1273 et FR-019, elle laissait un visiteur constater par une
seconde requête qu'une saisie nommant une personne opposée n'avait rien
enregistré (#1514). Chaque oracle est éprouvé deux fois : visiteur, bénévole.
"""
import pytest

from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.models.participation import Participation
from app.models.user import User
from app.models.volunteer_access_config import VolunteerAccessConfig
from app.repositories import participation_repository
from app.services import shared_password, volunteer_access
from tests.test_api.test_participations_api import _created, _oppose_jean_dupont, _payload


@pytest.fixture
def visitor(client):
    """Ni session SSO ni cookie bénévoles : le public."""
    client.cookies.delete(session_cookie_name(get_settings()))
    return client


@pytest.fixture
def volunteer(visitor, db_session):
    _volunteer_cookie(visitor, db_session)
    return visitor


@pytest.fixture
def entries(client, db_session):
    """Une saisie en attente et une saisie refusée, posées sur la même épreuve neuve."""
    pending = _created(client, db_session, _payload(bib="1", nom="ATTENTE"))
    rejected = _created(client, db_session, _payload(bib="2", nom="REFUS"))
    participation_repository.update(db_session, rejected, is_rejected=True)
    db_session.commit()
    return pending, rejected


def test_a_visitor_reads_a_pending_entry_as_a_missing_one(visitor, entries):
    pending, rejected = entries
    missing = visitor.get("/api/v1/participations/999999")

    for entry in (pending, rejected):
        answer = visitor.get(f"/api/v1/participations/{entry.id}")
        assert (answer.status_code, answer.json()) == (missing.status_code, missing.json())
    assert missing.status_code == 404


def test_a_volunteer_still_reads_a_pending_entry(volunteer, entries):
    pending, _ = entries
    assert volunteer.get(f"/api/v1/participations/{pending.id}").status_code == 200


def test_the_course_page_hides_pending_rows_from_a_visitor_only(visitor, entries, db_session):
    pending, _ = entries
    course_id = pending.course_id

    assert visitor.get(f"/api/v1/courses/{course_id}").json()["pending_participations"] == []

    _volunteer_cookie(visitor, db_session)
    shown = visitor.get(f"/api/v1/courses/{course_id}").json()["pending_participations"]
    assert [p["id"] for p in shown] == [pending.id]


def test_the_event_list_hides_pending_only_events_from_a_visitor(visitor, entries, db_session):
    pending, _ = entries
    course_id = pending.course_id

    listed = {e["id"] for e in visitor.get("/api/v1/courses/events").json()["items"]}
    assert course_id not in listed
    by_name = visitor.get("/api/v1/courses/events?name=attente").json()["items"]
    assert course_id not in {e["id"] for e in by_name}

    _volunteer_cookie(visitor, db_session)
    items = {e["id"]: e for e in visitor.get("/api/v1/courses/events").json()["items"]}
    assert items[course_id]["pending_count"] == 1


def test_the_athlete_page_and_csv_hide_pending_rows_from_a_visitor(visitor, entries, db_session):
    pending, rejected = entries

    for entry in (pending, rejected):
        athlete_id = entry.athlete_id
        assert visitor.get(f"/api/v1/athletes/{athlete_id}").json()["participations"] == []
        csv = visitor.get(f"/api/v1/athletes/{athlete_id}/participations.csv").text
        assert len(csv.strip().splitlines()) == 1, "en-tête seul"

    _volunteer_cookie(visitor, db_session)
    athlete_id = pending.athlete_id
    shown = visitor.get(f"/api/v1/athletes/{athlete_id}").json()["participations"]
    assert [p["id"] for p in shown] == [pending.id]
    assert "Triathlon de Nantes" in visitor.get(f"/api/v1/athletes/{athlete_id}/participations.csv").text


def test_resending_a_pending_entry_answers_201_and_stores_nothing_more(visitor, db_session):
    first = visitor.post("/api/v1/participations", json=_payload())
    again = visitor.post("/api/v1/participations", json=_payload())

    assert (first.status_code, again.status_code) == (201, 201)
    assert db_session.query(Participation).count() == 1
    assert again.json() == first.json()


def test_two_simultaneous_entries_with_one_bib_both_answer_201(visitor, db_session, monkeypatch):
    """Deux saisies parallèles passent toutes deux la lecture du dossard : la seconde
    heurte `uq_participation_bib`. Un 500 la distinguerait de celle d'une personne
    opposée, dont la première a été annulée."""
    first = visitor.post("/api/v1/participations", json=_payload())
    monkeypatch.setattr(participation_repository, "get_by_bib", lambda *args: None)

    again = visitor.post("/api/v1/participations", json=_payload())

    assert (first.status_code, again.status_code) == (201, 201)
    assert db_session.query(Participation).count() == 1
    assert again.json() == first.json()


def test_a_bib_held_by_a_published_result_is_still_refused(visitor, db_session):
    from tests.test_api.conftest import valider_toutes_les_participations

    visitor.post("/api/v1/participations", json=_payload())
    valider_toutes_les_participations(db_session)

    again = visitor.post("/api/v1/participations", json=_payload(nom="MARTIN"))

    assert again.status_code == 409


def test_a_visitor_cannot_tell_an_opposed_entry_from_another(visitor, db_session):
    """Les oracles de #1519 en séquence. Sans identifiant dans la réponse (#1724),
    il ne reste à un visiteur que les statuts d'une saisie et de son renvoi."""

    def probe(nom):
        payload = _payload(nom=nom, bib=nom)
        created = visitor.post("/api/v1/participations", json=payload)
        return created.status_code, visitor.post("/api/v1/participations", json=payload).status_code

    _oppose_jean_dupont(db_session)

    assert probe("DUPONT") == probe("MARTIN") == (201, 201)


def _volunteer_cookie(client, db_session):
    """Le mot de passe partagé des bénévoles, sans session SSO."""
    admin = db_session.query(User).first()
    volunteer_access.replace_password(db_session, password="secret", admin_user_id=admin.id)
    db_session.commit()
    config = db_session.query(VolunteerAccessConfig).one()
    client.cookies.set(
        volunteer_access.VOLUNTEER_SESSION_COOKIE, shared_password.sign_cookie(config.session_secret)
    )


def _ids_in(value):
    """Toute clé d'identifiant, à n'importe quelle profondeur."""
    if isinstance(value, dict):
        own = [key for key in value if key == "id" or key.endswith("_id")]
        return own + [found for nested in value.values() for found in _ids_in(nested)]
    if isinstance(value, list):
        return [found for nested in value for found in _ids_in(nested)]
    return []


def test_the_public_entry_answer_carries_no_id_opposed_or_not(visitor, db_session):
    """#1724 : un identifiant consommé ou réutilisé trahissait une saisie annulée."""
    _oppose_jean_dupont(db_session)
    relay = {"is_relay": True, "team_name": "Les Nantais"}

    opposed = visitor.post("/api/v1/participations", json={**_payload(), **relay})
    other = visitor.post("/api/v1/participations", json={**_payload(nom="MARTIN", bib="43"), **relay})

    assert (opposed.status_code, other.status_code) == (201, 201)
    assert _ids_in(opposed.json()) == _ids_in(other.json()) == []
    assert opposed.json() == {**other.json(), "athlete_name": "DUPONT", "bib_number": "42"}
    assert opposed.json()["is_pending_validation"] is True
