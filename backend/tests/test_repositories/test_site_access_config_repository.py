"""SiteAccessConfig — une seule ligne à tout instant, distincte de
`benevole_access_config` (#271) : même contrat, deux secrets indépendants."""
from app.repositories import site_access_config_repository, user_repository


def test_get_config_rend_none_en_l_absence_de_configuration(db_session):
    assert site_access_config_repository.get_config(db_session) is None


def test_get_config_sans_updated_by_ne_le_charge_pas(db_session):
    """Fix #7, revue finale : la garde (`require_site_access`) ne lit jamais
    que `session_secret` et n'a aucune raison de payer la jointure — mesuré en
    confirmant que l'attribut n'est **pas** chargé en session (`unloaded`),
    plutôt que sur le nombre de requêtes SQL, plus fragile à l'implémentation."""
    from sqlalchemy import inspect

    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()
    site_access_config_repository.save_config(
        db_session,
        password_hash="hash",
        password_salt="salt",
        session_secret="secret",
        updated_by_user_id=admin.id,
    )
    db_session.expire_all()

    config = site_access_config_repository.get_config(db_session, with_updated_by=False)

    assert config is not None
    assert "updated_by" in inspect(config).unloaded


def test_save_config_cree_la_ligne_absente(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    config = site_access_config_repository.save_config(
        db_session,
        password_hash="hash",
        password_salt="salt",
        session_secret="secret",
        updated_by_user_id=admin.id,
    )

    assert config.id is not None
    releve = site_access_config_repository.get_config(db_session)
    assert releve.id == config.id
    assert releve.updated_by.id == admin.id


def test_save_config_met_a_jour_la_ligne_existante_sans_en_creer_une_seconde(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    premiere = site_access_config_repository.save_config(
        db_session,
        password_hash="hash-1",
        password_salt="salt-1",
        session_secret="secret-1",
        updated_by_user_id=admin.id,
    )
    seconde = site_access_config_repository.save_config(
        db_session,
        password_hash="hash-2",
        password_salt="salt-2",
        session_secret="secret-2",
        updated_by_user_id=admin.id,
    )

    assert seconde.id == premiere.id
    releve = site_access_config_repository.get_config(db_session)
    assert releve.password_hash == "hash-2"
    assert releve.session_secret == "secret-2"


def test_save_config_ne_cree_pas_une_seconde_ligne_face_a_une_ecriture_concurrente(db_session):
    from app.models.site_access_config import SiteAccessConfig

    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()
    db_session.add(
        SiteAccessConfig(
            id=site_access_config_repository.CONFIG_ROW_ID,
            password_hash="hash-concurrent",
            password_salt="salt-concurrent",
            session_secret="secret-concurrent",
            updated_by_user_id=admin.id,
        )
    )
    db_session.flush()

    config = site_access_config_repository.save_config(
        db_session,
        password_hash="hash-apres",
        password_salt="salt-apres",
        session_secret="secret-apres",
        updated_by_user_id=admin.id,
    )

    assert config.id == site_access_config_repository.CONFIG_ROW_ID
    assert db_session.query(SiteAccessConfig).count() == 1
    assert config.password_hash == "hash-apres"
