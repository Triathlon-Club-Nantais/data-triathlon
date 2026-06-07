from datetime import date

from app.repositories import athlete_repo


def test_get_or_create_creates_then_dedups(db_session):
    a1 = athlete_repo.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    assert a1.id is not None

    # Même identité, casse différente → même athlète
    a2 = athlete_repo.get_or_create(db_session, nom="dupont", prenom="jean")
    assert a2.id == a1.id


def test_birth_date_distinguishes_homonyms(db_session):
    a1 = athlete_repo.get_or_create(
        db_session, nom="MARTIN", prenom="Paul", birth_date=date(1990, 1, 1)
    )
    a2 = athlete_repo.get_or_create(
        db_session, nom="MARTIN", prenom="Paul", birth_date=date(1985, 6, 2)
    )
    assert a1.id != a2.id


def test_get_or_create_updates_current_club(db_session):
    a1 = athlete_repo.get_or_create(db_session, nom="DURAND", prenom="Lucie", club="TCN")
    a2 = athlete_repo.get_or_create(
        db_session, nom="DURAND", prenom="Lucie", club="Triathlon Club Nantais"
    )
    assert a2.id == a1.id
    assert a2.club == "Triathlon Club Nantais"


def test_search_by_name(db_session):
    athlete_repo.get_or_create(db_session, nom="LEROY", prenom="Anne", club="TCN")
    athlete_repo.get_or_create(db_session, nom="MOREAU", prenom="Eric", club="TCN")
    db_session.flush()

    found = athlete_repo.search(db_session, name="lero")
    assert [a.nom for a in found] == ["LEROY"]
