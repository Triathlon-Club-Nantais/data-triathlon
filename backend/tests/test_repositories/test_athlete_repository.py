from datetime import date

from app.repositories import athlete_repository


def test_get_or_create_creates_then_dedups(db_session):
    a1 = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    assert a1.id is not None

    # Même identité, casse différente → même athlète
    a2 = athlete_repository.get_or_create(db_session, nom="dupont", prenom="jean")
    assert a2.id == a1.id


def test_birth_date_distinguishes_homonyms(db_session):
    a1 = athlete_repository.get_or_create(
        db_session, nom="MARTIN", prenom="Paul", birth_date=date(1990, 1, 1)
    )
    a2 = athlete_repository.get_or_create(
        db_session, nom="MARTIN", prenom="Paul", birth_date=date(1985, 6, 2)
    )
    assert a1.id != a2.id


def test_get_or_create_updates_current_club(db_session):
    a1 = athlete_repository.get_or_create(db_session, nom="DURAND", prenom="Lucie", club="TCN")
    a2 = athlete_repository.get_or_create(
        db_session, nom="DURAND", prenom="Lucie", club="Triathlon Club Nantais"
    )
    assert a2.id == a1.id
    assert a2.club == "Triathlon Club Nantais"


def test_search_by_name(db_session):
    athlete_repository.get_or_create(db_session, nom="LEROY", prenom="Anne", club="TCN")
    athlete_repository.get_or_create(db_session, nom="MOREAU", prenom="Eric", club="TCN")
    db_session.flush()

    found = athlete_repository.search(db_session, name="lero")
    assert [a.nom for a in found] == ["LEROY"]


def test_get_or_create_dedup_noms_accentues(db_session):
    """`lower()` de SQLite ignore les accents majuscules ('LEMÉE' → 'lemÉe').

    Sans fonction Unicode-aware, chaque import recréait un athlète accentué.
    """
    a1 = athlete_repository.get_or_create(db_session, nom="LEMÉE", prenom="Sébastien")
    a2 = athlete_repository.get_or_create(db_session, nom="LEMÉE", prenom="Sébastien")
    assert a2.id == a1.id


def test_get_or_create_dedup_accents_casse_mixte(db_session):
    a1 = athlete_repository.get_or_create(db_session, nom="LEMÉE", prenom="Sébastien")
    a2 = athlete_repository.get_or_create(db_session, nom="lemée", prenom="sébastien")
    assert a2.id == a1.id


def test_resolve_signale_creation_puis_reutilisation(db_session):
    a1, cree1 = athlete_repository.resolve(db_session, nom="ROUX", prenom="Alexis")
    assert cree1 is True
    a2, cree2 = athlete_repository.resolve(db_session, nom="ROUX", prenom="Alexis")
    assert cree2 is False
    assert a2.id == a1.id


def _course_avec_participation(db_session, nom_athlete):
    from app.repositories import course_repository, participation_repository

    course = course_repository.get_or_create(
        db_session, name="Tri", event_date=None, event_type="triathlon-m",
        source_url="https://k/x", provider="klikego",
    )
    athlete = athlete_repository.get_or_create(db_session, nom=nom_athlete, prenom="X")
    db_session.flush()
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
    )
    db_session.flush()
    return athlete


def test_delete_orphans_supprime_les_sans_participation(db_session):
    rattache = _course_avec_participation(db_session, "RATTACHE")
    orphelin = athlete_repository.get_or_create(db_session, nom="ORPHELIN", prenom="O")
    db_session.flush()

    n = athlete_repository.delete_orphans(db_session)

    assert n == 1
    assert athlete_repository.get(db_session, orphelin.id) is None
    assert athlete_repository.get(db_session, rattache.id) is not None


def test_delete_orphans_no_op_sur_base_saine(db_session):
    """Garde de non-régression : 0 orphelin aujourd'hui → la règle n'emporte rien."""
    _course_avec_participation(db_session, "RATTACHE")

    assert athlete_repository.delete_orphans(db_session) == 0
