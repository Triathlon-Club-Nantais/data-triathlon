from datetime import date

from app.repositories import course_repository


def test_get_or_create_dedups_on_identity(db_session):
    c1 = course_repository.get_or_create(
        db_session,
        name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        provider="klikego",
    )
    c2 = course_repository.get_or_create(
        db_session,
        name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        provider="klikego",
    )
    assert c1.id == c2.id


def test_different_event_type_is_distinct_course(db_session):
    c1 = course_repository.get_or_create(
        db_session, name="Tri X", event_date=date(2026, 5, 16), event_type="triathlon-s"
    )
    c2 = course_repository.get_or_create(
        db_session, name="Tri X", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    assert c1.id != c2.id


def test_is_relay_makes_distinct_course(db_session):
    solo = course_repository.get_or_create(
        db_session,
        name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        is_relay=False,
    )
    relais = course_repository.get_or_create(
        db_session,
        name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        is_relay=True,
    )
    assert solo.id != relais.id
    assert solo.is_relay is False
    assert relais.is_relay is True


def test_get_by_identity_discriminates_on_is_relay(db_session):
    course_repository.get_or_create(
        db_session,
        name="Tri Y",
        event_date=date(2026, 6, 1),
        event_type="triathlon-s",
        is_relay=True,
    )
    found_solo = course_repository.get_by_identity(
        db_session, "Tri Y", date(2026, 6, 1), "triathlon-s", is_relay=False
    )
    found_relais = course_repository.get_by_identity(
        db_session, "Tri Y", date(2026, 6, 1), "triathlon-s", is_relay=True
    )
    assert found_solo is None
    assert found_relais is not None
    assert found_relais.is_relay is True


def test_iter_all_filtre_par_provider_et_anciennete(db_session):
    from datetime import timedelta

    from app.core.time import utcnow

    # `source_url` en plus du provider, et ce n'est pas du décor depuis #279 : le
    # provider est porté par la **source**, dont l'URL est la raison d'être. Un
    # provider sans URL ne se range plus nulle part (cf.
    # `test_course_derived_source.test_a_provider_without_a_url_is_not_representable`).
    vieux = course_repository.get_or_create(
        db_session, name="Vieux", event_date=date(2025, 1, 1),
        event_type="triathlon-m", source_url="https://k/vieux", provider="klikego",
    )
    vieux.scraped_at = utcnow() - timedelta(days=40)
    frais = course_repository.get_or_create(
        db_session, name="Frais", event_date=date(2026, 1, 1),
        event_type="triathlon-m", source_url="https://t/frais", provider="timepulse",
    )
    frais.scraped_at = utcnow()
    db_session.flush()

    tous = course_repository.iter_all(db_session)
    assert {c.name for c in tous} == {"Vieux", "Frais"}

    klikego = course_repository.iter_all(db_session, provider="klikego")
    assert {c.name for c in klikego} == {"Vieux"}

    anciens = course_repository.iter_all(db_session, older_than_days=30)
    assert {c.name for c in anciens} == {"Vieux"}


def _epreuve_peuplee(db_session, nom, nb_participations):
    """Une épreuve et ses N résultats, chacun sur un athlète distinct."""
    from app.repositories import athlete_repository, participation_repository

    course = course_repository.get_or_create(
        db_session, name=nom, event_date=date(2026, 5, 17),
        event_type="triathlon-m", source_url=f"https://k/{nom}", provider="klikego",
    )
    db_session.flush()
    for indice in range(nb_participations):
        athlete = athlete_repository.get_or_create(
            db_session, nom=f"{nom}-{indice}", prenom="Coureur"
        )
        db_session.flush()
        participation_repository.create(
            db_session, athlete_id=athlete.id, course_id=course.id, bib_number=str(indice)
        )
    db_session.flush()
    return course


def test_delete_emporte_les_participations_de_l_epreuve(db_session):
    """AC1 — la cascade est portée par l'ORM (`delete-orphan`), pas par la DB."""
    from app.models.participation import Participation

    course = _epreuve_peuplee(db_session, "Supprimee", 3)
    course_id = course.id

    course_repository.delete(db_session, course)
    db_session.flush()

    assert course_repository.get(db_session, course_id) is None
    restantes = db_session.query(Participation).filter_by(course_id=course_id).count()
    assert restantes == 0


def test_delete_ne_touche_pas_les_epreuves_voisines(db_session):
    from app.models.participation import Participation

    cible = _epreuve_peuplee(db_session, "Cible", 2)
    voisine = _epreuve_peuplee(db_session, "Voisine", 2)
    voisine_id = voisine.id

    course_repository.delete(db_session, cible)
    db_session.flush()

    assert course_repository.get(db_session, voisine_id) is not None
    assert db_session.query(Participation).filter_by(course_id=voisine_id).count() == 2
