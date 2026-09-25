"""Purges de fiches coureur face aux autres FK vers `athletes.id` (#901).

`volunteer_actions`, `season_validations` et `users.athlete_id` référencent une
fiche sans passer par `participations`. Une fiche ainsi référencée n'est pas
orpheline : la purger lèverait une `ForeignKeyViolation` en PostgreSQL. Ces
tests tournent avec `PRAGMA foreign_keys=ON` (`db_session_fk`) pour que la
violation soit visible sous SQLite.
"""
from datetime import date

import pytest

from app.repositories import (
    athlete_repository,
    course_repository,
    participation_repository,
    season_validation_repository,
    user_repository,
    volunteer_action_repository,
)
from app.services import admin_actions


@pytest.fixture
def db(db_session_fk):
    return db_session_fk


@pytest.fixture
def auteur(db):
    return user_repository.create(db, email="admin@exemple.fr")


def _epreuve(db, nom="Triathlon de Nantes"):
    course = course_repository.get_or_create(
        db,
        name=nom,
        event_date=date(2026, 5, 17),
        event_type="triathlon-m",
        source_url=f"https://k/{nom}",
        provider="klikego",
    )
    db.flush()
    return course


def _coureur(db, nom):
    athlete = athlete_repository.get_or_create(db, nom=nom, prenom="Coureur", birth_date=None, club=None)
    db.flush()
    return athlete


def _inscrit(db, athlete, course, dossard="1"):
    ligne = participation_repository.create(
        db, athlete_id=athlete.id, course_id=course.id, bib_number=dossard
    )
    db.flush()
    return ligne


def _benevolat(db, athlete, _auteur):
    volunteer_action_repository.create_pending(
        db, athlete_id=athlete.id, season=2026, declared_by_user_id=None, title="Buvette", description=""
    )


def _validation(db, athlete, auteur):
    season_validation_repository.create(
        db, athlete_id=athlete.id, season=2026, validated_by_user_id=auteur.id
    )


def _compte_lie(db, athlete, _auteur):
    user = user_repository.create(db, email=f"{athlete.nom.lower()}@exemple.fr")
    user.athlete_id = athlete.id
    db.flush()


REFERENCES = [_benevolat, _validation, _compte_lie]


@pytest.mark.parametrize("reference", REFERENCES)
def test_reassign_epargne_la_fiche_source_encore_referencee(db, auteur, reference):
    course = _epreuve(db)
    doublon = _coureur(db, "DOUBLON")
    bon = _coureur(db, "BON")
    resultat = _inscrit(db, doublon, course)
    reference(db, doublon, auteur)

    admin_actions.reassign_participation(
        db, participation_id=resultat.id, athlete_id=bon.id, user_id=auteur.id
    )
    db.flush()

    assert athlete_repository.get(db, doublon.id) is not None


@pytest.mark.parametrize("reference", REFERENCES)
def test_delete_course_epargne_une_fiche_encore_referencee(db, auteur, reference):
    course = _epreuve(db)
    referencee = _coureur(db, "REFERENCEE")
    libre = _coureur(db, "LIBRE")
    _inscrit(db, referencee, course, "1")
    _inscrit(db, libre, course, "2")
    reference(db, referencee, auteur)

    resume = admin_actions.delete_course(db, course_id=course.id, user_id=auteur.id)
    db.flush()

    assert resume["athletes_purged"] == [libre.id]
    assert athlete_repository.get(db, referencee.id) is not None


@pytest.mark.parametrize("reference", REFERENCES)
def test_l_impact_de_suppression_ne_compte_pas_une_fiche_referencee(db, auteur, reference):
    course = _epreuve(db)
    referencee = _coureur(db, "REFERENCEE")
    _inscrit(db, referencee, course, "1")
    _inscrit(db, _coureur(db, "LIBRE"), course, "2")
    reference(db, referencee, auteur)

    impact = admin_actions.course_deletion_impact(db, course_id=course.id)

    assert impact["athletes"] == 1


@pytest.mark.parametrize("reference", REFERENCES)
def test_le_balayage_complet_epargne_une_fiche_referencee(db, auteur, reference):
    referencee = _coureur(db, "REFERENCEE")
    _coureur(db, "LIBRE")
    reference(db, referencee, auteur)

    assert athlete_repository.delete_orphans(db) == 1
    db.flush()
    assert athlete_repository.get(db, referencee.id) is not None


# --- Purges totales (#994) ---------------------------------------------------


@pytest.mark.parametrize("reference", REFERENCES)
def test_wipe_all_participations_epargne_une_fiche_referencee(db, auteur, reference):
    course = _epreuve(db)
    referencee = _coureur(db, "REFERENCEE")
    _inscrit(db, referencee, course, "1")
    _inscrit(db, _coureur(db, "LIBRE"), course, "2")
    reference(db, referencee, auteur)

    assert admin_actions.wipe_impact(db)["athletes"] == 1
    resume = admin_actions.wipe_all_participations(db, user_id=auteur.id)
    db.flush()

    assert resume["athletes_purged"] == 1
    assert athlete_repository.get(db, referencee.id) is not None


@pytest.mark.parametrize("reference", REFERENCES)
def test_wipe_all_courses_epargne_une_fiche_referencee(db, auteur, reference):
    course = _epreuve(db)
    referencee = _coureur(db, "REFERENCEE")
    _inscrit(db, referencee, course, "1")
    _inscrit(db, _coureur(db, "LIBRE"), course, "2")
    reference(db, referencee, auteur)

    assert admin_actions.courses_wipe_impact(db)["athletes"] == 1
    resume = admin_actions.wipe_all_courses(db, user_id=auteur.id)
    db.flush()

    assert resume["athletes_purged"] == 1
    assert athlete_repository.get(db, referencee.id) is not None
