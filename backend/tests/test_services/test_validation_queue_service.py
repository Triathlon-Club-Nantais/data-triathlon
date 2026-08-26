"""US13, #466 — arriéré de la file bénévole et délai moyen de résolution."""
from datetime import date, datetime

from app.repositories.participation_repository import ValidationQueueTimestamps
from app.services import validation_queue_service


def test_build_history_vide_sans_aucune_donnee():
    donnees = ValidationQueueTimestamps(actionable_since=[], validated=[], rejected=[])

    historique = validation_queue_service.build_history(donnees, aujourdhui=date(2026, 8, 26))

    assert historique.backlog_by_day == []
    assert historique.average_resolution_seconds is None


def test_build_history_compte_une_entree_encore_actionnable_jusqu_a_aujourd_hui():
    donnees = ValidationQueueTimestamps(
        actionable_since=[datetime(2026, 8, 24)], validated=[], rejected=[]
    )

    historique = validation_queue_service.build_history(donnees, aujourdhui=date(2026, 8, 26))

    jours = {p.date: p.pending_count for p in historique.backlog_by_day}
    assert jours == {date(2026, 8, 24): 1, date(2026, 8, 25): 1, date(2026, 8, 26): 1}


def test_build_history_une_entree_validee_ne_compte_plus_le_jour_de_sa_validation():
    donnees = ValidationQueueTimestamps(
        actionable_since=[],
        validated=[(datetime(2026, 8, 20), datetime(2026, 8, 22))],
        rejected=[],
    )

    historique = validation_queue_service.build_history(donnees, aujourdhui=date(2026, 8, 26))

    jours = {p.date: p.pending_count for p in historique.backlog_by_day}
    assert jours[date(2026, 8, 20)] == 1
    assert jours[date(2026, 8, 21)] == 1
    assert date(2026, 8, 22) not in jours or jours[date(2026, 8, 22)] == 0


def test_build_history_validee_le_jour_meme_ne_contribue_aucun_jour():
    donnees = ValidationQueueTimestamps(
        actionable_since=[],
        validated=[(datetime(2026, 8, 20), datetime(2026, 8, 20))],
        rejected=[],
    )

    historique = validation_queue_service.build_history(donnees, aujourdhui=date(2026, 8, 26))

    assert all(p.pending_count == 0 for p in historique.backlog_by_day)


def test_build_history_calcule_le_delai_moyen_sur_validees_et_rejetees():
    donnees = ValidationQueueTimestamps(
        actionable_since=[],
        validated=[(datetime(2026, 8, 20, 0, 0, 0), datetime(2026, 8, 20, 1, 0, 0))],  # 1h
        rejected=[(datetime(2026, 8, 21, 0, 0, 0), datetime(2026, 8, 21, 3, 0, 0))],  # 3h
    )

    historique = validation_queue_service.build_history(donnees, aujourdhui=date(2026, 8, 26))

    assert historique.average_resolution_seconds == 2 * 3600


def test_build_history_ignore_les_entrees_sans_timestamp_de_resolution():
    """Résolutions antérieures au déploiement de la colonne — pas d'antériorité reconstructible."""
    donnees = ValidationQueueTimestamps(actionable_since=[], validated=[], rejected=[])

    historique = validation_queue_service.build_history(donnees, aujourdhui=date(2026, 8, 26))

    assert historique.average_resolution_seconds is None
    assert historique.backlog_by_day == []
