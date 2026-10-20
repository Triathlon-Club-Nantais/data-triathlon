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


def _published(client, db_session, payload):
    """Une saisie, puis validée : elle fait exister sa fiche et son épreuve au public."""
    row = _created(client, db_session, payload)
    participation_repository.update(db_session, row, is_pending_validation=False)
    db_session.commit()
    return row


def test_the_course_page_hides_pending_rows_from_a_visitor_only(visitor, entries, db_session):
    pending, _ = entries
    course_id = pending.course_id
    _published(visitor, db_session, _payload(bib="3", nom="PUBLIE"))

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
    for nom in ("ATTENTE", "REFUS"):
        _published(visitor, db_session, {**_payload(bib=nom, nom=nom), "event_name": "Duathlon de Rezé"})

    for entry in (pending, rejected):
        athlete_id = entry.athlete_id
        shown = visitor.get(f"/api/v1/athletes/{athlete_id}").json()["participations"]
        assert [p["course"]["name"] for p in shown] == ["Duathlon de Rezé"]
        csv = visitor.get(f"/api/v1/athletes/{athlete_id}/participations.csv").text
        assert "Triathlon de Nantes" not in csv

    _volunteer_cookie(visitor, db_session)
    athlete_id = pending.athlete_id
    shown = visitor.get(f"/api/v1/athletes/{athlete_id}").json()["participations"]
    assert pending.id in [p["id"] for p in shown]
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
    restent les statuts et les recherches, où la fiche et l'épreuve neuves
    d'une saisie en attente n'apparaissent pas (#1615)."""

    def probe(nom):
        payload = {**_payload(nom=nom, bib=nom), "event_name": f"Epreuve {nom}"}
        created = visitor.post("/api/v1/participations", json=payload)
        return (
            created.status_code,
            visitor.post("/api/v1/participations", json=payload).status_code,
            visitor.get(f"/api/v1/athletes/search?q={nom}").json(),
            visitor.get(f"/api/v1/athletes?name={nom}").json(),
            visitor.get(f"/api/v1/courses?name=Epreuve {nom}").json(),
            visitor.get(f"/api/v1/courses/count?name=Epreuve {nom}").json(),
        )

    _oppose_jean_dupont(db_session)

    assert probe("DUPONT") == probe("MARTIN") == (201, 201, [], [], [], {"total": 0})


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


# --- #1615 : une fiche ou une épreuve que seules des saisies en attente font exister ---


def _relay_teammate(db_session, entry):
    """Un équipier attribué au relais d'une saisie en attente."""
    from app.repositories import athlete_repository

    paul = athlete_repository.get_or_create(db_session, nom="EQUIPIER", prenom="Paul")
    participation_repository.replace_teammates(db_session, entry, [paul.id, entry.athlete_id])
    db_session.commit()
    return paul.id


def _pages(athlete_id, course_id):
    return [
        f"/api/v1/athletes/{athlete_id}",
        f"/api/v1/athletes/{athlete_id}/participations.csv",
        f"/api/v1/courses/{course_id}",
        f"/api/v1/courses/{course_id}/summary",
        f"/api/v1/courses/{course_id}/sources",
    ]


def test_a_pending_only_athlete_or_course_answers_a_visitor_like_a_missing_one(visitor, entries, db_session):
    pending, rejected = entries
    teammate_id = _relay_teammate(db_session, pending)
    missing = [visitor.get(path) for path in [*_pages(999999, 999999), "/api/v1/club/roster/rank/999999"]]
    assert {answer.status_code for answer in missing} == {404}

    for athlete_id in (pending.athlete_id, rejected.athlete_id, teammate_id):
        paths = [*_pages(athlete_id, pending.course_id), f"/api/v1/club/roster/rank/{athlete_id}"]
        answers = [visitor.get(path) for path in paths]
        assert [(a.status_code, a.json()) for a in answers] == [(m.status_code, m.json()) for m in missing]

    _volunteer_cookie(visitor, db_session)
    for athlete_id in (pending.athlete_id, rejected.athlete_id, teammate_id):
        assert {visitor.get(path).status_code for path in _pages(athlete_id, pending.course_id)} == {200}


def test_searches_and_lists_skip_pending_only_rows_for_a_visitor_only(visitor, entries, db_session):
    pending, rejected = entries
    hidden = {pending.athlete_id, rejected.athlete_id, _relay_teammate(db_session, pending)}

    def seen():
        athletes = {
            row["id"]
            for nom in ("ATTENTE", "REFUS", "EQUIPIER")
            for path in (f"/api/v1/athletes/search?q={nom}", f"/api/v1/athletes?name={nom}")
            for row in visitor.get(path).json()
        }
        courses = {
            row["id"]
            for path in ("/api/v1/courses", "/api/v1/courses?name=Nantes")
            for row in visitor.get(path).json()
        }
        counts = {visitor.get(path).json()["total"] for path in ("/api/v1/courses/count", "/api/v1/courses/count?name=Nantes")}
        return athletes, courses, counts

    assert seen() == (set(), set(), {0})

    _volunteer_cookie(visitor, db_session)
    assert seen() == (hidden, {pending.course_id}, {1})


def test_a_published_result_a_claim_or_no_result_at_all_keeps_a_record_public(visitor, db_session):
    """Masquer sur « aucun résultat validé » seul retirerait les membres sans résultat (#562)."""
    from app.models.athlete import Athlete

    bare = Athlete(nom="SANSRESULTAT", prenom="Jean")
    db_session.add(bare)
    claimed = _created(visitor, db_session, _payload(bib="1", nom="RATTACHE"))
    db_session.query(User).first().athlete_id = claimed.athlete_id
    mixed = _published(visitor, db_session, _payload(bib="2", nom="MIXTE"))
    _created(visitor, db_session, {**_payload(bib="3", nom="MIXTE"), "event_name": "Autre épreuve"})

    for athlete_id in (bare.id, claimed.athlete_id, mixed.athlete_id):
        assert visitor.get(f"/api/v1/athletes/{athlete_id}").status_code == 200
    assert visitor.get(f"/api/v1/courses/{mixed.course_id}").status_code == 200
    listed = {row["nom"] for row in visitor.get("/api/v1/athletes").json()}
    assert {"SANSRESULTAT", "RATTACHE", "MIXTE"} <= listed


def test_a_member_cannot_claim_a_pending_only_athlete(client, db_session):
    """La réponse d'une demande nomme la fiche : elle ne doit pas sortir par là."""
    from tests.test_api.test_athlete_claims_api import MY_CLAIM, _member

    pending = _created(client, db_session, _payload(nom="ATTENTE"))
    _member(client, db_session)

    missing = client.post(MY_CLAIM, json={"athlete_id": 999999})
    hidden = client.post(MY_CLAIM, json={"athlete_id": pending.athlete_id})

    assert (hidden.status_code, hidden.json()) == (missing.status_code, missing.json()) == (
        404, {"detail": "Fiche athlète introuvable."}
    )


def test_a_validated_relay_elsewhere_does_not_unhide_a_pending_only_athlete(visitor, entries, db_session):
    """Revue de #1756 : la sous-requête des équipiers, non corrélée, voyait n'importe quel relais."""
    relay = _published(
        visitor, db_session, {**_payload(bib="R", nom="RELAIS"), "event_name": "Relais public", "is_relay": True}
    )
    _relay_teammate(db_session, relay)

    for path in ("/api/v1/athletes/search?q=ATTENTE", "/api/v1/athletes?name=ATTENTE"):
        assert visitor.get(path).json() == []


def test_a_volunteer_action_cannot_reach_or_unhide_a_pending_only_athlete(visitor, entries, db_session):
    """Revue de #1756 : un 201 au lieu d'un 404 servait d'oracle, et l'action rendait la fiche publique."""
    from app.repositories import volunteer_action_repository

    pending, _ = entries
    body = {"title": "Ravitaillement", "description": "Course des jeunes"}
    missing = visitor.post("/api/v1/volunteer-actions", json={**body, "athlete_id": 999999})
    hidden = visitor.post("/api/v1/volunteer-actions", json={**body, "athlete_id": pending.athlete_id})
    assert (hidden.status_code, hidden.json()) == (missing.status_code, missing.json())
    assert missing.status_code == 404

    action = volunteer_action_repository.create_pending(
        db_session, athlete_id=pending.athlete_id, season=2026, declared_by_user_id=None,
        title="Ravitaillement", description="",
    )
    db_session.commit()
    assert visitor.get(f"/api/v1/athletes/{pending.athlete_id}").status_code == 404
    volunteer_action_repository.set_status(db_session, action.id, "validee")
    db_session.commit()
    assert visitor.get(f"/api/v1/athletes/{pending.athlete_id}").status_code == 200


def test_claiming_a_pending_result_answers_like_an_unknown_one(client, entries, db_session):
    """Revue de #1756 : un 409 sur une saisie en attente, un 404 sur un id inconnu (#1637)."""
    from app.models.athlete import Athlete
    from tests.test_api.test_athlete_claims_api import _member

    pending, _ = entries
    mine = Athlete(nom="MOI", prenom="Léa")
    db_session.add(mine)
    user = _member(client, db_session)
    db_session.get(User, user.id).athlete_id = mine.id
    db_session.commit()

    missing = client.post("/api/v1/auth/me/result-claims", json={"participation_id": 999999})
    hidden = client.post("/api/v1/auth/me/result-claims", json={"participation_id": pending.id})

    assert (hidden.status_code, hidden.json()) == (missing.status_code, missing.json())
    assert missing.json() == {"detail": "Résultat introuvable."}
