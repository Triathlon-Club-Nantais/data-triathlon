"""Logique métier du formulaire public de déclaration de bénévolat (#778)."""
import pytest

from app.core.exceptions import NotFoundError
from app.repositories import athlete_repository, user_repository
from app.services import volunteer_action_service


def _auteur(db_session, email="adherent@exemple.fr"):
    user = user_repository.create(db_session, email=email)
    db_session.flush()
    return user


def _athlete(db_session, nom="DUPONT"):
    athlete = athlete_repository.get_or_create(db_session, nom=nom, prenom="Jean", club="TCN")
    db_session.flush()
    return athlete


def test_create_pending_credite_lathlete_choisi_a_la_saison_courante(db_session, monkeypatch):
    from app.core import season as season_module

    monkeypatch.setattr(season_module, "current_season", lambda: 2025)

    auteur = _auteur(db_session)
    athlete = _athlete(db_session)

    action = volunteer_action_service.create_pending(
        db_session,
        declared_by_user_id=auteur.id,
        athlete_id=athlete.id,
        title="Ravitaillement",
        description="Tenue du poste de ravitaillement km 15.",
    )

    assert action.athlete_id == athlete.id
    assert action.season == 2025
    assert action.declared_by_user_id == auteur.id
    assert action.status == "en_attente"


def test_create_pending_leve_notfounderror_si_athlete_inconnu(db_session):
    auteur = _auteur(db_session)

    with pytest.raises(NotFoundError):
        volunteer_action_service.create_pending(
            db_session,
            declared_by_user_id=auteur.id,
            athlete_id=999999,
            title="Ravitaillement",
            description="Tenue du poste de ravitaillement km 15.",
        )
