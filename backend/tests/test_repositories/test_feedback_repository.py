"""Accès données de UserFeedback (#267)."""
from datetime import timedelta

import pytest

from app.core.time import utcnow
from app.repositories import feedback_repository


def _create(db_session, **kwargs):
    defaults = {"type": "bug", "title": "Titre", "body": "Corps"}
    return feedback_repository.create(db_session, **{**defaults, **kwargs})


def test_create_stocke_les_champs(db_session):
    entry = _create(
        db_session,
        page_url="https://tcn.example/x",
        user_agent="Mozilla/5.0",
        ip_address="203.0.113.1",
    )

    assert entry.id is not None
    assert entry.type == "bug"
    assert entry.status == "nouveau"
    assert entry.page_url == "https://tcn.example/x"
    assert entry.ip_address == "203.0.113.1"
    assert entry.user_id is None
    assert entry.github_url is None


def test_count_recent_by_ip_fenetre_glissante(db_session):
    _create(db_session, ip_address="203.0.113.1")
    ancien = _create(db_session, ip_address="203.0.113.1")
    ancien.created_at = utcnow() - timedelta(hours=2)
    db_session.flush()

    recent = feedback_repository.count_recent_by_ip(
        db_session, ip_address="203.0.113.1", since=utcnow() - timedelta(hours=1)
    )

    assert recent == 1


def test_count_recent_by_ip_ignore_une_autre_ip(db_session):
    _create(db_session, ip_address="203.0.113.1")

    assert feedback_repository.count_recent_by_ip(
        db_session, ip_address="203.0.113.99", since=utcnow() - timedelta(hours=1)
    ) == 0


def test_list_sorted_par_date_desc_par_defaut(db_session):
    premier = _create(db_session, title="Premier")
    premier.created_at = utcnow() - timedelta(hours=1)
    _create(db_session, title="Second")
    db_session.flush()

    resultats = feedback_repository.list_sorted(db_session)

    assert [r.title for r in resultats] == ["Second", "Premier"]


def test_list_sorted_par_type_asc(db_session):
    _create(db_session, type="feedback", title="F")
    _create(db_session, type="bug", title="B")

    resultats = feedback_repository.list_sorted(db_session, sort="type", order="asc")

    assert [r.type for r in resultats] == ["bug", "feedback"]


def test_get_rend_none_si_absent(db_session):
    assert feedback_repository.get(db_session, 999) is None


def test_get_rend_lentree(db_session):
    entry = _create(db_session)

    assert feedback_repository.get(db_session, entry.id).id == entry.id


@pytest.mark.parametrize("statut", ["en_cours", "traite", "ignore", "nouveau"])
def test_update_status_toutes_les_transitions(db_session, statut):
    entry = _create(db_session)

    mis_a_jour = feedback_repository.update_status(db_session, entry.id, statut)

    assert mis_a_jour.status == statut


def test_update_status_rend_none_si_absent(db_session):
    assert feedback_repository.update_status(db_session, 999, "traite") is None


def test_set_github_url(db_session):
    entry = _create(db_session)

    mis_a_jour = feedback_repository.set_github_url(
        db_session, entry.id, "https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/1"
    )

    assert mis_a_jour.github_url == "https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/1"
