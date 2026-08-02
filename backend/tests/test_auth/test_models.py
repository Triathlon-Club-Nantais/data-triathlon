"""Modèles du socle d'authentification : contraintes et invariants de schéma."""
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.time import utcnow
from app.models.identity import Identity
from app.models.user import User
from app.models.user_session import UserSession


def _user(db, email="contributeur@exemple.fr") -> User:
    user = User(email=email)
    db.add(user)
    db.flush()
    return user


def test_deux_utilisateurs_peuvent_porter_la_meme_adresse(db_session):
    """`users.email` n'est **délibérément pas** unique (FR-003).

    Poser un UNIQUE ici forcerait un appariement par adresse et rouvrirait la
    prise de contrôle par pré-inscription. Ne pas « corriger » cette absence.
    """
    _user(db_session)
    _user(db_session)
    db_session.commit()

    assert db_session.query(User).filter_by(email="contributeur@exemple.fr").count() == 2


def test_une_identite_est_unique_par_provider_et_subject(db_session):
    user = _user(db_session)
    db_session.add(
        Identity(user_id=user.id, provider="github", subject="583231", email=user.email)
    )
    db_session.commit()

    db_session.add(
        Identity(user_id=user.id, provider="github", subject="583231", email=user.email)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_un_meme_subject_chez_deux_fournisseurs_reste_recevable(db_session):
    """La clé est le **couple**, pas l'identifiant seul (FR-002)."""
    user = _user(db_session)
    db_session.add(Identity(user_id=user.id, provider="github", subject="42", email=user.email))
    db_session.add(Identity(user_id=user.id, provider="ailleurs", subject="42", email=user.email))
    db_session.commit()

    assert db_session.query(Identity).count() == 2


def test_l_empreinte_de_session_est_unique(db_session):
    user = _user(db_session)
    expiration = utcnow() + timedelta(days=7)
    db_session.add(UserSession(user_id=user.id, token_hash="a" * 64, expires_at=expiration))
    db_session.commit()

    db_session.add(UserSession(user_id=user.id, token_hash="a" * 64, expires_at=expiration))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_created_at_est_alimente_par_utcnow(db_session):
    """`utcnow` du projet, jamais `datetime.utcnow` ni `func.now()`."""
    avant = utcnow()
    user = _user(db_session)
    session = UserSession(
        user_id=user.id, token_hash="b" * 64, expires_at=utcnow() + timedelta(days=7)
    )
    identity = Identity(user_id=user.id, provider="github", subject="1", email=user.email)
    db_session.add_all([session, identity])
    db_session.commit()
    apres = utcnow()

    for horodatage in (user.created_at, session.created_at, identity.created_at):
        assert avant <= horodatage <= apres
        assert horodatage.tzinfo is None  # colonnes DateTime naïves, en UTC


def test_un_utilisateur_est_actif_par_defaut(db_session):
    user = _user(db_session)
    db_session.commit()
    assert user.is_active is True


def test_le_rattachement_a_un_athlete_est_facultatif(db_session):
    """`athlete_id` est nullable et n'est pas exploité par cette feature."""
    user = _user(db_session)
    db_session.commit()
    assert user.athlete_id is None


def test_users_ne_porte_aucun_attribut_de_role(db_session):
    """FR-041 / SC-014 : le rôle de #115 est relatif à une **organisation**.

    Il vivra dans une association `(user, organisation, role)`, jamais en colonne
    ici — un scalaire `role` serait à défaire au premier utilisateur portant deux
    rôles dans deux clubs.
    """
    colonnes = {colonne.name for colonne in User.__table__.columns}
    assert not {nom for nom in colonnes if "role" in nom}
