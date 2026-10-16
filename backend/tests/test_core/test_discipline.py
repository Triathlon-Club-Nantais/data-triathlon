import pytest
from sqlalchemy import create_engine, literal, select

from app.core.counter_scope import DEFAULT_NON_FEDERAL_DISCIPLINES as NON_FEDERAL_TYPES
from app.core.counter_scope import non_federal_disciplines
from app.core.discipline import federal_clause
from app.scrapers.classify import CANONICAL_TYPES

FEDERALES = [
    "triathlon", "triathlon-s", "triathlon-m", "triathlon-xl",
    "duathlon", "duathlon-l", "swimrun", "swimrun-m",
    "aquathlon", "aquarun", "bike-run",
]
HORS_FEDERATION = [
    "trail", "cyclisme", "cyclisme-route", "cyclisme-clm",
    "course-a-pied", "course-a-pied-5k", "course-a-pied-10k",
    "course-a-pied-semi", "course-a-pied-marathon",
]


@pytest.mark.parametrize("event_type", FEDERALES)
def test_disciplines_federales(event_type):
    assert event_type not in non_federal_disciplines()


@pytest.mark.parametrize("event_type", HORS_FEDERATION)
def test_disciplines_hors_federation(event_type):
    assert event_type in non_federal_disciplines()


@pytest.mark.parametrize("event_type", ["", "Trail L", "sport-inconnu"])
def test_un_type_non_canonique_est_federal_par_defaut(event_type):
    """Liste d'exclusion : l'inconnu reste dans les compteurs plutôt que d'en sortir en silence."""
    with create_engine("sqlite://").connect() as conn:
        assert conn.scalar(select(federal_clause(literal(event_type)))) == 1


def test_les_types_hors_federation_sont_des_slugs_canoniques():
    """Une faute de frappe dans la liste la rendrait inopérante sans rien casser."""
    assert NON_FEDERAL_TYPES <= CANONICAL_TYPES


def test_la_liste_du_test_et_celle_du_module_coincident():
    """Le test doit tomber si quelqu'un élargit la liste sans y réfléchir ici."""
    assert set(HORS_FEDERATION) == NON_FEDERAL_TYPES
