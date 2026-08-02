"""SC-003 — un refus d'identité ne laisse **jamais** d'utilisateur enregistré."""
import pytest

from app.core.config import get_settings
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


def test_liste_vide(db_session, doublure, monkeypatch):
    """Fail-closed **en amont** : une liste vide ferme l'entrée du parcours.

    Le refus tombe donc en `not_configured` (503 côté HTTP) et non en
    `account_not_allowed` : il n'y a plus de parcours à achever. Le refus par
    liste au **retour** — le cas d'une liste garnie qui ne contient pas cette
    adresse — reste couvert par `test_adresse_hors_liste` et par
    `test_provisioning.py`. Dans les deux cas, rien n'est enregistré.
    """
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "")
    get_settings.cache_clear()

    with pytest.raises(LoginError) as refus:
        _parcours(db_session, doublure)

    assert refus.value.code == "not_configured"
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
