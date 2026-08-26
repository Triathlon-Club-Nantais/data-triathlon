"""Le registre qui porte la portée des compteurs (#95).

Deux ensembles vivent ici : les disciplines exclues des compteurs et les
libellés reconnus comme libellés du club. `core/club.py` et `core/discipline.py`
les lisent, un service les remplit depuis la base.
"""
import pytest

from app.core import counter_scope


@pytest.fixture(autouse=True)
def _registre_vierge():
    counter_scope.reset()
    yield
    counter_scope.reset()


def test_les_defauts_sont_les_neuf_disciplines_hors_federation():
    assert counter_scope.non_federal_disciplines() == frozenset({
        "trail",
        "cyclisme",
        "cyclisme-route",
        "cyclisme-clm",
        "course-a-pied",
        "course-a-pied-5k",
        "course-a-pied-10k",
        "course-a-pied-semi",
        "course-a-pied-marathon",
    })


def test_les_defauts_sont_les_trois_libelles_du_club():
    assert counter_scope.tcn_club_labels() == frozenset({
        "triathlon club nantais",
        "tri club nantais",
        "tcn",
    })


def test_load_remplace_les_deux_ensembles_dun_seul_geste():
    counter_scope.load(disciplines={"swimrun"}, club_labels={"tcn 44"})

    assert counter_scope.non_federal_disciplines() == frozenset({"swimrun"})
    assert counter_scope.tcn_club_labels() == frozenset({"tcn 44"})


def test_reset_revient_aux_defauts():
    counter_scope.load(disciplines=set(), club_labels=set())

    counter_scope.reset()

    assert counter_scope.non_federal_disciplines() == counter_scope.DEFAULT_NON_FEDERAL_DISCIPLINES
    assert counter_scope.tcn_club_labels() == counter_scope.DEFAULT_TCN_CLUB_LABELS


def test_les_accesseurs_rendent_un_ensemble_non_mutable():
    """Un appelant ne modifie pas la configuration par accident."""
    with pytest.raises(AttributeError):
        counter_scope.tcn_club_labels().add("racing club nantais")


@pytest.mark.parametrize(
    "accesseur",
    [counter_scope.non_federal_disciplines, counter_scope.tcn_club_labels],
)
def test_une_reference_prise_avant_un_load_ne_bouge_pas(accesseur):
    """La preuve du rebinding, et pas de la mutation en place.

    L'import d'épreuve tourne dans un thread d'arrière-plan (le scrape SSE de
    `import_service`) et appelle `is_tcn` ligne par ligne pendant qu'un
    administrateur peut écrire. Une réassignation de nom est atomique du point
    de vue de ce thread ; une mutation en place lui exposerait un ensemble à
    moitié écrit, et le résultat serait quelques lignes mal classées, sans
    erreur ni trace.
    """
    avant = accesseur()

    counter_scope.load(disciplines={"swimrun"}, club_labels={"tcn 44"})

    assert accesseur() is not avant
    assert avant == frozenset(
        counter_scope.DEFAULT_NON_FEDERAL_DISCIPLINES
        if accesseur is counter_scope.non_federal_disciplines
        else counter_scope.DEFAULT_TCN_CLUB_LABELS
    )


def test_load_accepte_nimporte_quel_iterable_et_rend_des_frozenset():
    counter_scope.load(disciplines=["trail", "trail"], club_labels=("tcn",))

    assert counter_scope.non_federal_disciplines() == frozenset({"trail"})
    assert isinstance(counter_scope.tcn_club_labels(), frozenset)
