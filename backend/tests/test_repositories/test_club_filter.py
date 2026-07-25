"""Le filtre SQL et le prédicat Python doivent rendre le même verdict.

Le prédicat existe nécessairement deux fois : en Python pour le champ `is_tcn`
du DTO et pour les scrapers, en SQL pour filtrer et paginer sans charger toute
la table. Deux implémentations, un seul contrat — celui de `tests/club_corpus.py`.
Sans ce test, un badge affiché « TCN » pourrait sortir du compteur « TCN ».
"""
from datetime import date

from app.core.club import is_tcn, tcn_clause
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
    """Régression directe de #76 : 12 libellés « nantais », 9 seulement sont TCN."""
    _peupler(db_session)

    rows = participation_repository.list_participations(
        db_session, club_only=True, page_size=100
    )

    assert {r.club for r in rows} == {
        libelle for libelle, attendu in CORPUS_SQL if attendu
    }
