from datetime import date

from app.models.admin_action_log import AdminActionLog
from app.scrapers.base import ScrapedResult
from app.services import scrape_service
from tests.test_api.conftest import valider_toutes_les_participations


def _payload(bib="42", nom="DUPONT", club="TCN"):
    """Payload d'une saisie manuelle via `POST /participations`.

    `provider` a été retiré du contrat d'entrée et `source_url` y est
    silencieusement ignoré (#565) : la route force toujours `provider="manuel"`
    et aucune source active. Ce comportement est couvert par
    `tests/test_auth/test_manual_participation_no_active_source.py`, pas ici.
    """
    return {
        "athlete_name": nom,
        "athlete_firstname": "Jean",
        "gender": "M",
        "club": club,
        "event_name": "Triathlon de Nantes",
        "event_date": "2026-05-16",
        "event_type": "triathlon-m",
        "bib_number": bib,
        "category": "V1H",
        "rank_overall": 10,
        "total_time": "01:59:00",
        "swim_time": "00:20:00",
        "bike_time": "01:00:00",
        "run_time": "00:39:00",
    }


def test_create_and_get_participation(client):
    resp = client.post("/api/v1/participations", json=_payload())
    assert resp.status_code == 201
    body = resp.json()
    pid = body["id"]
    assert body["athlete"]["nom"] == "DUPONT"
    assert body["course"]["name"] == "Triathlon de Nantes"
    assert body["splits"] == {"swim": "00:20:00", "bike": "01:00:00", "run": "00:39:00"}

    got = client.get(f"/api/v1/participations/{pid}")
    assert got.status_code == 200
    assert got.json()["bib_number"] == "42"


def test_create_participation_with_segments(client):
    # Chemin générique : segments étiquetés libres, déplafonnés, priment sur les slots.
    payload = _payload(bib="77")
    payload.pop("swim_time", None)
    payload.pop("bike_time", None)
    payload.pop("run_time", None)
    payload["event_type"] = "swimrun-l"
    payload["segments"] = [["swim1", "00:10:00"], ["run1", "00:20:00"], ["swim2", "00:08:00"]]
    resp = client.post("/api/v1/participations", json=payload)
    assert resp.status_code == 201
    assert resp.json()["splits"] == {
        "swim1": "00:10:00",
        "run1": "00:20:00",
        "swim2": "00:08:00",
    }


def test_duplicate_participation_409(client):
    client.post("/api/v1/participations", json=_payload())
    dup = client.post("/api/v1/participations", json=_payload())
    assert dup.status_code == 409


def test_list_filters(client, db_session):
    client.post("/api/v1/participations", json=_payload(bib="1", nom="DUPONT", club="TCN"))
    client.post("/api/v1/participations", json=_payload(bib="2", nom="MARTIN", club="ASPTT"))
    valider_toutes_les_participations(db_session)

    by_name = client.get("/api/v1/participations", params={"name": "dupont"})
    assert len(by_name.json()) == 1

    by_club = client.get("/api/v1/participations", params={"scope": "club"})
    assert by_club.status_code == 200
    assert by_club.json()[0]["club"] == "TCN"


def test_delete_participation(client):
    pid = client.post("/api/v1/participations", json=_payload()).json()["id"]
    # La suppression est hors de l'`assert` : sous `python -O` elle ne partirait
    # pas, et le 404 attendu ensuite ne prouverait plus rien.
    suppression = client.delete(f"/api/v1/participations/{pid}")
    assert suppression.status_code == 204
    assert client.get(f"/api/v1/participations/{pid}").status_code == 404


def test_delete_participation_consigne_une_entree_au_journal(client, db_session):
    """#439 — le geste le plus irréversible de l'API ne laissait aucune trace."""
    pid = client.post("/api/v1/participations", json=_payload()).json()["id"]

    suppression = client.delete(f"/api/v1/participations/{pid}")
    assert suppression.status_code == 204

    entrees = db_session.query(AdminActionLog).all()
    assert [(e.action, e.entity_type, e.entity_id) for e in entrees] == [
        ("participation.delete", "participation", pid)
    ]


def test_supprimer_deux_fois_rend_404_et_n_ecrit_rien_de_plus(client, db_session):
    """FR-014, FR-016 — un autre administrateur est passé avant : 404, pas 204.

    Un second 204 laisserait croire à une seconde suppression, et une seconde
    entrée au journal ferait compter deux gestes là où il n'y en a eu qu'un.
    """
    pid = client.post("/api/v1/participations", json=_payload()).json()["id"]
    client.delete(f"/api/v1/participations/{pid}")

    seconde = client.delete(f"/api/v1/participations/{pid}")

    assert seconde.status_code == 404
    assert db_session.query(AdminActionLog).count() == 1


def test_supprimer_un_resultat_en_attente_de_validation_rend_204_et_journalise(
    client, db_session
):
    """US2-AC6 — la route ne distingue pas les deux états.

    Un résultat créé par `POST /participations` naît en attente (#270) : le
    supprimer est le même geste, avec la même trace. Côté page, sa disparition
    ne bouge aucun indicateur — les cinq sont calculés sur les validés.
    """
    creation = client.post("/api/v1/participations", json=_payload())
    assert creation.json()["is_pending_validation"] is True
    pid = creation.json()["id"]

    suppression = client.delete(f"/api/v1/participations/{pid}")
    assert suppression.status_code == 204
    assert db_session.query(AdminActionLog).count() == 1


def test_get_missing_404(client):
    assert client.get("/api/v1/participations/9999").status_code == 404


def test_is_pending_validation_est_force_a_la_creation(client):
    """FR-016 — et un client qui tente de poser `false` lui-même ne le peut pas."""
    payload = _payload()
    payload["is_pending_validation"] = False
    resp = client.post("/api/v1/participations", json=payload)
    assert resp.status_code == 201
    assert resp.json()["is_pending_validation"] is True


def test_distance_km_saisie_est_transmise_a_l_epreuve(client):
    """FR-009 — distance totale des disciplines sans format normalisé."""
    payload = _payload(bib="88")
    payload["event_type"] = "raid-multisport"
    payload["distance_km"] = 42.5
    resp = client.post("/api/v1/participations", json=payload)
    assert resp.status_code == 201
    assert resp.json()["course"]["distance_km"] == 42.5


def test_sortie_porte_les_nouveaux_champs(client):
    payload = _payload(bib="99")
    payload["team_name"] = "Les Foulées"
    payload["evidence_url"] = "https://club.example/resultats"
    resp = client.post("/api/v1/participations", json=payload)
    body = resp.json()
    assert body["team_name"] == "Les Foulées"
    assert body["evidence_url"] == "https://club.example/resultats"


def test_evidence_url_ne_cree_aucune_source_de_scraping(client, db_session):
    """research.md D5 — le lien de vérification n'est jamais une CourseSource :
    sinon `attach` la poserait active sur cette épreuve neuve, qui entrerait
    dans le circuit de re-scrape avec `provider="manuel"`."""
    from app.repositories import course_repository

    payload = _payload(bib="100", nom="VERIF")
    payload["evidence_url"] = "https://club.example/resultats-officiels"
    resp = client.post("/api/v1/participations", json=payload)
    course_id = resp.json()["course"]["id"]

    course = course_repository.get(db_session, course_id)
    assert course.sources == []
    assert course.provider == ""
    assert course.source_url == ""


def test_is_tcn_expose_le_verdict_du_backend(client, db_session):
    """Le front n'a plus à deviner : le backend tranche et le dit."""
    client.post("/api/v1/participations", json=_payload(bib="1", nom="DUPONT", club="TRI CLUB NANTAIS"))
    client.post("/api/v1/participations", json=_payload(bib="2", nom="MARTIN", club="RACING CLUB NANTAIS *"))
    valider_toutes_les_participations(db_session)

    rows = client.get("/api/v1/participations").json()
    par_club = {r["club"]: r["is_tcn"] for r in rows}

    assert par_club["TRI CLUB NANTAIS"] is True
    assert par_club["RACING CLUB NANTAIS *"] is False


def test_stats_is_null_when_provider_is_not_eligible(client):
    """Une saisie manuelle n'ouvre jamais l'état détaillé, quel que soit son contenu (FR-003)."""
    pid = client.post("/api/v1/participations", json=_payload()).json()["id"]
    assert client.get(f"/api/v1/participations/{pid}").json()["stats"] is None


def _scraped(bib, nom="DUPONT", club="TCN", **kw) -> ScrapedResult:
    """Résultat scrapé d'un fournisseur éligible aux statistiques détaillées.

    Construit hors de `POST /participations` (#565) : depuis le correctif,
    cette route force toujours `provider="manuel"`, jamais éligible
    (`core/splits_reliability.MANUAL_PROVIDER`) — ces tests visent
    `participation_stats_service`, pas la garde de la route, donc le
    fournisseur légitime passe par le chemin d'import (`scrape_service`).
    """
    base = dict(
        source_url="https://raceresult.example/nantes",
        provider="raceresult",
        athlete_name=nom,
        athlete_firstname="Jean",
        gender="M",
        club=club,
        event_name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        bib_number=bib,
        category="V1H",
        rank_overall=10,
        total_time="01:59:00",
        swim_time="00:20:00",
        bike_time="01:00:00",
        run_time="00:39:00",
    )
    base.update(kw)
    return ScrapedResult(**base)


def test_stats_is_null_for_a_relay(client, db_session):
    participation = scrape_service.save_one(db_session, _scraped(bib="9", is_relay=True))
    body = client.get(f"/api/v1/participations/{participation.id}").json()
    assert body["stats"] is None


def test_stats_is_populated_for_an_eligible_course(client, db_session):
    scrape_service.save_one(db_session, _scraped(bib="1", nom="DUPONT"))
    participation = scrape_service.save_one(db_session, _scraped(bib="2", nom="MARTIN"))

    stats = client.get(f"/api/v1/participations/{participation.id}").json()["stats"]

    assert stats is not None
    assert set(stats) == {"segments", "ranking_evolution", "comparison", "improvement"}


def test_stats_comparison_rows_carry_raw_seconds_additively(client, db_session):
    """US4 (#466) : extension additive de ComparisonRow, ne casse pas la forme existante."""
    scrape_service.save_one(db_session, _scraped(bib="4", nom="DUPONT"))
    participation = scrape_service.save_one(db_session, _scraped(bib="5", nom="MARTIN"))

    stats = client.get(f"/api/v1/participations/{participation.id}").json()["stats"]

    assert stats["comparison"]
    row = stats["comparison"][0]
    assert set(row) == {"position_label", "rank", "percentages", "mine_seconds", "theirs_seconds"}
    assert set(row["mine_seconds"]) == set(row["percentages"])
    assert set(row["theirs_seconds"]) == set(row["percentages"])


def test_stats_ranking_evolution_steps_carry_cumulative_seconds(client, db_session):
    """US5 (#466) : extension additive de RankingEvolutionStep."""
    scrape_service.save_one(db_session, _scraped(bib="6", nom="DUPONT"))
    participation = scrape_service.save_one(db_session, _scraped(bib="7", nom="MARTIN"))

    stats = client.get(f"/api/v1/participations/{participation.id}").json()["stats"]

    assert stats["ranking_evolution"]
    step = stats["ranking_evolution"][0]
    assert set(step) == {"segment", "scratch_position", "segment_position", "cumulative_seconds"}
    assert step["cumulative_seconds"] == 20 * 60


def test_stats_ignores_club_membership(client, db_session):
    """FR-004 : les splits sont déjà publics ailleurs, la page n'ajoute aucune confidentialité."""
    participation = scrape_service.save_one(
        db_session, _scraped(bib="3", nom="MARTIN", club="ASPTT")
    )

    body = client.get(f"/api/v1/participations/{participation.id}").json()

    assert body["is_tcn"] is False
    assert body["stats"] is not None


def test_course_listing_carries_the_field_without_computing_it(client, db_session):
    """Le champ est additif partout où `ParticipationOut` est sérialisé ; le calcul, lui, ne l'est pas."""
    participation = scrape_service.save_one(db_session, _scraped(bib="4"))

    rows = client.get(f"/api/v1/courses/{participation.course_id}").json()["participations"]

    assert [row["stats"] for row in rows] == [None]
