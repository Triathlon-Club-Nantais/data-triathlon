"""Mot de passe partagé fermant l'accès public au site (#509)."""
from app.repositories import user_repository
from app.services import site_access


def test_new_session_secret_rend_une_valeur_differente_a_chaque_appel():
    assert site_access.new_session_secret() != site_access.new_session_secret()


def test_generate_password_rend_une_valeur_suffisamment_longue_et_variable():
    premier = site_access.generate_password()
    second = site_access.generate_password()
    assert premier != second
    assert len(premier) >= 20


def test_verify_session_respecte_le_ttl():
    valeur = site_access.sign_session("secret-du-site")
    assert site_access.verify_session(valeur, "secret-du-site", max_age_seconds=3600) is True
    assert site_access.verify_session(valeur, "secret-du-site", max_age_seconds=0) is False


def test_verify_password_accepte_le_bon_mot_de_passe():
    password_hash, password_salt = site_access.hash_password("mot-de-passe-club")
    assert site_access.verify_password(
        "mot-de-passe-club", password_hash=password_hash, password_salt=password_salt
    )


def test_replace_password_avec_saisie_stocke_le_hash_et_pas_le_mot_de_passe(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    config, mot_de_passe = site_access.replace_password(
        db_session, password="mon-nouveau-secret", admin_user_id=admin.id
    )

    assert mot_de_passe == "mon-nouveau-secret"
    assert config.password_hash != "mon-nouveau-secret"
    assert site_access.verify_password(
        "mon-nouveau-secret",
        password_hash=config.password_hash,
        password_salt=config.password_salt,
    )


def test_replace_password_sans_saisie_genere_un_mot_de_passe(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    config, mot_de_passe = site_access.replace_password(
        db_session, password=None, admin_user_id=admin.id
    )

    assert len(mot_de_passe) >= 20
    assert site_access.verify_password(
        mot_de_passe, password_hash=config.password_hash, password_salt=config.password_salt
    )


def test_replace_password_regenere_le_secret_de_session(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    premiere_config, _ = site_access.replace_password(
        db_session, password="premier-secret", admin_user_id=admin.id
    )
    ancien_secret = premiere_config.session_secret

    seconde_config, _ = site_access.replace_password(
        db_session, password="second-secret", admin_user_id=admin.id
    )

    assert seconde_config.session_secret != ancien_secret
