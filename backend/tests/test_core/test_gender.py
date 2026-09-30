"""Contrat du genre d'un athlète (#936) : `M`, `F` ou vide, et une seule règle
de « podium de genre » pour tous les compteurs."""
from datetime import date

import pytest
from sqlalchemy import select

from app.core.gender import gender_podium_clause, is_gender_podium, normalize_gender
from app.models.athlete import Athlete
from app.models.participation import Participation
from app.repositories import athlete_repository, course_repository, participation_repository


@pytest.mark.parametrize("raw", ["M", "m", "H", "h", "M ()", "Homme", "Hommes", "Masculin", "Male", "Men"])
def test_normalize_gender_reads_men(raw):
    assert normalize_gender(raw) == "M"


@pytest.mark.parametrize("raw", ["F", "f", "W", "F ()", "Femme", "Femmes", "Féminin", "Female", "Women", "Dames"])
def test_normalize_gender_reads_women(raw):
    assert normalize_gender(raw) == "F"


@pytest.mark.parametrize("raw", ["", None, "X", "A", "1", "2", "Mixte", "M+F"])
def test_normalize_gender_leaves_the_rest_empty(raw):
    assert normalize_gender(raw) == ""


@pytest.mark.parametrize(
    ("rank_gender", "gender", "expected"),
    [(1, "M", True), (3, "F", True), (4, "F", False), (None, "M", False), (2, "", False), (2, "X", False)],
)
def test_is_gender_podium(rank_gender, gender, expected):
    assert is_gender_podium(rank_gender, gender) is expected


def test_gender_podium_clause_matches_the_python_rule(db_session):
    course = course_repository.get_or_create(
        db_session, name="C", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    cas = [(1, "M"), (2, "F"), (3, ""), (1, "X"), (5, "F")]
    for index, (rang, genre) in enumerate(cas):
        athlete = athlete_repository.get_or_create(
            db_session, nom=f"N{index}", prenom="P", club="TCN", gender=genre
        )
        participation_repository.create(
            db_session, athlete_id=athlete.id, course_id=course.id, bib_number=str(index),
            club="TCN", status="finisher", rank_gender=rang,
        )
    db_session.flush()

    lignes = db_session.execute(
        select(Participation.rank_gender, Athlete.gender)
        .join(Athlete, Athlete.id == Participation.athlete_id)
        .where(gender_podium_clause(Participation.rank_gender, Athlete.gender))
    ).all()

    assert sorted(lignes) == sorted(
        (rang, genre) for rang, genre in cas if is_gender_podium(rang, genre)
    )
