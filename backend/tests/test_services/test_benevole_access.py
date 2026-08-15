"""Cookie de session signé par HMAC pour l'accès bénévoles (#271, research.md §D1).

Aucune table : la clé de vérification est le mot de passe courant lui-même.
"""
import pytest

from app.repositories import user_repository
from app.services import benevole_access


def test_round_trip_avec_le_meme_mot_de_passe():
    valeur = benevole_access.sign_session("secret-du-club")
    assert benevole_access.verify_session(valeur, "secret-du-club") is True


def test_echoue_si_le_mot_de_passe_a_change():
    valeur = benevole_access.sign_session("ancien-secret")
    assert benevole_access.verify_session(valeur, "nouveau-secret") is False


def test_echoue_si_l_horodatage_est_corrompu():
    valeur = benevole_access.sign_session("secret-du-club")
    horodatage, _, signature = valeur.partition(".")
    trafique = f"{horodatage}9.{signature}"
    assert benevole_access.verify_session(trafique, "secret-du-club") is False


def test_echoue_sur_une_valeur_vide_ou_mal_formee():
    assert benevole_access.verify_session(None, "secret-du-club") is False
    assert benevole_access.verify_session("", "secret-du-club") is False
    assert benevole_access.verify_session("sans-point", "secret-du-club") is False


def test_echoue_si_aucun_mot_de_passe_n_est_configure():
    valeur = benevole_access.sign_session("secret-du-club")
    assert benevole_access.verify_session(valeur, "") is False


def test_system_user_id_trouve_le_compte_seme_par_la_migration(db_session):
    compte = user_repository.create(
        db_session, email=benevole_access.SYSTEM_USER_EMAIL, display_name="Bénévoles (accès partagé)"
    )
    db_session.flush()

    assert benevole_access.system_user_id(db_session) == compte.id


def test_system_user_id_leve_si_le_compte_n_a_jamais_ete_seme(db_session):
    with pytest.raises(RuntimeError):
        benevole_access.system_user_id(db_session)
