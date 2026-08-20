"""Socle HMAC + scrypt partagé par benevole_access (#271) et site_access (#509)."""
import time

from app.services import shared_password


def test_round_trip_avec_la_meme_cle():
    valeur = shared_password.sign_cookie("secret")
    assert shared_password.verify_cookie(valeur, "secret") is True


def test_echoue_si_la_cle_a_change():
    valeur = shared_password.sign_cookie("ancien-secret")
    assert shared_password.verify_cookie(valeur, "nouveau-secret") is False


def test_echoue_sur_une_valeur_vide_ou_mal_formee():
    assert shared_password.verify_cookie(None, "secret") is False
    assert shared_password.verify_cookie("", "secret") is False
    assert shared_password.verify_cookie("sans-point", "secret") is False


def test_echoue_si_aucune_cle_n_est_configuree():
    valeur = shared_password.sign_cookie("secret")
    assert shared_password.verify_cookie(valeur, "") is False


def test_sans_max_age_une_valeur_ancienne_reste_valide():
    horodatage = str(int(time.time()) - 999_999)
    signature = shared_password._hmac("secret", horodatage)
    valeur = f"{horodatage}.{signature}"
    assert shared_password.verify_cookie(valeur, "secret") is True


def test_avec_max_age_une_valeur_trop_ancienne_est_refusee():
    horodatage = str(int(time.time()) - 100)
    signature = shared_password._hmac("secret", horodatage)
    valeur = f"{horodatage}.{signature}"
    assert shared_password.verify_cookie(valeur, "secret", max_age_seconds=50) is False


def test_avec_max_age_une_valeur_recente_reste_valide():
    valeur = shared_password.sign_cookie("secret")
    assert shared_password.verify_cookie(valeur, "secret", max_age_seconds=3600) is True


def test_avec_max_age_un_horodatage_non_numerique_est_refuse():
    valeur = f"pas-un-nombre.{shared_password._hmac('secret', 'pas-un-nombre')}"
    assert shared_password.verify_cookie(valeur, "secret", max_age_seconds=3600) is False


def test_hash_password_accepte_le_bon_mot_de_passe():
    password_hash, password_salt = shared_password.hash_password("secret-du-club")
    assert shared_password.verify_password(
        "secret-du-club", password_hash=password_hash, password_salt=password_salt
    )


def test_hash_password_rejette_un_mauvais_mot_de_passe():
    password_hash, password_salt = shared_password.hash_password("secret-du-club")
    assert not shared_password.verify_password(
        "autre-mot-de-passe", password_hash=password_hash, password_salt=password_salt
    )


def test_hash_password_produit_un_sel_different_a_chaque_appel():
    premier_hash, premier_sel = shared_password.hash_password("secret-du-club")
    second_hash, second_sel = shared_password.hash_password("secret-du-club")
    assert premier_sel != second_sel
    assert premier_hash != second_hash
