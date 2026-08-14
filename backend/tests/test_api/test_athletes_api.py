

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
