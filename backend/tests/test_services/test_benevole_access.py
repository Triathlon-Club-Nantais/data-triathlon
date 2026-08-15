"""Cookie de session signé par HMAC pour l'accès bénévoles (#271, research.md §D1).

Depuis `specs/20260815-173645-admin-mdp-benevoles/` : la clé de vérification
n'est plus le mot de passe lui-même mais `session_secret`, stocké aux côtés
du mot de passe **haché et salé** — jamais en clair (FR-004).
"""
import pytest

from app.repositories import benevole_config_repository, user_repository
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


# --- Hachage du mot de passe (research.md §D1) -------------------------------


def test_hash_password_accepte_le_bon_mot_de_passe():
    password_hash, password_salt = benevole_access.hash_password("secret-du-club")

    assert benevole_access.verify_password(
        "secret-du-club", password_hash=password_hash, password_salt=password_salt
    )


def test_hash_password_rejette_un_mauvais_mot_de_passe():
    password_hash, password_salt = benevole_access.hash_password("secret-du-club")

    assert not benevole_access.verify_password(
        "un-autre-mot-de-passe", password_hash=password_hash, password_salt=password_salt
    )


def test_hash_password_produit_un_sel_different_a_chaque_appel():
    """Le même mot de passe hache différemment à chaque appel (FR-004) — sans
    quoi deux administrateurs choisissant le même mot de passe le sauraient
    en comparant les lignes en base."""
    premier_hash, premier_sel = benevole_access.hash_password("secret-du-club")
    second_hash, second_sel = benevole_access.hash_password("secret-du-club")

    assert premier_sel != second_sel
    assert premier_hash != second_hash


# --- Secret de session (research.md §D2) -------------------------------------


def test_new_session_secret_rend_une_valeur_differente_a_chaque_appel():
    assert benevole_access.new_session_secret() != benevole_access.new_session_secret()


# --- Génération sécurisée (research.md §D5) ----------------------------------


def test_generate_password_rend_une_valeur_suffisamment_longue_et_variable():
    premier = benevole_access.generate_password()
    second = benevole_access.generate_password()

    assert premier != second
    assert len(premier) >= 20


# --- Remplacement, orchestration de service (data-model.md, invariant d'atomicité) --


def test_replace_password_avec_saisie_stocke_le_hash_et_pas_le_mot_de_passe(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    config, mot_de_passe = benevole_access.replace_password(
        db_session, password="mon-nouveau-secret", admin_user_id=admin.id
    )

    assert mot_de_passe == "mon-nouveau-secret"
    assert config.password_hash != "mon-nouveau-secret"
    assert benevole_access.verify_password(
        "mon-nouveau-secret",
        password_hash=config.password_hash,
        password_salt=config.password_salt,
    )


def test_replace_password_sans_saisie_genere_un_mot_de_passe(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    config, mot_de_passe = benevole_access.replace_password(
        db_session, password=None, admin_user_id=admin.id
    )

    assert len(mot_de_passe) >= 20
    assert benevole_access.verify_password(
        mot_de_passe, password_hash=config.password_hash, password_salt=config.password_salt
    )


def test_replace_password_rotationne_le_secret_de_session(db_session):
    """FR-006 : chaque remplacement régénère `session_secret`, ce qui invalide
    les sessions signées avec l'ancien — les trois champs sont réécrits
    ensemble, jamais l'un sans les autres."""
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    premiere_config, _ = benevole_access.replace_password(
        db_session, password="premier-secret", admin_user_id=admin.id
    )
    ancien_secret = premiere_config.session_secret

    seconde_config, _ = benevole_access.replace_password(
        db_session, password="second-secret", admin_user_id=admin.id
    )

    assert seconde_config.session_secret != ancien_secret


def test_replace_password_n_ecrit_qu_une_seule_ligne(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    benevole_access.replace_password(db_session, password="premier", admin_user_id=admin.id)
    benevole_access.replace_password(db_session, password="second", admin_user_id=admin.id)
    db_session.commit()

    config = benevole_config_repository.get_config(db_session)
    assert config is not None
    assert benevole_access.verify_password(
        "second", password_hash=config.password_hash, password_salt=config.password_salt
    )
