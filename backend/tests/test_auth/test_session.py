"""Sessions applicatives — jeton opaque, empreinte en base, invariant de validité."""
from datetime import timedelta

import pytest

from app.core.time import utcnow
from app.models.user_session import UserSession
from app.repositories import session_repository, user_repository
from app.services.auth import session


def _user(db, actif=True):
    user = user_repository.create(db, email="a@exemple.fr", display_name="a")
    user.is_active = actif
    db.flush()
    return user


def test_le_jeton_rendu_est_long_et_opaque(db_session):
    """FR-011 : imprévisible, et sans aucune information sur l'utilisateur.

    L'opacité ne se prouve pas en cherchant `str(user.id)` dans le jeton — un
    « 1 » y figure par hasard une fois sur deux. Ce qui la prouve : deux jetons
    du même utilisateur n'ont rien de commun, et l'adresse n'y est pas.
    """
    user = user_repository.create(
        db_session, email="identifiable@exemple.fr", display_name="identifiable"
    )
    db_session.flush()

    premier = session.open_for(db_session, user)
    second = session.open_for(db_session, user)

    assert len(premier) >= 43
    assert premier != second
    assert user.email not in premier
    assert "identifiable" not in premier


def test_la_base_ne_contient_que_l_empreinte(db_session):
    """FR-012 : la divulgation du stockage ne permet pas d'usurper une session."""
    user = _user(db_session)

    jeton = session.open_for(db_session, user)
    db_session.commit()

    lignes = db_session.query(UserSession).all()
    assert len(lignes) == 1
    assert lignes[0].token_hash != jeton
    assert len(lignes[0].token_hash) == 64
    assert jeton not in lignes[0].token_hash


def test_un_jeton_trop_court_ne_peut_pas_ouvrir_de_session(db_session):
    """La garde de longueur est ce qui rend SHA-256 nu suffisant (`research.md` §3).

    Le jour où quelqu'un rangerait un code court dans la même colonne, elle
    deviendrait cassable hors ligne sans qu'aucun autre test n'échoue.
    """
    user = _user(db_session)

    with pytest.raises(ValueError):
        session.open_with_token(db_session, user, token="trop-court")


def test_une_session_valide_resout_son_utilisateur(db_session):
    user = _user(db_session)
    jeton = session.open_for(db_session, user)
    db_session.commit()

    assert session.resolve(db_session, jeton) is user


def test_un_jeton_inconnu_ne_resout_rien(db_session):
    assert session.resolve(db_session, "j" * 43) is None


def test_une_session_expiree_ne_resout_rien(db_session):
    user = _user(db_session)
    jeton = session.open_for(db_session, user)
    ligne = db_session.query(UserSession).one()
    ligne.expires_at = utcnow() - timedelta(seconds=1)
    db_session.commit()

    assert session.resolve(db_session, jeton) is None


def test_la_desactivation_ferme_immediatement_toutes_les_sessions(db_session):
    """FR-015 : la troisième condition est une **jointure**, jamais un cache.

    C'est elle qui rend la révocation vraie sans avoir à parcourir les sessions
    à la désactivation.
    """
    user = _user(db_session)
    premier = session.open_for(db_session, user)
    second = session.open_for(db_session, user)
    db_session.commit()

    user.is_active = False
    db_session.commit()

    assert session.resolve(db_session, premier) is None
    assert session.resolve(db_session, second) is None
    assert db_session.query(UserSession).count() == 2  # aucune ligne n'a été touchée


def test_la_deconnexion_ne_ferme_que_cette_session(db_session):
    """FR-014 : les autres appareils restent connectés."""
    user = _user(db_session)
    garde = session.open_for(db_session, user)
    ferme = session.open_for(db_session, user)
    db_session.commit()

    session.close(db_session, ferme)
    db_session.commit()

    assert session.resolve(db_session, ferme) is None
    assert session.resolve(db_session, garde) is user


def test_la_deconnexion_sans_session_est_sans_effet(db_session):
    """FR-014 : idempotente, et jamais une erreur."""
    session.close(db_session, None)
    session.close(db_session, "j" * 43)
    db_session.commit()


def test_l_ouverture_purge_les_sessions_expirees_de_l_utilisateur(db_session):
    """FR-019 : hygiène opportuniste, faute d'ordonnanceur dans le dépôt."""
    user = _user(db_session)
    session_repository.create(
        db_session,
        user_id=user.id,
        token_hash="0" * 64,
        expires_at=utcnow() - timedelta(days=1),
    )
    db_session.commit()

    session.open_for(db_session, user)
    db_session.commit()

    empreintes = {ligne.token_hash for ligne in db_session.query(UserSession).all()}
    assert "0" * 64 not in empreintes
    assert len(empreintes) == 1
