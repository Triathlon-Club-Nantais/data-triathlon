"""Mot de passe partagé fermant l'accès public au site (#509).

Ce qui est propre à cette feature : la génération du secret, celle du mot de
passe, et `replace_password`. La signature du cookie et le hachage scrypt sont
éprouvés une fois pour toutes dans `test_shared_password.py` — les tests qui les
rejouaient ici sont partis avec les délégations, en revue de #513. Le TTL du
cookie, lui, s'éprouve là où il est appliqué : `test_require_site_access.py`.
"""
from app.repositories import user_repository
from app.services import shared_password, site_access


def test_new_session_secret_rend_une_valeur_differente_a_chaque_appel():
    assert site_access.new_session_secret() != site_access.new_session_secret()


def test_generate_password_rend_une_valeur_suffisamment_longue_et_variable():
    premier = site_access.generate_password()
    second = site_access.generate_password()
    assert premier != second
    assert len(premier) >= 20


def test_replace_password_avec_saisie_stocke_le_hash_et_pas_le_mot_de_passe(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    config, mot_de_passe = site_access.replace_password(
        db_session, password="mon-nouveau-secret", admin_user_id=admin.id
    )

    assert mot_de_passe == "mon-nouveau-secret"
    assert config.password_hash != "mon-nouveau-secret"
    assert shared_password.verify_password(
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
    assert shared_password.verify_password(
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
