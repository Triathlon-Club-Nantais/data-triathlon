

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


def _epreuve(db_session, nom, event_date):
    from app.repositories import course_repository

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
    membre = athlete_repository.get_or_create(db_session, nom="ACTIF", prenom="A")
    exterieur = athlete_repository.get_or_create(db_session, nom="EXTERIEUR", prenom="E")
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


def test_season_activity_saison_sans_activite_rend_une_liste_vide(client, db_session):
    resp = client.get(
        "/api/v1/athletes/season-activity", params={"scope": "club", "seasons": "2019"}
    )

    assert resp.status_code == 200
    assert resp.json() == []


def test_season_activity_accessible_sans_authentification(client, db_session):
    """FR-006 — pas de cookie de session : `client` n'en pose jamais."""
    resp = client.get("/api/v1/athletes/season-activity")

    assert resp.status_code == 200
