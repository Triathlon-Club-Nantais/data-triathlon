"""Tests du re-classement de l'existant (normalisation + raffinage + km)."""
from app.models.course import Course
from app.services.reclassify import reclassify_existing


def _add(db, **kw):
    c = Course(**kw)
    db.add(c)
    db.flush()
    return c


def test_normalise_casse_et_format(db_session):
    c = _add(db_session, name="Triathlon de Test 2026", event_type="Triathlon M")
    reclassify_existing(db_session)
    db_session.refresh(c)
    assert c.event_type == "triathlon-m"


def test_raffine_nu_meme_famille_depuis_le_nom(db_session):
    # "triathlon" nu + nom révélant la distance → raffiné dans la même famille.
    c = _add(db_session, name="Triathlon Olympique de Nantes", event_type="triathlon")
    reclassify_existing(db_session)
    db_session.refresh(c)
    assert c.event_type == "triathlon-m"


def test_ne_change_pas_de_famille(db_session):
    # "triathlon" nu dont le nom parle d'un marathon → on NE bascule PAS de famille
    # (conservateur ; correction laissée au re-scrape). Reste "triathlon".
    c = _add(db_session, name="Marathon de la Ville", event_type="triathlon")
    reclassify_existing(db_session)
    db_session.refresh(c)
    assert c.event_type == "triathlon"


def test_backfill_distance_km(db_session):
    c = _add(db_session, name="Trail des Forts 23 km", event_type="trail")
    reclassify_existing(db_session)
    db_session.refresh(c)
    assert c.distance_km == 23.0


def test_idempotent(db_session):
    c = _add(db_session, name="Triathlon de Test 2026", event_type="Triathlon M")
    n1 = reclassify_existing(db_session)
    n2 = reclassify_existing(db_session)
    db_session.refresh(c)
    assert c.event_type == "triathlon-m"
    assert n1 == 1  # une course modifiée au 1er passage
    assert n2 == 0  # rien à faire au 2e passage


def test_fusionne_les_doublons_d_identite(db_session):
    # Après normalisation, "Triathlon M" et "triathlon-m" (même nom+date) entrent
    # en collision d'identité → la participation est repointée et le doublon supprimé.
    from app.models.athlete import Athlete
    from app.models.participation import Participation

    canon = _add(db_session, name="Triathlon X", event_date=None, event_type="triathlon-m")
    dup = _add(db_session, name="Triathlon X", event_date=None, event_type="Triathlon M")
    ath = Athlete(nom="Doe", prenom="Jane")
    db_session.add(ath)
    db_session.flush()
    db_session.add(Participation(athlete_id=ath.id, course_id=dup.id, bib_number="42"))
    db_session.flush()

    reclassify_existing(db_session)

    remaining = db_session.query(Course).filter(Course.name == "Triathlon X").all()
    assert len(remaining) == 1
    assert remaining[0].id == canon.id
    parts = db_session.query(Participation).filter(
        Participation.course_id == canon.id
    ).all()
    assert len(parts) == 1
    assert parts[0].bib_number == "42"
