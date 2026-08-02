"""Repositories du socle d'authentification — seule couche qui construit des requêtes."""
from datetime import timedelta

from app.core.time import utcnow
from app.models.identity import Identity
from app.models.user import User
from app.models.user_session import UserSession
from app.repositories import identity_repository, session_repository, user_repository


def test_une_identite_se_resout_par_provider_et_subject(db_session):
    user = user_repository.create(db_session, email="a@exemple.fr", display_name="a")
    identity_repository.create(
        db_session, user_id=user.id, provider="github", subject="42", email="a@exemple.fr"
    )
    db_session.commit()

    trouvee = identity_repository.get_by_subject(db_session, provider="github", subject="42")
    assert trouvee is not None
    assert trouvee.user_id == user.id


def test_un_subject_inconnu_ne_resout_rien(db_session):
    assert identity_repository.get_by_subject(db_session, provider="github", subject="42") is None


def test_le_couple_compte_pas_le_subject_seul(db_session):
    """Un même identifiant chez deux fournisseurs désigne deux personnes (FR-002)."""
    user = user_repository.create(db_session, email="a@exemple.fr", display_name="a")
    identity_repository.create(
        db_session, user_id=user.id, provider="github", subject="42", email="a@exemple.fr"
    )
    db_session.commit()

    assert identity_repository.get_by_subject(db_session, provider="ailleurs", subject="42") is None


def test_une_adresse_deja_connue_donne_un_nouvel_utilisateur(db_session):
    """FR-003 : l'adresse n'apparie **jamais**.

    C'est ce qui ferme la prise de contrôle par pré-inscription — un attaquant
    ouvrant chez un fournisseur laxiste un compte à l'adresse d'un contributeur.
    """
    premier = user_repository.create(db_session, email="partage@exemple.fr", display_name="un")
    second = user_repository.create(db_session, email="partage@exemple.fr", display_name="deux")
    db_session.commit()

    assert premier.id != second.id
    assert db_session.query(User).filter_by(email="partage@exemple.fr").count() == 2


def test_l_adresse_est_rafraichie_sans_creer_de_doublon(db_session):
    """FR-008 : les attributs mutables suivent le fournisseur."""
    user = user_repository.create(db_session, email="ancienne@exemple.fr", display_name="a")
    identity = identity_repository.create(
        db_session, user_id=user.id, provider="github", subject="42", email="ancienne@exemple.fr"
    )
    db_session.commit()

    user_repository.refresh_profile(
        db_session, user, email="nouvelle@exemple.fr", display_name="b"
    )
    identity_repository.refresh_email(db_session, identity, email="nouvelle@exemple.fr")
    db_session.commit()

    assert user.email == "nouvelle@exemple.fr"
    assert user.display_name == "b"
    assert identity.email == "nouvelle@exemple.fr"
    assert db_session.query(User).count() == 1
    assert db_session.query(Identity).count() == 1


def test_une_session_se_resout_par_son_empreinte(db_session):
    user = user_repository.create(db_session, email="a@exemple.fr", display_name="a")
    session_repository.create(
        db_session,
        user_id=user.id,
        token_hash="c" * 64,
        expires_at=utcnow() + timedelta(days=7),
    )
    db_session.commit()

    trouvee = session_repository.get_by_token_hash(db_session, "c" * 64)
    assert trouvee is not None and trouvee.user_id == user.id
    assert session_repository.get_by_token_hash(db_session, "d" * 64) is None


def test_supprimer_une_session_ne_touche_pas_les_autres(db_session):
    """FR-014 : la déconnexion ferme cet appareil seul."""
    user = user_repository.create(db_session, email="a@exemple.fr", display_name="a")
    expiration = utcnow() + timedelta(days=7)
    gardee = session_repository.create(
        db_session, user_id=user.id, token_hash="e" * 64, expires_at=expiration
    )
    fermee = session_repository.create(
        db_session, user_id=user.id, token_hash="f" * 64, expires_at=expiration
    )
    db_session.commit()

    session_repository.delete(db_session, fermee)
    db_session.commit()

    restantes = db_session.query(UserSession).all()
    assert [s.id for s in restantes] == [gardee.id]


def test_supprimer_les_sessions_expirees_d_un_utilisateur(db_session):
    """Hygiène opportuniste (FR-019) : le dépôt n'a aucun ordonnanceur."""
    user = user_repository.create(db_session, email="a@exemple.fr", display_name="a")
    autre = user_repository.create(db_session, email="b@exemple.fr", display_name="b")
    session_repository.create(
        db_session, user_id=user.id, token_hash="1" * 64, expires_at=utcnow() - timedelta(days=1)
    )
    valide = session_repository.create(
        db_session, user_id=user.id, token_hash="2" * 64, expires_at=utcnow() + timedelta(days=7)
    )
    expiree_ailleurs = session_repository.create(
        db_session, user_id=autre.id, token_hash="3" * 64, expires_at=utcnow() - timedelta(days=1)
    )
    db_session.commit()

    supprimees = session_repository.delete_expired(db_session, user_id=user.id)
    db_session.commit()

    assert supprimees == 1
    restantes = {s.id for s in db_session.query(UserSession).all()}
    assert restantes == {valide.id, expiree_ailleurs.id}
