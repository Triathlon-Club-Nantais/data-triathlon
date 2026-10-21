"""Contrat des routes de lecture d'une épreuve (issue #163).

Le classement est paginé **par défaut** — un changement de comportement assumé
de `/api/v1/courses/{id}`, assorti de l'échappatoire explicite `page_size=all`.
La synthèse, elle, est une route nouvelle qui n'accepte aucun paramètre.
"""
from datetime import date

import pytest

from app.models.course import Course
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


def test_course_brief_exposes_stored_weather(client, db_session, epreuve):
    """#1370 : la météo stockée, lue sans aucun appel réseau."""
    epreuve.weather_temperature_c = 18.0
    epreuve.weather_wind_kmh = 11.3
    epreuve.weather_precipitation_mm = 0.4
    db_session.commit()

    course = client.get(f"/api/v1/courses/{epreuve.id}").json()["course"]

    assert (course["weather_temperature_c"], course["weather_wind_kmh"],
            course["weather_precipitation_mm"]) == (18.0, 11.3, 0.4)


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


def test_classement_et_synthese_excluent_une_participation_pendante(
    client, epreuve, db_session
):
    """#270, FR-021 — au niveau contrat HTTP, pas seulement au repository."""
    avant = client.get(f"/api/v1/courses/{epreuve.id}?page_size=all").json()
    synthese_avant = client.get(f"/api/v1/courses/{epreuve.id}/summary").json()

    athlete = athlete_repository.get_or_create(
        db_session, nom="PENDANT", prenom="Test", club="ASPTT"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=epreuve.id, bib_number="pendant",
        club="ASPTT", status="finisher", rank_overall=1, total_time="01:00:00",
        is_pending_validation=True,
    )
    db_session.commit()

    apres = client.get(f"/api/v1/courses/{epreuve.id}?page_size=all").json()
    synthese_apres = client.get(f"/api/v1/courses/{epreuve.id}/summary").json()

    assert apres["total"] == avant["total"]
    assert synthese_apres["total"] == synthese_avant["total"]


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
    """Trois épreuves, trois dates, deux types — de quoi croiser les filtres.

    Rend `{nom: id}` — inutile aux tests de filtre par nom/date/type, mais
    c'est ce qui permet à ceux du filtre par `id` de cibler une épreuve
    précise sans deviner sa clé primaire.
    """
    ids = {}
    for nom, jour, type_epreuve in (
        ("Triathlon de Nantes", date(2026, 5, 1), "triathlon-m"),
        ("Triathlon de Vierzon", date(2026, 6, 1), "triathlon-s"),
        ("Duathlon de Nantes", date(2026, 7, 1), "duathlon"),
    ):
        course = course_repository.get_or_create(
            db_session, name=nom, event_date=jour, event_type=type_epreuve
        )
        ids[nom] = course.id
    db_session.commit()
    return ids


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


def test_catalogue_filtre_par_id(client, catalogue):
    """#718 — retrouver une épreuve précise sans la chercher par nom."""
    cible = catalogue["Triathlon de Vierzon"]

    noms = [c["name"] for c in client.get(f"/api/v1/courses?id={cible}").json()]

    assert noms == ["Triathlon de Vierzon"]


def test_catalogue_filtre_par_id_inconnu_rend_une_liste_vide(client, catalogue):
    assert client.get("/api/v1/courses?id=999999").json() == []


def test_catalogue_id_illisible_est_une_erreur_d_usage(client, catalogue):
    """Contrairement à `date_from`, `id` n'a pas de repli silencieux : une
    valeur qui n'est pas un entier est une erreur d'usage, comme `page`."""
    assert client.get("/api/v1/courses?id=abc").status_code == 422


# ── GET /courses/count — le total qui rend « page 1 sur 7 » ──────────────────


def test_compte_le_catalogue_entier(client, catalogue):
    """Passe aussi parce que `/courses/count` est déclarée avant `/courses/{id}` :
    dans l'autre ordre, « count » se lirait comme un identifiant et rendrait 422."""
    assert client.get("/api/v1/courses/count").json() == {"total": 3}


def test_compte_aux_memes_filtres_que_la_liste(client, catalogue):
    """Un total qui ignorerait les filtres annoncerait des pages vides."""
    cible = catalogue["Triathlon de Vierzon"]
    for query in (
        "?name=nantes",
        "?event_type=triathlon-m",
        "?date_to=2026-05-31",
        f"?id={cible}",
    ):
        liste = client.get(f"/api/v1/courses{query}").json()
        assert client.get(f"/api/v1/courses/count{query}").json()["total"] == len(liste)


def test_compte_ignore_la_pagination(client, catalogue):
    """`count` n'est pas paginé : c'est ce qui permet de feuilleter sans le refaire."""
    assert client.get("/api/v1/courses/count?page=2&page_size=1").json() == {"total": 3}


# ── GET /courses?unreliable=true — filtre de revalidation (#119) ──────────────


def _epreuve(db_session, **colonnes) -> Course:
    """Une épreuve minimale pour le filtre de revalidation (#119)."""
    course = Course(
        name=colonnes.pop("name", "Épreuve"),
        event_type="triathlon-m",
        event_date=colonnes.pop("event_date", date(2026, 6, 1)),
        **colonnes,
    )
    db_session.add(course)
    db_session.commit()
    return course


def test_le_catalogue_filtre_les_epreuves_douteuses(client, db_session):
    douteuse = _epreuve(db_session, name="Douteuse", is_reliable_computed=False)
    _epreuve(db_session, name="Fiable", is_reliable_computed=True)

    reponse = client.get("/api/v1/courses", params={"unreliable": "true"})

    assert reponse.status_code == 200
    assert [c["id"] for c in reponse.json()] == [douteuse.id]


def test_le_catalogue_rend_les_anomalies_de_chaque_epreuve_douteuse(client, db_session):
    """AC2 — l'écran décode `quality_issues`, encore faut-il que la route le rende."""
    _epreuve(
        db_session,
        name="Douteuse",
        is_reliable_computed=False,
        quality_issues={"rank_gap": 3, "duplicate_bib": 1},
    )

    corps = client.get("/api/v1/courses", params={"unreliable": "true"}).json()

    assert corps[0]["quality_issues"] == {"rank_gap": 3, "duplicate_bib": 1}
    assert corps[0]["is_reliable"] is False


def test_sans_le_parametre_la_reponse_est_inchangee(client, db_session):
    """Principe IV — l'ajout est additif, aucun appelant existant ne bouge."""
    _epreuve(db_session, name="Douteuse", is_reliable_computed=False)
    _epreuve(db_session, name="Fiable", is_reliable_computed=True)

    assert len(client.get("/api/v1/courses").json()) == 2


def test_le_comptage_suit_le_meme_filtre(client, db_session):
    _epreuve(db_session, name="Douteuse 1", is_reliable_computed=False)
    _epreuve(db_session, name="Douteuse 2", is_reliable_computed=False)
    _epreuve(db_session, name="Fiable", is_reliable_computed=True)

    reponse = client.get("/api/v1/courses/count", params={"unreliable": "true"})

    assert reponse.status_code == 200
    assert reponse.json()["total"] == 2


def test_awaiting_review_keeps_only_courses_without_a_human_verdict(client, db_session):
    """#1232: the quality queue shows what its nav badge counts."""
    waiting = _epreuve(db_session, name="À revoir", is_reliable_computed=False)
    _epreuve(db_session, name="Jugée douteuse", is_reliable_computed=False, reliability_override=False)
    _epreuve(db_session, name="Jugée fiable", is_reliable_computed=False, reliability_override=True)
    _epreuve(db_session, name="Fiable", is_reliable_computed=True)
    _epreuve(db_session, name="Jamais évaluée")

    listed = client.get("/api/v1/courses", params={"awaiting_review": "true"}).json()
    counted = client.get("/api/v1/courses/count", params={"awaiting_review": "true"}).json()
    badge = {"total": client.get("/api/v1/admin/badge-counts").json()["quality"]}

    assert [c["id"] for c in listed] == [waiting.id]
    assert counted == badge == {"total": 1}


def test_event_type_to_review_keeps_only_fallback_typed_courses(client, db_session):
    """#1744: the review queue lists what the triathlon fallback typed."""
    fallback = _epreuve(db_session, name="Repli", event_type_origin="fallback")
    _epreuve(db_session, name="Classée", event_type_origin="classified")
    _epreuve(db_session, name="Confirmée", event_type_origin="manual")

    listed = client.get("/api/v1/courses", params={"event_type_to_review": "true"}).json()
    counted = client.get("/api/v1/courses/count", params={"event_type_to_review": "true"}).json()
    everything = client.get("/api/v1/courses").json()

    assert [c["id"] for c in listed] == [fallback.id]
    assert counted == {"total": 1}
    assert sorted(c["event_type_origin"] for c in everything) == ["classified", "fallback", "manual"]


def test_la_file_est_triee_par_date_la_plus_recente(client, db_session):
    """AC1 — le tri vient de `list_all`, ce test le verrouille au niveau route."""
    ancienne = _epreuve(
        db_session, name="Ancienne", event_date=date(2025, 3, 1), is_reliable_computed=False
    )
    recente = _epreuve(
        db_session, name="Récente", event_date=date(2026, 9, 1), is_reliable_computed=False
    )

    corps = client.get("/api/v1/courses", params={"unreliable": "true"}).json()

    assert [c["id"] for c in corps] == [recente.id, ancienne.id]


# ── Fiabilité et écart des inters (issue #486, RES-10) ───────────────────────


def test_le_classement_publie_l_ecart_de_chaque_ligne(client, db_session):
    """`split_gap_ratio` est une **mesure**, publiée par ligne — jamais un verdict."""
    course = course_repository.get_or_create(
        db_session, name="Tri Écart", event_date=date(2026, 8, 2), event_type="triathlon-m"
    )
    athlete = athlete_repository.get_or_create(
        db_session, nom="ECART", prenom="Test", gender="M", club="ASPTT"
    )
    participation_repository.create(
        db_session,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number="1",
        club="ASPTT",
        status="finisher",
        total_time="01:00:00",
        splits={
            "swim": "00:15:00",
            "t1": "00:01:00",
            "bike": "00:30:00",
            "t2": "00:03:00",
            "run": "00:10:00",
        },
    )
    db_session.commit()

    corps = client.get(f"/api/v1/courses/{course.id}").json()

    assert corps["participations"][0]["split_gap_ratio"] == pytest.approx(60 / 3600)


def test_l_ecart_est_nul_quand_la_ligne_n_est_pas_evaluable(client, epreuve):
    """L'épreuve de la fixture n'a aucun split : rien à mesurer, donc `null`."""
    corps = client.get(f"/api/v1/courses/{epreuve.id}").json()

    assert all(p["split_gap_ratio"] is None for p in corps["participations"])


def test_la_synthese_publie_la_mediane_des_ecarts(client, epreuve):
    corps = client.get(f"/api/v1/courses/{epreuve.id}/summary").json()

    assert "split_gap_median" in corps
    assert corps["split_gap_median"] is None


def test_la_liste_des_epreuves_porte_la_fiabilite(client, db_session):
    """`EventOut` ne portait aucun champ de fiabilité : la liste ne pouvait pas marquer.

    `quality_issues` est une colonne JSON — elle doit rester **hors** du `GROUP BY`,
    PostgreSQL n'ayant pas d'opérateur d'égalité sur `json`.
    """
    course = _epreuve(
        db_session,
        name="Douteuse avec anomalies",
        is_reliable_computed=False,
        quality_issues={"duplicate_bib": 3},
    )
    athlete = athlete_repository.get_or_create(
        db_session, nom="LISTE", prenom="Test", gender="M", club="ASPTT"
    )
    participation_repository.create(
        db_session,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number="1",
        club="ASPTT",
        status="finisher",
        total_time="01:00:00",
    )
    # Compteur dénormalisé (#623) : posé directement, fixture hors import.
    course.participation_count, course.tcn_count = 1, 0
    db_session.commit()

    items = client.get("/api/v1/courses/events").json()["items"]
    ligne = next(item for item in items if item["id"] == course.id)

    assert ligne["is_reliable"] is False
    assert ligne["quality_issues"] == {"duplicate_bib": 3}


def test_une_epreuve_jamais_evaluee_porte_des_champs_nuls(client, db_session):
    """`null` est un état normal : les imports antérieurs au calcul n'ont pas été remplis."""
    course = _epreuve(db_session, name="Jamais évaluée")
    athlete = athlete_repository.get_or_create(
        db_session, nom="NULLE", prenom="Test", gender="M", club="ASPTT"
    )
    participation_repository.create(
        db_session,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number="1",
        club="ASPTT",
        status="finisher",
        total_time="01:00:00",
    )
    # Compteur dénormalisé (#623) : posé directement, fixture hors import.
    course.participation_count, course.tcn_count = 1, 0
    db_session.commit()

    items = client.get("/api/v1/courses/events").json()["items"]
    ligne = next(item for item in items if item["id"] == course.id)

    assert ligne["is_reliable"] is None
    assert ligne["quality_issues"] is None


# ── Filtres club et catégorie (issue #486, RES-11) ───────────────────────────


@pytest.fixture
def epreuve_filtrable(db_session):
    """Deux clubs, deux catégories — de quoi vérifier le cumul et l'exactitude."""
    course = course_repository.get_or_create(
        db_session, name="Tri Filtres API", event_date=date(2026, 8, 3), event_type="triathlon-m"
    )
    lignes = [
        ("BLAINV2", "BLAIN TRIATHLON", "V2"),
        ("BLAINS1", "BLAIN TRIATHLON", "S1"),
        ("JEUNESV2", "BLAIN TRIATHLON JEUNES", "V2"),
    ]
    for nom, club, categorie in lignes:
        athlete = athlete_repository.get_or_create(
            db_session, nom=nom, prenom="Test", gender="M", club=club
        )
        participation_repository.create(
            db_session,
            athlete_id=athlete.id,
            course_id=course.id,
            bib_number=nom,
            club=club,
            category=categorie,
            status="finisher",
            rank_overall=1,
            total_time="01:00:00",
        )
    db_session.commit()
    return course


def test_le_filtre_club_ne_ramasse_pas_les_libelles_voisins(client, epreuve_filtrable):
    corps = client.get(
        f"/api/v1/courses/{epreuve_filtrable.id}", params={"club": "BLAIN TRIATHLON"}
    ).json()

    assert corps["total"] == 2
    assert all(p["club"] == "BLAIN TRIATHLON" for p in corps["participations"])


def test_le_filtre_categorie_restreint_le_classement(client, epreuve_filtrable):
    corps = client.get(
        f"/api/v1/courses/{epreuve_filtrable.id}", params={"category": "V2"}
    ).json()

    assert corps["total"] == 2


def test_les_deux_filtres_se_cumulent_sur_la_route(client, epreuve_filtrable):
    corps = client.get(
        f"/api/v1/courses/{epreuve_filtrable.id}",
        params={"club": "BLAIN TRIATHLON", "category": "V2"},
    ).json()

    assert corps["total"] == 1


def test_une_valeur_inconnue_rend_200_et_une_selection_vide(client, epreuve_filtrable):
    """L'épreuve existe : c'est la sélection qui est vide, pas l'adresse qui est morte."""
    reponse = client.get(
        f"/api/v1/courses/{epreuve_filtrable.id}", params={"club": "CLUB INEXISTANT"}
    )

    assert reponse.status_code == 200
    assert reponse.json()["participations"] == []
    assert reponse.json()["total"] == 0


def test_les_nouveaux_parametres_ont_un_defaut_neutre(client, epreuve_filtrable):
    """Principe V, et additivité du contrat : absents, ils ne filtrent rien."""
    sans = client.get(f"/api/v1/courses/{epreuve_filtrable.id}").json()

    assert sans["total"] == 3
    assert len(sans["participations"]) == 3


def test_la_synthese_ignore_les_filtres_du_classement(client, epreuve_filtrable):
    """La synthèse porte sur l'épreuve **entière** : elle n'accepte aucun paramètre (#163)."""
    corps = client.get(
        f"/api/v1/courses/{epreuve_filtrable.id}/summary", params={"club": "BLAIN TRIATHLON"}
    ).json()

    assert corps["total"] == 3


# ── GET /courses/{id}?gender= : place par sexe (#1645) ───────────────────────


def _row(db_session, course, nom, *, gender, **columns):
    athlete = athlete_repository.get_or_create(
        db_session, nom=nom, prenom="Test", gender=gender, club="ASPTT"
    )
    return participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number=nom,
        club="ASPTT", **{"status": "finisher", "total_time": "01:00:00", **columns},
    )


@pytest.fixture
def mixed_course(db_session):
    """Four ranked women (gender ranks 1, 2, 4, 5), a man, a row without sex,
    a DNF woman and a woman's relay without `rank_gender`."""
    course = course_repository.get_or_create(
        db_session, name="Tri Mixte", event_date=date(2026, 8, 2), event_type="triathlon-m"
    )
    women = [
        _row(db_session, course, f"FEMME{index}", gender="F", rank_overall=overall, rank_gender=gender_rank)
        for index, (overall, gender_rank) in enumerate([(10, 1), (11, 2), (15, 4), (19, 5)], start=1)
    ]
    others = {
        "man": _row(db_session, course, "HOMME", gender="M", rank_overall=1, rank_gender=1),
        "unknown": _row(db_session, course, "INCONNU", gender="", rank_overall=2),
        "relay": _row(db_session, course, "RELAIS", gender="F", rank_overall=12, is_relay=True),
        "dnf": _row(db_session, course, "ABANDON", gender="F", status="DNF", total_time=None),
    }
    db_session.commit()
    return course, women, others


def _women(client, course, query=""):
    return client.get(f"/api/v1/courses/{course.id}?gender=F{query}").json()


def test_get_course_without_gender_is_unchanged(client, mixed_course):
    course, women, others = mixed_course

    rows = client.get(f"/api/v1/courses/{course.id}").json()["participations"]

    assert [p["id"] for p in rows] == [
        others["man"].id, others["unknown"].id, women[0].id, women[1].id,
        others["relay"].id, women[2].id, women[3].id, others["dnf"].id,
    ]
    assert {(p["gender_place"], p["gender_place_official"]) for p in rows} == {(None, None)}


def test_get_course_gender_uses_official_rank_gender(client, mixed_course):
    course, women, others = mixed_course

    body = _women(client, course)
    rows = body["participations"]

    assert [p["id"] for p in rows] == [w.id for w in women] + [others["relay"].id, others["dnf"].id]
    assert [p["gender_place"] for p in rows] == [1, 2, 4, 5, None, None]
    assert all(p["gender_place_official"] is True for p in rows[:4])
    assert body["total"] == 6


def test_get_course_gender_recalculates_when_one_rank_gender_missing(client, db_session, mixed_course):
    course, women, _ = mixed_course
    women[2].rank_gender = None
    db_session.commit()

    rows = _women(client, course)["participations"]

    assert [p["id"] for p in rows[:4]] == [w.id for w in women]
    assert [p["gender_place"] for p in rows[:4]] == [1, 2, 3, 4]
    assert all(p["gender_place_official"] is False for p in rows[:4])


def test_get_course_gender_recalculates_when_rank_gender_collides(client, db_session, mixed_course):
    course, women, _ = mixed_course
    women[2].rank_gender = 2
    db_session.commit()

    rows = _women(client, course)["participations"]

    assert [p["gender_place"] for p in rows[:4]] == [1, 2, 3, 4]
    assert all(p["gender_place_official"] is False for p in rows[:4])


def test_get_course_gender_recalculates_place_beyond_field_on_complete_course(
    client, db_session, mixed_course
):
    course, _, _ = mixed_course
    course.quality_issues = {}
    db_session.commit()

    rows = _women(client, course)["participations"]

    assert [p["gender_place"] for p in rows[:4]] == [1, 2, 3, 4]
    assert all(p["gender_place_official"] is False for p in rows[:4])


def test_get_course_gender_keeps_official_gaps_on_partial_course(client, db_session, mixed_course):
    course, _, _ = mixed_course
    course.quality_issues = {"rank_gap": 12}
    db_session.commit()

    rows = _women(client, course)["participations"]

    assert [p["gender_place"] for p in rows[:4]] == [1, 2, 4, 5]
    assert all(p["gender_place_official"] is True for p in rows[:4])


def test_get_course_gender_relay_does_not_switch_to_recalculated(client, mixed_course):
    course, _, others = mixed_course

    rows = _women(client, course)["participations"]

    assert others["relay"].rank_gender is None
    assert rows[0]["gender_place_official"] is True


def test_get_course_gender_place_survives_query_filter(client, mixed_course):
    course, _, _ = mixed_course

    rows = _women(client, course, "&q=FEMME3")["participations"]

    assert [p["gender_place"] for p in rows] == [4]


def test_get_course_gender_place_continues_across_pages(client, mixed_course):
    course, _, _ = mixed_course

    rows = _women(client, course, "&page_size=2&page=2")["participations"]

    assert [p["gender_place"] for p in rows] == [4, 5]


def test_get_course_gender_without_matching_finisher_is_empty(client, epreuve):
    body = _women(client, epreuve)

    assert body["participations"] == []
    assert body["total"] == 0


def test_get_course_gender_filters_pending_rows(client, db_session, mixed_course):
    course, _, _ = mixed_course
    _row(db_session, course, "ATTENTEH", gender="M", rank_overall=3, is_pending_validation=True)
    pending_woman = _row(
        db_session, course, "ATTENTEF", gender="F", rank_overall=4, rank_gender=1,
        is_pending_validation=True,
    )
    db_session.commit()

    pending = _women(client, course)["pending_participations"]

    assert [p["id"] for p in pending] == [pending_woman.id]
    assert pending[0]["gender_place"] is None


def test_get_course_rejects_unknown_gender(client, epreuve):
    assert client.get(f"/api/v1/courses/{epreuve.id}?gender=X").status_code == 422
