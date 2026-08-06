

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
