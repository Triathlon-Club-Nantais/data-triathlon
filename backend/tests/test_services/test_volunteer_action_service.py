"""Logique métier du formulaire public de déclaration de bénévolat (#778) et
de son workflow de validation admin (#779)."""
import pytest

from app.core.exceptions import NotFoundError
from app.repositories import athlete_repository, user_repository, volunteer_action_repository
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


def _declaration(db_session, *, status="en_attente"):
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)
    action = volunteer_action_repository.create_pending(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur.id,
        title="Ravitaillement", description="Poste eau.",
    )
    db_session.flush()
    if status != "en_attente":
        volunteer_action_repository.set_status(db_session, action.id, status)
    return auteur, action


def test_list_pending_ne_rend_que_les_declarations_en_attente(db_session):
    _, en_attente = _declaration(db_session)
    _declaration(db_session, status="validee")

    resultat = volunteer_action_service.list_pending(db_session)

    assert [a.id for a in resultat] == [en_attente.id]


def test_accept_fait_passer_en_attente_a_validee(db_session):
    admin, action = _declaration(db_session)

    mise_a_jour = volunteer_action_service.accept(db_session, admin_user_id=admin.id, action_id=action.id)

    assert mise_a_jour.status == "validee"


def test_accept_est_idempotent_si_deja_validee(db_session):
    admin, action = _declaration(db_session, status="validee")

    mise_a_jour = volunteer_action_service.accept(db_session, admin_user_id=admin.id, action_id=action.id)

    assert mise_a_jour.status == "validee"


def test_accept_est_un_noop_si_refusee(db_session):
    """#779, research.md D6 / `/speckit-analyze` finding U1 — pas de retour
    vers « validée » depuis « refusée »."""
    admin, action = _declaration(db_session, status="refusee")

    mise_a_jour = volunteer_action_service.accept(db_session, admin_user_id=admin.id, action_id=action.id)

    assert mise_a_jour.status == "refusee"


def test_accept_leve_notfounderror_si_id_inconnu(db_session):
    admin = _auteur(db_session)

    with pytest.raises(NotFoundError):
        volunteer_action_service.accept(db_session, admin_user_id=admin.id, action_id=999999)


def test_reject_fait_passer_en_attente_a_refusee(db_session):
    admin, action = _declaration(db_session)

    mise_a_jour = volunteer_action_service.reject(db_session, admin_user_id=admin.id, action_id=action.id)

    assert mise_a_jour.status == "refusee"


def test_reject_fait_passer_validee_a_refusee(db_session):
    admin, action = _declaration(db_session, status="validee")

    mise_a_jour = volunteer_action_service.reject(db_session, admin_user_id=admin.id, action_id=action.id)

    assert mise_a_jour.status == "refusee"


def test_reject_est_idempotent_si_deja_refusee(db_session):
    admin, action = _declaration(db_session, status="refusee")

    mise_a_jour = volunteer_action_service.reject(db_session, admin_user_id=admin.id, action_id=action.id)

    assert mise_a_jour.status == "refusee"
