"""Portée des compteurs — la couche qui normalise et qui valide (#95).

Ce fichier ne couvre que ce qui ne passe pas par HTTP : la forme retenue selon
la nature, et le verdict « discipline connue ». Les refus (valeur vide, doublon,
dernier libellé) sont éprouvés de bout en bout dans
`tests/test_api/test_admin_counter_scope.py`, avec leur code de retour — les
rejouer ici ne dirait rien de plus.
"""
import pytest

from app.models.counter_scope_entry import CLUB_LABEL, NON_FEDERAL_DISCIPLINE
from app.services import counter_scope


@pytest.mark.parametrize(
    "saisie,attendu",
    [
        ("TRIATHLON  CLUB NANTAIS", "triathlon club nantais"),
        ("  Tri Club Nantais  ", "tri club nantais"),
        ("TRI\tCLUB NANTAIS", "tri club nantais"),
        # Espace insécable, écrit en échappement : le HTML français en glisse via
        # `get_text(strip=True)`, et écrit tel quel il est invisible à la relecture.
        ("TRI\xa0CLUB NANTAIS", "tri club nantais"),
        ("", ""),
    ],
)
def test_un_libelle_de_club_passe_par_la_normalisation_du_predicat(saisie, attendu):
    """La **même** fonction que `is_tcn` et son miroir SQL.

    Une normalisation propre à l'écriture laisserait enregistrer un libellé que
    le prédicat ne retrouverait jamais — déclaré, invisible, et sans erreur.
    """
    assert counter_scope.normalize_value(CLUB_LABEL, saisie) == attendu


@pytest.mark.parametrize(
    "saisie,attendu",
    [("Trail", "trail"), ("  CYCLISME-ROUTE ", "cyclisme-route"), ("", "")],
)
def test_une_discipline_se_contente_des_minuscules_et_des_bords(saisie, attendu):
    """La nomenclature ne porte ni espaces internes ni accents."""
    assert counter_scope.normalize_value(NON_FEDERAL_DISCIPLINE, saisie) == attendu


def test_une_discipline_de_la_nomenclature_est_connue():
    assert counter_scope.is_known_discipline("trail") is True


def test_une_discipline_hors_nomenclature_est_signalee_sans_etre_refusee():
    """FR-011 : exclure une discipline pas encore importée est légitime — c'est
    un avertissement, pas un refus."""
    assert counter_scope.is_known_discipline("kayak-polo") is False


def test_load_from_db_ne_lit_que_la_base(db_session):
    """Registre remplacé par ce que porte la base, y compris quand elle est vide."""
    from app.core import counter_scope as registre

    counter_scope.load_from_db(db_session)

    assert registre.tcn_club_labels() == frozenset()
    assert registre.non_federal_disciplines() == frozenset()
