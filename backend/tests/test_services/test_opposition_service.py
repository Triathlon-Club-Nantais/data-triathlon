"""Appliquer une opposition (#334) : anonymiser, retirer la fiche, journaliser, sans décaler personne."""
from datetime import date

import pytest

from app.core.exceptions import DomainError
from app.core.identity import identity_hash
from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.season_validation import SeasonValidation
from app.models.volunteer_action import VolunteerAction
from app.repositories import (
    athlete_repository,
    course_repository,
    opposition_repository,
    participation_repository,
    season_validation_repository,
    user_repository,
    volunteer_action_repository,
)
from app.services import opposition_service

TODAY = date(2026, 10, 1)


@pytest.fixture
def db(db_session_fk):
    return db_session_fk


@pytest.fixture
def admin(db):
    return user_repository.create(db, email="admin@exemple.fr", display_name="Admin")


@pytest.fixture
def course(db):
    return course_repository.get_or_create(
        db, name="Triathlon de Nantes", event_date=date(2026, 6, 7), event_type="triathlon-m",
        source_url="https://www.klikego.com/resultats/x/1", provider="klikego",
    )


def _classer(db, course, athlete, rang, dossard, club="BLAIN TRI"):
    return participation_repository.create(
        db, course_id=course.id, athlete_id=athlete.id, bib_number=dossard, rank_overall=rang,
        total_time="2:10:00", status="finisher", club=club, category="SEM", raw_data={"nom": athlete.nom},
    )


def _athlete(db, nom, prenom):
    return athlete_repository.get_or_create(db, nom=nom, prenom=prenom)


def test_preview_counts_results_homonyms_included(db, course):
    jean = _athlete(db, "DUPONT", "Jean")
    homonyme = athlete_repository.get_or_create(db, nom="Dupont", prenom="Jean", birth_date=date(1990, 1, 1))
    autre = _athlete(db, "MARTIN", "Alix")
    _classer(db, course, jean, 12, "120")
    _classer(db, course, homonyme, 40, "400")
    _classer(db, course, autre, 13, "130")

    apercu = opposition_service.preview(db, athlete_id=jean.id)

    assert (apercu.athletes, apercu.results, apercu.already_opposed) == (2, 2, False)


def test_apply_anonymises_the_rows_and_keeps_everyone_elses_rank(db, course, admin):
    jean = _athlete(db, "DUPONT", "Jean")
    autre = _athlete(db, "MARTIN", "Alix")
    sienne = _classer(db, course, jean, 12, "120")
    voisine = _classer(db, course, autre, 13, "130")

    opposition, creee = opposition_service.apply(
        db, admin, athlete_id=jean.id, requested_on=date(2026, 9, 20), today=TODAY
    )

    assert creee and opposition.anonymised_count == 1
    db.refresh(sienne)
    assert sienne.athlete.nom == f"Anonyme {course.id}-120"
    assert sienne.athlete.prenom == ""
    assert (sienne.club, sienne.category, sienne.raw_data) == ("", "", {})
    assert (sienne.bib_number, sienne.rank_overall, sienne.total_time, sienne.status) == (
        "120", 12, "2:10:00", "finisher",
    )
    db.refresh(voisine)
    assert voisine.rank_overall == 13 and voisine.athlete_id == autre.id
    assert db.get(Athlete, jean.id) is None
    assert athlete_repository.search(db, name="Dupont") == []


def test_apply_lowers_the_club_counter_of_a_club_member(db, course, admin):
    jean = _athlete(db, "DUPONT", "Jean")
    _classer(db, course, jean, 12, "120", club="TRIATHLON CLUB NANTAIS")
    course.tcn_count = 1
    db.flush()

    opposition_service.apply(db, admin, athlete_id=jean.id, requested_on=TODAY, today=TODAY)

    db.refresh(course)
    assert course.tcn_count == 0


def test_apply_replaces_the_person_by_an_anonymous_teammate(db, course, admin):
    # Une équipe compte 2 à 8 équipiers : retirer la personne casserait l'équipe de deux.
    porteur = _athlete(db, "MARTIN", "Alix")
    jean = _athlete(db, "DUPONT", "Jean")
    relais = _classer(db, course, porteur, 5, "50")
    participation_repository.replace_teammates(db, relais, [porteur.id, jean.id])

    opposition, _ = opposition_service.apply(db, admin, athlete_id=jean.id, requested_on=TODAY, today=TODAY)

    equipe = [db.get(Athlete, i) for i in participation_repository.teammate_athlete_ids(db, relais.id)]
    assert [(a.nom, a.prenom) for a in equipe] == [("MARTIN", "Alix"), (f"Anonyme {course.id}-50-1", "")]
    assert opposition.anonymised_count == 1


def test_apply_cuts_every_other_link_to_the_record(db, course, admin):
    jean = _athlete(db, "DUPONT", "Jean")
    _classer(db, course, jean, 12, "120")
    compte = user_repository.create(db, email="jean@exemple.fr", display_name="Jean")
    compte.athlete_id = jean.id
    volunteer_action_repository.create_pending(
        db, athlete_id=jean.id, season=2025, declared_by_user_id=None, title="Ravitaillement", description="",
    )
    season_validation_repository.create(db, athlete_id=jean.id, season=2025, validated_by_user_id=admin.id)
    db.flush()

    opposition_service.apply(db, admin, athlete_id=jean.id, requested_on=TODAY, today=TODAY)

    db.refresh(compte)
    assert compte.athlete_id is None
    assert db.query(VolunteerAction).count() == 0
    assert db.query(SeasonValidation).count() == 0


def test_apply_is_logged_with_both_dates_and_without_the_name(db, course, admin):
    jean = _athlete(db, "DUPONT", "Jean")
    _classer(db, course, jean, 12, "120")

    opposition, _ = opposition_service.apply(
        db, admin, athlete_id=jean.id, requested_on=date(2026, 9, 20), today=TODAY
    )

    entree = db.query(AdminActionLog).filter_by(action="opposition_applied").one()
    assert (entree.user_id, entree.entity_type, entree.entity_id) == (admin.id, "opposition", opposition.id)
    assert entree.payload == {"requested_on": "2026-09-20", "anonymised_count": 1}
    assert "dupont" not in str(entree.payload).lower()


def test_an_opposition_by_name_without_any_record_is_stored(db, admin):
    opposition, creee = opposition_service.apply(
        db, admin, nom="Dupont", prenom="Jean", requested_on=TODAY, today=TODAY
    )

    assert creee and opposition.anonymised_count == 0
    assert opposition_repository.get_by_hash(db, identity_hash("Dupont", "Jean")) is not None


def test_applying_twice_reuses_the_opposition(db, course, admin):
    premiere, _ = opposition_service.apply(db, admin, nom="Dupont", prenom="Jean", requested_on=TODAY, today=TODAY)
    jean = _athlete(db, "DUPONT", "Jean")
    _classer(db, course, jean, 12, "120")

    seconde, creee = opposition_service.apply(db, admin, athlete_id=jean.id, requested_on=TODAY, today=TODAY)

    assert not creee and seconde.id == premiere.id
    assert seconde.anonymised_count == 1


def test_a_future_request_date_is_refused(db, admin):
    with pytest.raises(DomainError):
        opposition_service.apply(db, admin, nom="Dupont", prenom="Jean", requested_on=date(2026, 10, 2), today=TODAY)


def test_an_identity_is_required(db, admin):
    with pytest.raises(DomainError):
        opposition_service.apply(db, admin, nom=" ", prenom="", requested_on=TODAY, today=TODAY)
