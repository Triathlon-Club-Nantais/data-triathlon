

from datetime import date


def test_la_lecture_publique_ne_rend_aucune_date_de_naissance(client, db_session):
    """FR-025 (#117) — la porte que garde `athletes:read`.

    Enrichir `AthleteBrief` de `birth_date` publierait la date de naissance de
    chaque coureur du club sur une route ouverte, et viderait du même geste le
    pouvoir `athletes:read` de son objet. Ce test est ce qui l'interdit.
    """
    from datetime import date

    from app.repositories import athlete_repository

    athlete_repository.get_or_create(
        db_session, nom="PRIVE", prenom="Paul", birth_date=date(1988, 3, 2)
    )
    db_session.commit()

    liste = client.get("/api/v1/athletes", params={"name": "prive"}).json()
    detail = client.get(f"/api/v1/athletes/{liste[0]['id']}").json()

    assert liste and "birth_date" not in liste[0]
    assert "birth_date" not in detail.get("athlete", detail)


def test_fiche_athlete_rend_une_participation_pendante_mais_pas_son_rang_dans_le_classement(
    client, db_session
):
    """#270, FR-019/FR-021 — la fiche athlète est la seule surface qui montre
    une participation pendante ; `course_finishers` ne la compte pas."""
    from datetime import date

    from app.repositories import athlete_repository, course_repository, participation_repository

    athlete = athlete_repository.get_or_create(db_session, nom="PENDANT", prenom="Léa", club="TCN")
    autre = athlete_repository.get_or_create(db_session, nom="AUTRE", prenom="Marc", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="Tri Pendant", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=autre.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1,
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="2",
        club="TCN", status="finisher", rank_overall=2, is_pending_validation=True,
    )
    db_session.commit()

    detail = client.get(f"/api/v1/athletes/{athlete.id}").json()

    assert len(detail["participations"]) == 1
    participation = detail["participations"][0]
    assert participation["is_pending_validation"] is True
    # Un seul finisher classé (validé) sur cette course : le sien n'y entre pas.
    assert participation["course_finishers"] == 1


# ── GET /athletes/season-activity (issue #274) ───────────────────────────────


def _epreuve(db_session, nom, event_date=None):
    from app.repositories import course_repository

    if event_date is None:
        event_date = date(2025, 10, 1)
    course = course_repository.get_or_create(
        db_session, name=nom, event_date=event_date, event_type="triathlon-m",
        source_url=f"https://k/{nom}", provider="klikego",
    )
    db_session.flush()
    return course


def _inscrit(db_session, athlete, course, dossard, club="Triathlon Club Nantais"):
    from app.repositories import participation_repository

    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number=dossard, club=club,
    )
    db_session.flush()


def test_season_activity_ne_rend_que_les_actifs_de_la_saison_scopes_club(client, db_session):
    from app.repositories import athlete_repository

    course = _epreuve(db_session, "Saison 2025", date(2025, 10, 1))
    membre = athlete_repository.get_or_create(db_session, nom="ACTIF", prenom="A", club="Triathlon Club Nantais")
    exterieur = athlete_repository.get_or_create(db_session, nom="EXTERIEUR", prenom="E", club="Un Autre Club")
    db_session.commit()
    _inscrit(db_session, membre, course, "1")
    _inscrit(db_session, exterieur, course, "2", club="Un Autre Club")
    db_session.commit()

    resp = client.get(
        "/api/v1/athletes/season-activity", params={"scope": "club", "seasons": "2025"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert [a["nom"] for a in body] == ["ACTIF"]
    assert body[0]["participation_count"] == 1
    assert body[0]["total_count"] == 1
    assert body[0]["validated_count"] == 1
    assert body[0]["club_affiliated_count"] == 1


def test_season_activity_expose_trois_compteurs_distincts_quand_ils_divergent(client, db_session):
    """#709 — `total_count` compte tout, `validated_count`/`club_affiliated_count`
    filtrent, et `participation_count` reste égal à `club_affiliated_count`
    (compat, research.md D3)."""
    from app.repositories import athlete_repository

    course_affiliee = _epreuve(db_session, "Affiliée", date(2025, 9, 15))
    course_sans_affiliation = _epreuve(db_session, "Sans affiliation", date(2025, 10, 1))
    athlete = athlete_repository.get_or_create(db_session, nom="DIVERGENT", prenom="D", club="Triathlon Club Nantais")
    db_session.commit()
    _inscrit(db_session, athlete, course_affiliee, "1")
    _inscrit(db_session, athlete, course_sans_affiliation, "2", club=None)
    db_session.commit()

    resp = client.get(
        "/api/v1/athletes/season-activity", params={"scope": "club", "seasons": "2025"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["total_count"] == 2
    assert body[0]["validated_count"] == 2
    assert body[0]["club_affiliated_count"] == 1
    assert body[0]["participation_count"] == 1


def test_season_activity_saison_sans_activite_rend_une_liste_vide(client, db_session):
    resp = client.get(
        "/api/v1/athletes/season-activity", params={"scope": "club", "seasons": "2019"}
    )

    assert resp.status_code == 200
    assert resp.json() == []


def test_season_activity_refuse_l_anonyme(client, db_session):
    """#811 — la route exige désormais `pages:preview` ; retrait explicite du
    cookie superutilisateur que `session_de_saisie` (autouse) pose sinon."""
    client.cookies.clear()

    resp = client.get("/api/v1/athletes/season-activity")

    assert resp.status_code == 401


def test_season_activity_season_validated_null_par_defaut(client, db_session):
    """#709 — aucune validation en base : `season_validated` reste `False`/absent, jamais une erreur."""
    from app.repositories import athlete_repository

    course = _epreuve(db_session, "Saison 2025", date(2025, 10, 1))
    membre = athlete_repository.get_or_create(db_session, nom="ACTIF", prenom="A", club="Triathlon Club Nantais")
    db_session.commit()
    _inscrit(db_session, membre, course, "1")
    db_session.commit()

    resp = client.get(
        "/api/v1/athletes/season-activity", params={"scope": "club", "seasons": "2025"}
    )

    assert resp.status_code == 200
    assert resp.json()[0]["season_validated"] is False


def test_season_activity_season_validated_vrai_apres_validation(client, db_session):
    from app.repositories import athlete_repository, season_validation_repository, user_repository

    course = _epreuve(db_session, "Saison 2025", date(2025, 10, 1))
    membre = athlete_repository.get_or_create(db_session, nom="ACTIF", prenom="A", club="Triathlon Club Nantais")
    auteur = user_repository.create(db_session, email="admin@exemple.fr")
    db_session.commit()
    _inscrit(db_session, membre, course, "1")
    season_validation_repository.create(
        db_session, athlete_id=membre.id, season=2025, validated_by_user_id=auteur.id
    )
    db_session.commit()

    resp = client.get(
        "/api/v1/athletes/season-activity", params={"scope": "club", "seasons": "2025"}
    )

    assert resp.status_code == 200
    assert resp.json()[0]["season_validated"] is True


def test_season_activity_season_validated_absent_sur_plusieurs_saisons(client, db_session):
    """research.md D9 — le statut est mono-saison ; sur une sélection multiple, `null`."""
    from app.repositories import athlete_repository

    course = _epreuve(db_session, "Saison 2025", date(2025, 10, 1))
    membre = athlete_repository.get_or_create(db_session, nom="ACTIF", prenom="A", club="Triathlon Club Nantais")
    db_session.commit()
    _inscrit(db_session, membre, course, "1")
    db_session.commit()

    resp = client.get(
        "/api/v1/athletes/season-activity", params={"scope": "club", "seasons": "2024,2025"}
    )

    assert resp.status_code == 200
    assert resp.json()[0]["season_validated"] is None


def test_season_activity_federal_only_retire_les_disciplines_hors_federation(client, db_session):
    """#382 — même paramètre et même défaut neutre que sur /dashboard et /club (#76)."""
    from app.repositories import athlete_repository, course_repository

    course_tri = _epreuve(db_session, "Triathlon", date(2025, 9, 15))
    course_trail = course_repository.get_or_create(
        db_session, name="Trail", event_date=date(2025, 9, 20), event_type="trail",
        source_url="https://k/Trail", provider="klikego",
    )
    db_session.flush()
    triathlete = athlete_repository.get_or_create(db_session, nom="TRIATHLETE", prenom="T", club="Triathlon Club Nantais")
    traileur = athlete_repository.get_or_create(db_session, nom="TRAILEUR", prenom="T", club="Triathlon Club Nantais")
    db_session.commit()
    _inscrit(db_session, triathlete, course_tri, "1")
    _inscrit(db_session, traileur, course_trail, "2")
    db_session.commit()

    resp = client.get(
        "/api/v1/athletes/season-activity",
        params={"scope": "club", "seasons": "2025", "federal_only": "true"},
    )

    assert resp.status_code == 200
    assert [a["nom"] for a in resp.json()] == ["TRIATHLETE"]


# ── GET /athletes/search (issue #484, NAV-8) ─────────────────────────────────


def test_search_rend_le_compte_de_participations_sans_date_de_naissance(client, db_session):
    from app.repositories import athlete_repository

    course = _epreuve(db_session, "Recherche")
    athlete = athlete_repository.get_or_create(
        db_session, nom="HERRMANN", prenom="Mathieu", birth_date=date(1990, 1, 1), club="TCN"
    )
    db_session.commit()
    _inscrit(db_session, athlete, course, "1")

    resp = client.get("/api/v1/athletes/search", params={"q": "herr"})

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["nom"] == "HERRMANN"
    assert body[0]["participation_count"] == 1
    assert "birth_date" not in body[0]


def test_search_classe_par_pertinence_avant_le_volume(client, db_session):
    """Preuve de terrain NAV-8 (audit § 5) rejouée à l'API."""
    from app.repositories import athlete_repository

    prefixe = athlete_repository.get_or_create(db_session, nom="HERRMANN", prenom="Mathieu")
    milieu = athlete_repository.get_or_create(db_session, nom="CHERRUEAU", prenom="Yves")
    db_session.commit()
    _inscrit(db_session, prefixe, _epreuve(db_session, "P1"), "1")
    for i in range(5):
        _inscrit(db_session, milieu, _epreuve(db_session, f"P-milieu-{i}"), "1")

    resp = client.get("/api/v1/athletes/search", params={"q": "herr"})

    assert [a["nom"] for a in resp.json()] == ["HERRMANN", "CHERRUEAU"]


def test_search_refuse_un_terme_de_moins_de_deux_caracteres(client):
    resp = client.get("/api/v1/athletes/search", params={"q": "h"})
    assert resp.status_code == 422


def test_search_refuse_l_absence_de_terme(client):
    resp = client.get("/api/v1/athletes/search")
    assert resp.status_code == 422


def test_search_respecte_la_limite(client, db_session):
    from app.repositories import athlete_repository

    for i in range(3):
        athlete_repository.get_or_create(db_session, nom=f"TESTLIM{i}", prenom="A")
    db_session.commit()

    resp = client.get("/api/v1/athletes/search", params={"q": "testlim", "limit": 2})

    assert len(resp.json()) == 2


def test_search_nest_pas_capturee_par_la_route_athlete_id(client, db_session):
    """Précédence de route, même piège que `/athletes/season-activity` (#274) :
    `search` doit se résoudre avant `{athlete_id}` (int), sinon FastAPI rend
    422 sur `search` comme identifiant invalide."""
    resp = client.get("/api/v1/athletes/search", params={"q": "zzzzz"})
    assert resp.status_code == 200
    assert resp.json() == []


# ── GET /athletes/{id} : filtres saison / discipline (#502) ──────────────────


def _athlete_trois_saisons(db_session):
    """Le même corpus que le test de repository, vu depuis la route."""
    from app.repositories import athlete_repository, course_repository, participation_repository

    athlete = athlete_repository.get_or_create(db_session, nom="BANDE", prenom="Bruno")
    db_session.flush()
    corpus = [
        ("Tri 2025", date(2025, 10, 5), "triathlon-m"),
        ("Trail 2025", date(2025, 10, 12), "trail"),
        ("Tri 2024", date(2024, 10, 5), "triathlon-m"),
    ]
    for i, (nom, jour, type_epreuve) in enumerate(corpus, start=1):
        course = course_repository.get_or_create(
            db_session, name=nom, event_date=jour, event_type=type_epreuve,
            source_url=f"https://k/{nom}", provider="klikego",
        )
        db_session.flush()
        participation_repository.create(
            db_session, athlete_id=athlete.id, course_id=course.id,
            bib_number=str(i), club="Triathlon Club Nantais",
        )
    db_session.commit()
    return athlete


def test_fiche_athlete_sans_parametre_rend_la_carriere_entiere(client, db_session):
    """Non-régression du contrat publié : les deux filtres de #502 sont neutres
    par défaut, la fiche athlète ne change pas de comportement."""
    athlete = _athlete_trois_saisons(db_session)

    detail = client.get(f"/api/v1/athletes/{athlete.id}").json()

    assert len(detail["participations"]) == 3


def test_fiche_athlete_filtre_par_saison(client, db_session):
    athlete = _athlete_trois_saisons(db_session)

    detail = client.get(
        f"/api/v1/athletes/{athlete.id}", params={"seasons": "2025"}
    ).json()

    assert sorted(p["course"]["name"] for p in detail["participations"]) == [
        "Trail 2025",
        "Tri 2025",
    ]


def test_fiche_athlete_federal_only_retire_les_disciplines_hors_federation(client, db_session):
    athlete = _athlete_trois_saisons(db_session)

    detail = client.get(
        f"/api/v1/athletes/{athlete.id}", params={"federal_only": "true"}
    ).json()

    assert sorted(p["course"]["name"] for p in detail["participations"]) == [
        "Tri 2024",
        "Tri 2025",
    ]


def test_fiche_athlete_combine_les_deux_filtres(client, db_session):
    athlete = _athlete_trois_saisons(db_session)

    detail = client.get(
        f"/api/v1/athletes/{athlete.id}",
        params={"seasons": "2025", "federal_only": "true"},
    ).json()

    assert [p["course"]["name"] for p in detail["participations"]] == ["Tri 2025"]


def test_fiche_athlete_saisons_non_parsables_valent_toutes_saisons(client, db_session):
    """`parse_seasons` ignore les valeurs non entières et rend une liste vide,
    qui vaut « pas de filtre » — pas de 422, pas de 500."""
    athlete = _athlete_trois_saisons(db_session)

    resp = client.get(f"/api/v1/athletes/{athlete.id}", params={"seasons": "abc"})

    assert resp.status_code == 200
    assert len(resp.json()["participations"]) == 3
