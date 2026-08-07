"""SC-003 — un refus d'identité ne laisse **jamais** d'utilisateur enregistré."""
import pytest

from app.models.identity import Identity
from app.models.user import User
from app.models.user_session import UserSession
from app.services.auth import flow, state
from app.services.auth.errors import LoginError
from app.services.auth.idp.base import ExternalIdentity


def _parcours(db, doublure):
    _, jeton_etat = flow.start_login(doublure.slug)
    charge = state.read(jeton_etat)
    return flow.complete_login(
        db,
        provider_slug=doublure.slug,
        state_token=jeton_etat,
        state_param=charge.state,
        code="code-1",
        error=None,
    )


def _base_vide(db) -> bool:
    return (
        db.query(User).count() == 0
        and db.query(Identity).count() == 0
        and db.query(UserSession).count() == 0
    )


def test_adresse_non_certifiee(db_session, doublure):
    doublure.identite = ExternalIdentity(
        provider=doublure.slug,
        subject="1",
        email="contributeur@exemple.fr",
        email_verified=False,
        display_name="x",
    )

    with pytest.raises(LoginError) as refus:
        _parcours(db_session, doublure)

    assert refus.value.code == "email_unverified"
    assert _base_vide(db_session)


def test_adresse_hors_liste(db_session, doublure):
    doublure.identite = ExternalIdentity(
        provider=doublure.slug,
        subject="1",
        email="intrus@exemple.fr",
        email_verified=True,
        display_name="x",
    )

    with pytest.raises(LoginError) as refus:
        _parcours(db_session, doublure)

    assert refus.value.code == "account_not_allowed"
    assert _base_vide(db_session)


def test_liste_vide(db_session, doublure, vider_la_liste_autorisation):
    """Fail-closed **au retour**, et non plus à l'entrée du parcours (#170).

    C'est le changement de comportement assumé par le passage de la liste en
    base : le garde de configuration ne la pèse plus, donc une liste vide
    n'interdit plus d'ouvrir le parcours — elle refuse à l'arrivée, en
    `account_not_allowed`. Le prix est un aller-retour chez le fournisseur pour
    rien ; ce qu'on gagne est de ne pas faire porter une requête base à
    `/auth/methods`, route **publique** appelée par la page de connexion.

    Ce qui n'a pas bougé, et c'est l'essentiel : rien n'est enregistré, et une
    liste vide n'a jamais valu « tout le monde ».
    """
    vider_la_liste_autorisation()

    with pytest.raises(LoginError) as refus:
        _parcours(db_session, doublure)

    assert refus.value.code == "account_not_allowed"
    assert _base_vide(db_session)


def test_le_refus_precede_la_liste_d_autorisation(db_session, doublure):
    """FR-005 : une adresse **autorisée mais non certifiée** sort en
    `email_unverified`, pas en `account_not_allowed` — l'ordre est contractuel."""
    doublure.identite = ExternalIdentity(
        provider=doublure.slug,
        subject="1",
        email="contributeur@exemple.fr",  # dans la liste
        email_verified=False,             # mais non certifiée
        display_name="x",
    )

    with pytest.raises(LoginError) as refus:
        _parcours(db_session, doublure)

    assert refus.value.code == "email_unverified"


def test_un_refus_puis_un_parcours_legitime_aboutit(db_session, doublure):
    """Scénario 5 d'US3 : rien de l'échec précédent ne subsiste."""
    doublure.identite = ExternalIdentity(
        provider=doublure.slug, subject="1", email="intrus@exemple.fr",
        email_verified=True, display_name="x",
    )
    with pytest.raises(LoginError):
        _parcours(db_session, doublure)
    db_session.rollback()

    doublure.identite = ExternalIdentity(
        provider=doublure.slug, subject="2", email="contributeur@exemple.fr",
        email_verified=True, display_name="contributeur",
    )
    jeton, user = _parcours(db_session, doublure)
    db_session.commit()

    assert jeton and user.email == "contributeur@exemple.fr"
    assert db_session.query(User).count() == 1


def test_un_compte_desactive_ne_peut_plus_ouvrir_de_session(db_session, doublure):
    """FR-015 — la désactivation ferme l'accès, y compris pour une **nouvelle** connexion.

    `session.resolve` refusait déjà un compte désactivé, mais `resolve_user` ne
    l'éprouvait pas : le parcours aboutissait, posait un cookie et redirigeait
    comme s'il avait réussi. L'utilisateur se retrouvait dans une boucle de
    connexion qui paraît toujours marcher — et chaque tentative laissait une
    session orpheline en base et réécrivait le profil du compte révoqué.
    """
    from app.models.user_session import UserSession

    _, user = _parcours(db_session, doublure)
    db_session.commit()

    user.is_active = False
    db_session.commit()
    sessions_avant = db_session.query(UserSession).count()

    with pytest.raises(LoginError) as refus:
        _parcours(db_session, doublure)
    db_session.rollback()

    assert refus.value.code == "account_not_allowed"
    assert db_session.query(UserSession).count() == sessions_avant


def test_un_compte_desactive_ne_voit_pas_son_profil_reecrit(db_session, doublure):
    """Le refus intervient **avant** `refresh_profile` : rien n'est touché."""
    _, user = _parcours(db_session, doublure)
    db_session.commit()
    user.is_active = False
    user.display_name = "nom figé"
    db_session.commit()

    doublure.identite = ExternalIdentity(
        provider=doublure.slug, subject="doublure-1", email="contributeur@exemple.fr",
        email_verified=True, display_name="nom venu du fournisseur",
    )
    with pytest.raises(LoginError):
        _parcours(db_session, doublure)
    db_session.rollback()

    db_session.refresh(user)
    assert user.display_name == "nom figé"


def test_une_identite_pendante_est_refusee_lisiblement(db_session, doublure, caplog):
    """Une ligne `identities` dont l'utilisateur a disparu ne doit pas lever nu.

    L'état est atteignable : `database.py` n'émet aucun `PRAGMA
    foreign_keys=ON`, donc la clé étrangère est **inerte** en SQLite. Sans
    garde, `refresh_profile` levait un `AttributeError` sur `None` que le
    `except Exception` du router imputait au fournisseur, sans rien nommer.

    Écrit **après** le correctif, contrairement au reste du fichier : le cas est
    adjacent au précédent et a été refermé dans le même geste.
    """
    import logging

    from sqlalchemy import text

    _, user = _parcours(db_session, doublure)
    db_session.commit()
    # En SQL brut : `db.delete(user)` passerait par la cascade ORM et emporterait
    # l'identité avec lui, ce qui est justement le cas **sain**. C'est la
    # suppression directe — celle qu'un opérateur fait en console — qui laisse
    # l'identité derrière elle, la FK étant inerte en SQLite.
    db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    db_session.commit()
    db_session.expunge_all()

    with caplog.at_level(logging.ERROR):
        with pytest.raises(LoginError) as refus:
            _parcours(db_session, doublure)
    db_session.rollback()

    assert refus.value.code == "provider_error"
    assert "Dangling identity" in caplog.text
