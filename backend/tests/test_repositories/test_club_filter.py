"""Le filtre SQL et le prédicat Python doivent rendre le même verdict.

Le prédicat existe nécessairement deux fois : en Python pour le champ `is_tcn`
du DTO et pour les scrapers, en SQL pour filtrer et paginer sans charger toute
la table. Deux implémentations, un seul contrat — celui de `tests/club_corpus.py`.
Sans ce test, un badge affiché « TCN » pourrait sortir du compteur « TCN ».
"""
from datetime import date

import pytest

from app.core import counter_scope
from app.core.club import is_tcn, normalize_club, tcn_clause
from app.models.participation import Participation
from app.repositories import athlete_repository, course_repository, participation_repository
from tests.club_corpus import CORPUS_SQL


def _peupler(db_session):
    """Une participation par libellé du corpus, sur une seule épreuve."""
    course = course_repository.get_or_create(
        db_session, name="Tri des libellés", event_date=date(2026, 5, 16),
        event_type="triathlon-m",
    )
    for index, (libelle, _) in enumerate(CORPUS_SQL):
        athlete = athlete_repository.get_or_create(
            db_session, nom=f"NOM{index}", prenom="Test"
        )
        participation_repository.create(
            db_session,
            athlete_id=athlete.id,
            course_id=course.id,
            bib_number=str(index),
            club=libelle,
        )
    db_session.flush()
    return course


def test_le_filtre_sql_retient_exactement_ce_que_retient_le_predicat(db_session):
    _peupler(db_session)

    retenus = {
        p.club
        for p in db_session.query(Participation).filter(tcn_clause(Participation.club)).all()
    }
    attendus = {libelle for libelle, attendu in CORPUS_SQL if attendu}

    assert retenus == attendus


def test_le_predicat_python_est_d_accord_avec_le_corpus():
    """Garde-fou : le corpus décrit bien ce que fait `is_tcn`, pas autre chose."""
    for libelle, attendu in CORPUS_SQL:
        assert is_tcn(libelle) is attendu


def test_la_liste_filtree_par_scope_club_ne_rend_que_le_club(db_session):
    """Régression directe de #76 : des libellés « nantais » qui ne sont pas le TCN.

    Attendu recalculé depuis le corpus, jamais figé en dur : enrichir
    `club_corpus.py` resserre ce test au lieu de le périmer.
    """
    _peupler(db_session)

    rows = participation_repository.list_participations(
        db_session, club_only=True, page_size=100
    )

    assert {r.club for r in rows} == {
        libelle for libelle, attendu in CORPUS_SQL if attendu
    }


# --- Le contrat tient aussi sur une configuration modifiée (#95) -------------
#
# Depuis que les libellés vivent en base, l'accord entre les deux
# implémentations ne suffit plus à démontrer sur la seule configuration livrée :
# c'est le **registre** qui les alimente toutes les deux, et c'est cela qu'il
# faut éprouver. Un registre qui n'alimenterait que `is_tcn` laisserait un badge
# affiché « TCN » hors du compteur « TCN » — exactement le bug de #76, retourné.

#: Une configuration délibérément différente de celle livrée : « tcn » retiré,
#: « racing club nantais * » ajouté. Les deux implémentations doivent suivre
#: ensemble, dans les deux sens.
_CONFIGURATION_MODIFIEE = frozenset({
    "triathlon club nantais",   # conservé
    "tri club nantais",         # conservé
    "racing club nantais *",    # ajouté — un faux positif de #76, ici déclaré
})


@pytest.fixture
def _libelles_modifies():
    counter_scope.load(
        disciplines=counter_scope.non_federal_disciplines(),
        club_labels=_CONFIGURATION_MODIFIEE,
    )
    yield
    counter_scope.reset()


def _attendus_selon_le_registre() -> set[str]:
    """Recalculé depuis le registre, jamais figé : c'est ce que le filtre SQL
    devra retenir si — et seulement si — il lit la même source que le Python."""
    return {
        libelle
        for libelle, _ in CORPUS_SQL
        if normalize_club(libelle) in counter_scope.tcn_club_labels()
    }


def test_le_filtre_sql_suit_la_configuration_modifiee(db_session, _libelles_modifies):
    _peupler(db_session)

    retenus = {
        p.club
        for p in db_session.query(Participation).filter(tcn_clause(Participation.club)).all()
    }

    assert retenus == _attendus_selon_le_registre()


def test_le_predicat_python_suit_la_configuration_modifiee(_libelles_modifies):
    for libelle, _ in CORPUS_SQL:
        assert is_tcn(libelle) is (normalize_club(libelle) in _CONFIGURATION_MODIFIEE)


def test_le_libelle_retire_sort_des_deux_implementations(db_session, _libelles_modifies):
    """« TCN » est retiré de la configuration : ni le badge ni le compteur."""
    _peupler(db_session)

    assert is_tcn("TCN") is False
    assert "TCN" not in {
        p.club
        for p in db_session.query(Participation).filter(tcn_clause(Participation.club)).all()
    }


def test_le_libelle_ajoute_entre_dans_les_deux_implementations(db_session, _libelles_modifies):
    """Et le faux positif de #76 devient un vrai positif si on le déclare —
    la règle n'a pas changé, seule la liste a changé."""
    _peupler(db_session)

    assert is_tcn("RACING CLUB NANTAIS *") is True
    assert "RACING CLUB NANTAIS *" in {
        p.club
        for p in db_session.query(Participation).filter(tcn_clause(Participation.club)).all()
    }
