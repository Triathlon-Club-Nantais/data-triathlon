"""Résultats en attente sur la page de l'épreuve, hors de tout compte (#1273).

Chaque compte de FR-006 est relu **avant** puis **après** l'ajout d'une ligne en
attente (et d'une ligne refusée) : il doit rendre exactement la même valeur. La
ligne en attente n'apparaît que dans `pending_participations` de
`GET /courses/{id}` et dans `pending_count` de `GET /courses/events`.
"""
from datetime import date

import pytest

from app.repositories import course_repository, participation_repository, tcn_count_repository
from app.scrapers.base import ScrapedResult
from app.services import scrape_service

URL = "https://raceresult.example/alpe"


def _scraped(bib, nom, *, club="TCN", rank=1, pending=False, event_name="Triathlon Alpe") -> ScrapedResult:
    return ScrapedResult(
        source_url=URL if event_name == "Triathlon Alpe" else f"{URL}/{event_name}",
        provider="raceresult",
        athlete_name=nom,
        athlete_firstname="Jean",
        gender="M",
        club=club,
        event_name=event_name,
        event_date=date(2026, 8, 6),
        event_type="triathlon-m",
        bib_number=bib,
        category="V1H",
        rank_overall=rank,
        total_time=f"02:0{rank}:00",
        swim_time="00:20:00",
        bike_time="01:00:00",
        run_time=f"00:4{rank}:00",
        is_pending_validation=pending,
    )


def _recount(db_session, course):
    validated, _ = participation_repository.list_page_for_course(db_session, course.id, page_size=None)
    tcn_count_repository.recompute_counts_for_tcn(db_session)
    course_repository.set_counts(
        db_session, course, participation_count=len(validated), tcn_count=course.tcn_count
    )
    db_session.commit()


#: Lectures dont aucune valeur ne doit bouger quand une ligne en attente s'ajoute.
def _counts(client, course_id, validee_id):
    events = client.get("/api/v1/courses/events").json()
    event = next(e for e in events["items"] if e["id"] == course_id)
    page = client.get(f"/api/v1/courses/{course_id}?page_size=all").json()
    return {
        "page.total": page["total"],
        "page.participations": [p["id"] for p in page["participations"]],
        "summary": client.get(f"/api/v1/courses/{course_id}/summary").json(),
        "rangs et écarts": client.get(f"/api/v1/participations/{validee_id}").json()["stats"],
        "stats": client.get("/api/v1/stats").json(),
        "stats club": client.get("/api/v1/stats?scope=club").json(),
        "saisons": client.get("/api/v1/stats/seasons").json(),
        "club": client.get("/api/v1/club/summary").json(),
        "events.total": event["total"],
        "events.tcn_count": event["tcn_count"],
        "events.total_participations": events["total_participations"],
        "events club": [
            (e["id"], e["total"], e["tcn_count"])
            for e in client.get("/api/v1/courses/events?scope=club").json()["items"]
        ],
        "geo": client.get("/api/v1/stats/events-geo").json(),
        "qualité": client.get("/api/v1/courses/count?unreliable=true").json(),
        "qualité à trancher": client.get("/api/v1/courses/count?awaiting_review=true").json(),
    }


@pytest.fixture
def epreuve(db_session):
    validee = scrape_service.save_one(db_session, _scraped("1", "DUPONT", rank=1))
    scrape_service.save_one(db_session, _scraped("2", "MARTIN", club="ASPTT", rank=2))
    course = validee.course
    _recount(db_session, course)
    return course, validee


def _ajoute_en_attente(db_session, course):
    en_attente = scrape_service.save_one(db_session, _scraped("3", "ATTENTE", rank=1, pending=True))
    refusee = scrape_service.save_one(db_session, _scraped("4", "REFUS", rank=1, pending=True))
    participation_repository.update(db_session, refusee, is_rejected=True)
    tcn_count_repository.recompute_counts_for_tcn(db_session)
    db_session.commit()
    return en_attente, refusee


def test_aucun_compte_ne_bouge_quand_une_ligne_en_attente_s_ajoute(client, db_session, epreuve):
    course, validee = epreuve
    avant = _counts(client, course.id, validee.id)
    assert avant["rangs et écarts"] is not None, "l'épreuve doit être éligible aux statistiques"

    _ajoute_en_attente(db_session, course)
    apres = _counts(client, course.id, validee.id)

    for cle in avant:
        assert apres[cle] == avant[cle], cle


def test_page_epreuve_rend_la_ligne_en_attente_a_part(client, db_session, epreuve):
    course, _ = epreuve
    en_attente, refusee = _ajoute_en_attente(db_session, course)

    page1 = client.get(f"/api/v1/courses/{course.id}?page_size=1").json()
    page2 = client.get(f"/api/v1/courses/{course.id}?page_size=1&page=2").json()

    assert page1["total"] == 2
    assert [p["id"] for p in page1["pending_participations"]] == [en_attente.id]
    assert page1["pending_participations"][0]["is_pending_validation"] is True
    assert page2["pending_participations"] == page1["pending_participations"]
    ids_classes = {p["id"] for p in page1["participations"] + page2["participations"]}
    assert en_attente.id not in ids_classes and refusee.id not in ids_classes


def test_page_epreuve_filtre_les_lignes_en_attente_comme_le_classement(client, db_session, epreuve):
    course, _ = epreuve
    en_attente, _ = _ajoute_en_attente(db_session, course)

    trouvee = client.get(f"/api/v1/courses/{course.id}?q=attente").json()
    absente = client.get(f"/api/v1/courses/{course.id}?q=dupont").json()

    assert [p["id"] for p in trouvee["pending_participations"]] == [en_attente.id]
    assert absente["pending_participations"] == []


def test_liste_des_epreuves_rend_l_epreuve_en_attente_seule_avec_pending_count(client, db_session, epreuve):
    course, _ = epreuve
    _ajoute_en_attente(db_session, course)
    seule = scrape_service.save_one(
        db_session, _scraped("1", "SOLO", pending=True, event_name="Alpe solo")
    ).course

    body = client.get("/api/v1/courses/events").json()
    items = {e["id"]: e for e in body["items"]}

    assert (items[seule.id]["total"], items[seule.id]["pending_count"]) == (0, 1)
    assert (items[course.id]["total"], items[course.id]["pending_count"]) == (2, 1)
    assert body["total_participations"] == 2
    assert body["total_events"] == 2


def test_page_epreuve_sans_ligne_en_attente_rend_une_liste_vide(client, epreuve):
    course, _ = epreuve
    body = client.get(f"/api/v1/courses/{course.id}").json()
    assert body["pending_participations"] == []
