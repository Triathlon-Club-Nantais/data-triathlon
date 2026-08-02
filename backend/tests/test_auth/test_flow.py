"""Orchestration du parcours — `start_login` et `complete_login`.

Le flux ne construit aucune requête : il enchaîne registre, état, provisionnement
et session. Ce fichier l'éprouve sur la doublure, donc sans réseau ni GitHub.
"""
from datetime import timedelta

import pytest

from app.core.time import utcnow
from app.models.user_session import UserSession
from app.repositories import session_repository
from app.services.auth import flow, session, state
from app.services.auth.errors import LoginError


def _parcours(db, doublure, **surcharges):
    _, jeton_etat = flow.start_login(doublure.slug)
    charge = state.read(jeton_etat)
    arguments = {
        "provider_slug": doublure.slug,
        "state_token": jeton_etat,
        "state_param": charge.state,
        "code": "code-de-retour",
        "error": None,
    }
    arguments.update(surcharges)
    return flow.complete_login(db, **arguments)


def test_start_login_rend_l_url_et_l_etat_signe(doublure):
    url, jeton_etat = flow.start_login(doublure.slug)

    charge = state.read(jeton_etat)
    assert charge.provider == doublure.slug
    assert charge.state in url


def test_start_login_refuse_un_fournisseur_inconnu():
    with pytest.raises(LoginError) as refus:
        flow.start_login("inexistant")
    assert refus.value.code == "unknown_provider"


def test_le_parcours_nominal_ouvre_une_session(db_session, doublure):
    jeton, user = _parcours(db_session, doublure)
    db_session.commit()

    assert session.resolve(db_session, jeton) is user
    assert user.email == "contributeur@exemple.fr"


def test_le_code_de_retour_est_transmis_au_fournisseur(db_session, doublure):
    _parcours(db_session, doublure)

    assert doublure.appels == [
        {"code": "code-de-retour", "round_trip": {"cle-inventee": "valeur"}}
    ]


def test_un_etat_ne_correspondant_pas_est_refuse(db_session, doublure):
    with pytest.raises(LoginError) as refus:
        _parcours(db_session, doublure, state_param="autre-chose")

    assert refus.value.code == "state_mismatch"
    assert doublure.appels == []  # aucun échange n'a eu lieu


def test_un_etat_emis_pour_un_autre_fournisseur_est_refuse(db_session, doublure):
    """FR-022 : la preuve désigne explicitement le moyen de connexion."""
    _, jeton_etat = flow.start_login("github")
    charge = state.read(jeton_etat)

    with pytest.raises(LoginError) as refus:
        flow.complete_login(
            db_session,
            provider_slug=doublure.slug,
            state_token=jeton_etat,
            state_param=charge.state,
            code="code",
            error=None,
        )

    assert refus.value.code == "state_mismatch"
    assert doublure.appels == []


def test_un_refus_du_fournisseur_est_transmis_tel_quel_en_code_ferme(db_session, doublure):
    with pytest.raises(LoginError) as refus:
        _parcours(db_session, doublure, error="access_denied", code=None)

    assert refus.value.code == "provider_error"
    assert doublure.appels == []


def test_un_retour_sans_code_est_refuse(db_session, doublure):
    with pytest.raises(LoginError) as refus:
        _parcours(db_session, doublure, code=None)

    assert refus.value.code == "provider_error"
    assert doublure.appels == []


def test_l_ouverture_purge_les_sessions_expirees_de_l_utilisateur(db_session, doublure):
    """FR-019, vérifié au niveau du flux — c'est là que l'hygiène se déclenche."""
    premier, user = _parcours(db_session, doublure)
    db_session.commit()

    perimee = session_repository.get_by_token_hash(db_session, session.hash_token(premier))
    perimee.expires_at = utcnow() - timedelta(seconds=1)
    db_session.commit()

    second, _ = _parcours(db_session, doublure)
    db_session.commit()

    empreintes = {ligne.token_hash for ligne in db_session.query(UserSession).all()}
    assert empreintes == {session.hash_token(second)}


def test_une_reconnexion_ne_cree_pas_de_second_utilisateur(db_session, doublure):
    _, premier = _parcours(db_session, doublure)
    db_session.commit()
    _, second = _parcours(db_session, doublure)
    db_session.commit()

    assert second.id == premier.id


def test_un_refus_de_provisionnement_ne_laisse_aucune_session(db_session, doublure, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "quelquun-dautre@exemple.fr")
    get_settings.cache_clear()

    with pytest.raises(LoginError) as refus:
        _parcours(db_session, doublure)

    assert refus.value.code == "account_not_allowed"
    assert db_session.query(UserSession).count() == 0
