"""feedback_service.submit — honeypot, limitation de débit, association user_id (#267)."""
import pytest

from app.core.config import get_settings
from app.core.exceptions import TooManyRequestsError
from app.repositories import feedback_repository
from app.services import feedback_service


def _submit(db_session, **kwargs):
    defaults = dict(
        type="bug", title="Titre", body="Corps", page_url=None, user_agent=None,
        ip_address="203.0.113.1", user_id=None, honeypot=None,
    )
    return feedback_service.submit(db_session, **{**defaults, **kwargs})


def test_honeypot_rempli_ne_persiste_rien(db_session):
    resultat = _submit(db_session, honeypot="je-suis-un-bot")

    assert resultat is None
    assert feedback_repository.list_sorted(db_session) == []


def test_sans_honeypot_persiste(db_session):
    resultat = _submit(db_session)

    assert resultat is not None
    assert len(feedback_repository.list_sorted(db_session)) == 1


def test_debit_depasse_refuse(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "feedback_rate_limit_max_per_window", 2)

    _submit(db_session)
    _submit(db_session)

    with pytest.raises(TooManyRequestsError):
        _submit(db_session)


def test_debit_ne_compte_pas_les_autres_ip(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "feedback_rate_limit_max_per_window", 1)

    _submit(db_session, ip_address="203.0.113.1")

    # Une IP différente n'est pas concernée par le seuil de la première.
    resultat = _submit(db_session, ip_address="203.0.113.2")
    assert resultat is not None


def test_sans_adresse_ip_aucune_limitation_de_debit(db_session, monkeypatch):
    """Une IP non résolue ne doit pas être rate-limitée contre elle-même."""
    monkeypatch.setattr(get_settings(), "feedback_rate_limit_max_per_window", 1)

    _submit(db_session, ip_address=None)
    resultat = _submit(db_session, ip_address=None)

    assert resultat is not None


def test_user_id_renseigne_seulement_si_fourni(db_session):
    anonyme = _submit(db_session, user_id=None)
    connecte = _submit(db_session, user_id=42, ip_address="203.0.113.9")

    assert anonyme.user_id is None
    assert connecte.user_id == 42
