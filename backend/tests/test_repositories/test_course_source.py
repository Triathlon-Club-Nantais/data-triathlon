"""Contraintes de la table des sources d'une épreuve (#278).

Ce que ces tests éprouvent est tenu par la **base**, pas par une garde
applicative : l'unicité de la source active est un index partiel, et deux
exploitants simultanés franchiraient tous deux une lecture préalable là où ils
butent tous deux sur la contrainte.

Ils éprouvent aussi ce que la table **n'interdit pas** : une même URL portant N
épreuves (heats Klikego, multi-catégories Wiclax, multi-listes RaceResult,
multi-épreuves Chronoplace). Un `UNIQUE(url)` global casserait ces quatre
fournisseurs — c'est documenté sur `course_repository.list_by_source_url`.
"""
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.course_source import CourseSource
from app.repositories import course_repository, course_source_repository

URL = "https://www.klikego.com/resultats/mesquer-2026"


def _course(db_session, name: str, event_type: str = "triathlon-m"):
    return course_repository.get_or_create(
        db_session, name=name, event_date=date(2026, 5, 16), event_type=event_type
    )


def _source(db_session, course, url: str = URL, *, provider="klikego", is_active=False):
    source = CourseSource(
        course_id=course.id, url=url, provider=provider, is_active=is_active
    )
    db_session.add(source)
    db_session.flush()
    return source


def test_a_source_is_passive_unless_stated(db_session):
    """D3 — une URL soumise pour une épreuve déjà connue n'emporte pas la main."""
    source = _source(db_session, _course(db_session, "Mesquer"))

    assert source.is_active is False
    # L'import n'a pas d'utilisateur, et n'a pas encore scrapé cette source.
    assert source.created_by_user_id is None
    assert source.last_scraped_at is None


def test_the_same_url_cannot_be_registered_twice_on_one_course(db_session):
    """AC3 — `UNIQUE(course_id, url)`."""
    course = _course(db_session, "Mesquer")
    _source(db_session, course)

    with pytest.raises(IntegrityError):
        _source(db_session, course)


def test_a_course_cannot_carry_two_active_sources(db_session):
    """AC3 — l'index partiel `UNIQUE(course_id) WHERE is_active`."""
    course = _course(db_session, "Mesquer")
    _source(db_session, course, URL, is_active=True)

    with pytest.raises(IntegrityError):
        _source(
            db_session,
            course,
            "https://www.breizhchrono.com/resultats/mesquer",
            provider="breizhchrono",
            is_active=True,
        )


def test_a_course_can_carry_several_passive_sources(db_session):
    """L'index partiel ne doit pas dégénérer en unique complet sur `course_id`.

    C'est le mode de panne du `*_where` manquant sur un dialecte : le second
    chronométreur deviendrait irreprésentable.
    """
    course = _course(db_session, "Mesquer")
    _source(db_session, course, URL, is_active=True)
    _source(db_session, course, "https://www.breizhchrono.com/resultats/mesquer")
    _source(db_session, course, "https://www.chronoplace.fr/mesquer")

    assert len(course.sources) == 3
    assert [source.is_active for source in course.sources].count(True) == 1


def test_two_courses_can_share_one_url(db_session):
    """AC4 — le cas des heats : une URL publie N épreuves, chacune active dessus."""
    premier = _course(db_session, "Mesquer", "triathlon-s")
    second = _course(db_session, "Mesquer", "swimrun-m")

    _source(db_session, premier, URL, is_active=True)
    _source(db_session, second, URL, is_active=True)

    assert db_session.query(CourseSource).filter_by(url=URL).count() == 2


def test_deleting_a_course_deletes_its_sources(db_session):
    """AC5 — cascade portée par l'ORM (`delete-orphan`), comme les participations.

    `core/database.py` n'émet aucun `PRAGMA foreign_keys=ON` : un `ondelete` en
    base serait inerte en SQLite (dev et tests) et actif en PostgreSQL.
    """
    course = _course(db_session, "Supprimee")
    _source(db_session, course, URL, is_active=True)
    _source(db_session, course, "https://www.chronoplace.fr/supprimee")
    course_id = course.id

    course_repository.delete(db_session, course)
    db_session.flush()

    assert course_repository.get(db_session, course_id) is None
    assert db_session.query(CourseSource).filter_by(course_id=course_id).count() == 0


def test_remove_deletes_the_source_and_spares_its_neighbours(db_session):
    """`course_source_repository.remove` (#739) — pas la garde `is_active`,
    portée par `admin_actions.delete_course_source`."""
    course = _course(db_session, "Mesquer")
    partant = _source(db_session, course, URL, is_active=True)
    restant = _source(
        db_session, course, "https://www.chronoplace.fr/mesquer", provider="chronoplace"
    )

    course_source_repository.remove(db_session, partant)

    assert db_session.query(CourseSource).filter_by(id=partant.id).first() is None
    assert db_session.query(CourseSource).filter_by(id=restant.id).first() is restant


def test_deleting_a_course_spares_the_sources_of_its_neighbours(db_session):
    cible = _course(db_session, "Cible")
    voisine = _course(db_session, "Voisine")
    _source(db_session, cible, URL, is_active=True)
    _source(db_session, voisine, URL, is_active=True)
    voisine_id = voisine.id

    course_repository.delete(db_session, cible)
    db_session.flush()

    assert db_session.query(CourseSource).filter_by(course_id=voisine_id).count() == 1
