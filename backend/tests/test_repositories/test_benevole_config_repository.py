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


def test_save_config_ne_cree_pas_une_seconde_ligne_face_a_une_ecriture_concurrente(
    db_session,
):
    """Revue de code (#271 → cette feature) : deux administrateurs — ou un
    double-clic — remplaçant le mot de passe au tout premier réglage ne
    doivent jamais laisser deux lignes coexister (spec.md, edge case
    « deux administrateurs modifient le mot de passe presque
    simultanément… sans état incohérent »).

    Le harnais de test (une session, une connexion SQLite en mémoire) ne
    peut pas reproduire deux transactions réellement concurrentes ; ce test
    vérifie donc l'invariant observable — au plus une ligne, toujours la
    dernière écriture — face à une ligne posée juste avant l'appel, plutôt
    que la branche exacte de `save_config` qui l'atteint. La garantie sous
    charge réelle tient à la contrainte de clé primaire (id fixe), pas à une
    lecture préalable que deux exploitants simultanés franchiraient
    pareillement — patron `allowed_email_repository.add`."""
    from app.models.benevole_access_config import BenevoleAccessConfig

    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()
    db_session.add(
        BenevoleAccessConfig(
            id=benevole_config_repository.CONFIG_ROW_ID,
            password_hash="hash-concurrent",
            password_salt="salt-concurrent",
            session_secret="secret-concurrent",
            updated_by_user_id=admin.id,
        )
    )
    db_session.flush()

    config = benevole_config_repository.save_config(
        db_session,
        password_hash="hash-apres",
        password_salt="salt-apres",
        session_secret="secret-apres",
        updated_by_user_id=admin.id,
    )

    assert config.id == benevole_config_repository.CONFIG_ROW_ID
    assert db_session.query(BenevoleAccessConfig).count() == 1
    assert config.password_hash == "hash-apres"
