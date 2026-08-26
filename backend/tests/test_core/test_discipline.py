import pytest

from app.core.counter_scope import DEFAULT_NON_FEDERAL_DISCIPLINES as NON_FEDERAL_TYPES
from app.core.discipline import is_federal
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
    assert is_federal(event_type) is True


@pytest.mark.parametrize("event_type", HORS_FEDERATION)
def test_disciplines_hors_federation(event_type):
    assert is_federal(event_type) is False


@pytest.mark.parametrize("event_type", ["", None, "Trail L", "sport-inconnu"])
def test_un_type_non_canonique_est_federal_par_defaut(event_type):
    """Liste d'exclusion : l'inconnu reste dans les compteurs plutôt que d'en sortir en silence."""
    assert is_federal(event_type) is True


def test_les_types_hors_federation_sont_des_slugs_canoniques():
    """Une faute de frappe dans la liste la rendrait inopérante sans rien casser."""
    assert NON_FEDERAL_TYPES <= CANONICAL_TYPES


def test_la_partition_couvre_tous_les_slugs_canoniques():
    """Tout slug canonique tombe d'un côté ou de l'autre, aucun n'est orphelin."""
    federaux = {t for t in CANONICAL_TYPES if is_federal(t)}
    assert federaux | NON_FEDERAL_TYPES == CANONICAL_TYPES
    assert federaux & NON_FEDERAL_TYPES == set()


def test_la_liste_du_test_et_celle_du_module_coincident():
    """Le test doit tomber si quelqu'un élargit la liste sans y réfléchir ici."""
    assert set(HORS_FEDERATION) == NON_FEDERAL_TYPES
