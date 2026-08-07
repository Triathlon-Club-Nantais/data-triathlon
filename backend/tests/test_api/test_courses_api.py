"""Contrat des routes de lecture d'une épreuve (issue #163).

Le classement est paginé **par défaut** — un changement de comportement assumé
de `/api/v1/courses/{id}`, assorti de l'échappatoire explicite `page_size=all`.
La synthèse, elle, est une route nouvelle qui n'accepte aucun paramètre.
"""
from datetime import date

import pytest

from app.repositories import athlete_repository, course_repository, participation_repository


@pytest.fixture
def epreuve(db_session):
    """Épreuve de 45 participations : deux pages pleines et une partielle."""
    course = course_repository.get_or_create(
        db_session, name="Tri Contrat", event_date=date(2026, 8, 1), event_type="triathlon-m"
    )
    for index in range(45):
        athlete = athlete_repository.get_or_create(
            db_session, nom=f"NOM{index:03d}", prenom="Test", gender="M", club="ASPTT"
        )
        participation_repository.create(
            db_session,
            athlete_id=athlete.id,
            course_id=course.id,
            bib_number=str(index),
            club="ASPTT",
            category="SEM",
            status="finisher",
            rank_overall=index + 1,
            total_time="01:00:00",
        )
    db_session.commit()
    return course


# ── GET /courses/{id} — classement paginé ────────────────────────────────────


def test_classement_pagine_par_defaut_a_20(client, epreuve):
    body = client.get(f"/api/v1/courses/{epreuve.id}").json()

    assert len(body["participations"]) == 20
    assert body["total"] == 45
    assert body["page"] == 1
    assert body["page_size"] == 20
    # La clé historique `participations` est conservée, elle n'est pas renommée.
    assert "items" not in body
    assert body["course"]["name"] == "Tri Contrat"


def test_classement_page_suivante_poursuit_sans_doublon_ni_trou(client, epreuve):
    page1 = client.get(f"/api/v1/courses/{epreuve.id}?page=1").json()["participations"]
    page2 = client.get(f"/api/v1/courses/{epreuve.id}?page=2").json()["participations"]
    page3 = client.get(f"/api/v1/courses/{epreuve.id}?page=3").json()["participations"]

    ids = [p["id"] for p in page1 + page2 + page3]
    assert len(page3) == 5
    assert len(ids) == len(set(ids)) == 45


def test_classement_page_hors_bornes_rend_une_tranche_vide(client, epreuve):
    body = client.get(f"/api/v1/courses/{epreuve.id}?page=99999").json()

    assert body["participations"] == []
    assert body["total"] == 45


def test_classement_page_size_all_rend_tout_en_une_page(client, epreuve):
    body = client.get(f"/api/v1/courses/{epreuve.id}?page_size=all").json()

    assert len(body["participations"]) == body["total"] == 45
    assert body["page_size"] is None


@pytest.mark.parametrize("page_size", ["0", "-1", "201", "tout", "20.5"])
def test_classement_page_size_invalide_est_une_erreur_d_usage(client, epreuve, page_size):
    resp = client.get(f"/api/v1/courses/{epreuve.id}?page_size={page_size}")

    assert resp.status_code == 422


def test_classement_page_invalide_est_une_erreur_d_usage(client, epreuve):
    assert client.get(f"/api/v1/courses/{epreuve.id}?page=0").status_code == 422


def test_classement_epreuve_inconnue(client):
    assert client.get("/api/v1/courses/999999").status_code == 404


# ── GET /courses/{id}/summary — synthèse d'épreuve entière ───────────────────


def test_synthese_forme_de_reponse(client, epreuve):
    body = client.get(f"/api/v1/courses/{epreuve.id}/summary").json()

    assert body["total"] == 45
    assert body["finishers"] == 45
    assert body["non_finishers"] == body["unknown"] == 0
    assert body["male"] == 45
    assert body["tcn_count"] == 0
    assert body["categories"] == [{"name": "SEM", "count": 45}]
    assert body["clubs"] == [{"name": "ASPTT", "count": 45, "is_tcn": False}]
    assert body["split_keys"] == []
    assert body["histogram"]["bucket_sec"] == 300


def test_synthese_ne_depend_ni_de_la_recherche_ni_de_la_portee(client, epreuve):
    """FR-018 : chercher un nom ne doit pas faire tomber l'histogramme à une barre."""
    nue = client.get(f"/api/v1/courses/{epreuve.id}/summary").json()

    for query in ("?q=NOM001", "?scope=club", "?page=2", "?page_size=5"):
        assert client.get(f"/api/v1/courses/{epreuve.id}/summary{query}").json() == nue


def test_synthese_epreuve_inconnue(client):
    assert client.get("/api/v1/courses/999999/summary").status_code == 404


# ── GET /courses — filtres du catalogue (administration) ─────────────────────


@pytest.fixture
def catalogue(db_session):
    """Trois épreuves, trois dates, deux types — de quoi croiser les filtres."""
    for nom, jour, type_epreuve in (
        ("Triathlon de Nantes", date(2026, 5, 1), "triathlon-m"),
        ("Triathlon de Vierzon", date(2026, 6, 1), "triathlon-s"),
        ("Duathlon de Nantes", date(2026, 7, 1), "duathlon"),
    ):
        course_repository.get_or_create(
            db_session, name=nom, event_date=jour, event_type=type_epreuve
        )
    db_session.commit()


def test_catalogue_filtre_par_nom_partiel(client, catalogue):
    noms = [c["name"] for c in client.get("/api/v1/courses?name=nantes").json()]

    assert sorted(noms) == ["Duathlon de Nantes", "Triathlon de Nantes"]


def test_catalogue_filtre_par_intervalle_de_dates(client, catalogue):
    noms = [
        c["name"]
        for c in client.get("/api/v1/courses?date_from=2026-06-01&date_to=2026-06-30").json()
    ]

    assert noms == ["Triathlon de Vierzon"]


def test_catalogue_croise_nom_type_et_dates(client, catalogue):
    url = "/api/v1/courses?name=nantes&event_type=duathlon&date_from=2026-01-01"
    noms = [c["name"] for c in client.get(url).json()]

    assert noms == ["Duathlon de Nantes"]


def test_catalogue_date_illisible_est_ignoree(client, catalogue):
    """`_parse_date` rend `None` sur une saisie invalide : le filtre disparaît."""
    assert len(client.get("/api/v1/courses?date_from=hier").json()) == 3


# ── GET /courses/count — le total qui rend « page 1 sur 7 » ──────────────────


def test_compte_le_catalogue_entier(client, catalogue):
    """Passe aussi parce que `/courses/count` est déclarée avant `/courses/{id}` :
    dans l'autre ordre, « count » se lirait comme un identifiant et rendrait 422."""
    assert client.get("/api/v1/courses/count").json() == {"total": 3}


def test_compte_aux_memes_filtres_que_la_liste(client, catalogue):
    """Un total qui ignorerait les filtres annoncerait des pages vides."""
    for query in ("?name=nantes", "?event_type=triathlon-m", "?date_to=2026-05-31"):
        liste = client.get(f"/api/v1/courses{query}").json()
        assert client.get(f"/api/v1/courses/count{query}").json()["total"] == len(liste)


def test_compte_ignore_la_pagination(client, catalogue):
    """`count` n'est pas paginé : c'est ce qui permet de feuilleter sans le refaire."""
    assert client.get("/api/v1/courses/count?page=2&page_size=1").json() == {"total": 3}
