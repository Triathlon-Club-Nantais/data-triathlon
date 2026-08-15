"""BenevoleAccessConfig — une seule ligne existe à tout instant (data-model.md)."""
from app.repositories import benevole_config_repository, user_repository


def test_get_config_rend_none_en_l_absence_de_configuration(db_session):
    assert benevole_config_repository.get_config(db_session) is None


def test_save_config_cree_la_ligne_absente(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    config = benevole_config_repository.save_config(
        db_session,
        password_hash="hash",
        password_salt="salt",
        session_secret="secret",
        updated_by_user_id=admin.id,
    )

    assert config.id is not None
    releve = benevole_config_repository.get_config(db_session)
    assert releve.id == config.id
    assert releve.updated_by.id == admin.id


def test_save_config_met_a_jour_la_ligne_existante_sans_en_creer_une_seconde(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    premiere = benevole_config_repository.save_config(
        db_session,
        password_hash="hash-1",
        password_salt="salt-1",
        session_secret="secret-1",
        updated_by_user_id=admin.id,
    )
    seconde = benevole_config_repository.save_config(
        db_session,
        password_hash="hash-2",
        password_salt="salt-2",
        session_secret="secret-2",
        updated_by_user_id=admin.id,
    )

    assert seconde.id == premiere.id
    releve = benevole_config_repository.get_config(db_session)
    assert releve.password_hash == "hash-2"
    assert releve.session_secret == "secret-2"
