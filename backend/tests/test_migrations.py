"""
Vérifie que la chaîne Alembic s'applique de bout en bout sur une base vierge.

Les fixtures de test construisent le schéma via `Base.metadata.create_all` : sans
ce test, une migration qui dépend du modèle ORM courant peut casser
`alembic upgrade head` (et donc `scripts/reset_db.py`, la CI, tout nouveau
déploiement) sans qu'aucun test ne s'en aperçoive.
"""
import logging
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.core.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sqlite_url(tmp_path, monkeypatch):
    """URL SQLite jetable, vue par `alembic/env.py` via `get_settings()`."""
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    yield url
    get_settings.cache_clear()


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


def _columns(url: str, table: str) -> set[str]:
    engine = sa.create_engine(url)
    try:
        return {c["name"] for c in sa.inspect(engine).get_columns(table)}
    finally:
        engine.dispose()


def test_upgrade_head_sur_base_vierge(sqlite_url):
    command.upgrade(_alembic_config(), "head")
    assert {"is_reliable_computed", "reliability_override", "quality_issues"} <= _columns(
        sqlite_url, "courses"
    )
    # `is_reliable` est une **propriété** de l'ORM depuis #115, jamais une
    # colonne : la voir reparaître ici signalerait un `add_column` de trop.
    assert "is_reliable" not in _columns(sqlite_url, "courses")


def test_upgrade_head_creates_the_group_tables(sqlite_url):
    """#197 — les deux tables, et surtout ce qu'elles **ne** portent pas.

    Les absences sont assertées plutôt que supposées : un `is_superuser` sur
    `groups` ferait entrer un groupe dans la décision d'accès (FR-017), et un
    `organisation_id` sur `user_groups` rendrait représentable une appartenance
    dont le club contredit celui du groupe.
    """
    command.upgrade(_alembic_config(), "head")

    assert _columns(sqlite_url, "groups") == {
        "id",
        "organisation_id",
        "slug",
        "name",
        "description",
        "created_at",
    }
    assert _columns(sqlite_url, "user_groups") == {
        "id",
        "user_id",
        "group_id",
        "joined_at",
    }


def test_upgrade_ne_desactive_pas_les_loggers_existants(sqlite_url):
    """`alembic/env.py` ne doit pas éteindre les loggers déjà enregistrés.

    `fileConfig()` désactive par défaut tout logger absent de `alembic.ini`
    (`disable_existing_loggers=True`). Sans garde-fou, exécuter une migration
    dans la même suite coupe silencieusement les loggers applicatifs (`app.*`).
    """
    logger = logging.getLogger("app.services.import_service")
    original_disabled = logger.disabled
    logger.disabled = False
    try:
        command.upgrade(_alembic_config(), "head")
        assert not logging.getLogger("app.services.import_service").disabled
    finally:
        logger.disabled = original_disabled


def _tables(url: str) -> set[str]:
    engine = sa.create_engine(url)
    try:
        return set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_les_tables_d_authentification_sont_creees(sqlite_url):
    command.upgrade(_alembic_config(), "head")
    assert {"users", "identities", "user_sessions"} <= _tables(sqlite_url)


def test_users_ne_porte_aucune_colonne_de_role(sqlite_url):
    """FR-041 / SC-014, vérifié sur le **schéma appliqué**, pas sur le modèle.

    Le rôle de #115 est relatif à une organisation et vivra dans une
    association ; un scalaire posé ici serait à défaire par une migration
    destructive.
    """
    command.upgrade(_alembic_config(), "head")
    assert not {nom for nom in _columns(sqlite_url, "users") if "role" in nom}


def test_downgrade_puis_upgrade_des_tables_d_authentification(sqlite_url):
    """Cycle complet : les contraintes nommées rendent la descente déterministe.

    La cible de descente est **nommée** et non relative (`-1`) : la prochaine
    migration ajoutée décalerait un `-1`, qui descendrait alors autre chose sans
    que l'assertion cesse pour autant de passer.
    """
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    command.downgrade(cfg, "c3d4e5f6a7b8")  # révision précédant le socle d'auth
    assert not {"users", "identities", "user_sessions"} & _tables(sqlite_url)

    command.upgrade(cfg, "head")
    assert {"users", "identities", "user_sessions"} <= _tables(sqlite_url)


def test_downgrade_puis_upgrade_de_l_indice_de_fiabilite(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    # Cible nommée : `-1` désignait l'indice de fiabilité tant qu'il était en
    # tête, mais toute migration ajoutée depuis le décale (le socle d'auth l'a
    # fait) — l'assertion se serait alors mise à éprouver autre chose.
    command.downgrade(cfg, "b2c3d4e5f6a7")
    assert not {"is_reliable", "is_reliable_computed", "quality_issues"} & _columns(
        sqlite_url, "courses"
    )

    command.upgrade(cfg, "head")
    assert {"is_reliable_computed", "reliability_override", "quality_issues"} <= _columns(
        sqlite_url, "courses"
    )


def test_les_tables_du_rbac_sont_creees(sqlite_url):
    command.upgrade(_alembic_config(), "head")
    assert {
        "organisations",
        "roles",
        "role_permissions",
        "user_roles",
    } <= _tables(sqlite_url)


def _lignes(url: str, requete: str) -> list[tuple]:
    engine = sa.create_engine(url)
    try:
        with engine.connect() as connexion:
            return [tuple(ligne) for ligne in connexion.execute(sa.text(requete))]
    finally:
        engine.dispose()


def test_la_migration_seme_exactement_trois_roles_systeme(sqlite_url):
    """FR-041 — et ce semis ne se rejoue **jamais**.

    Aucune migration ultérieure ne doit recomposer ces trois lignes : leur
    composition devient une donnée d'exploitation dès la première édition à
    chaud, et une migration qui la réécrirait effacerait une décision humaine
    sans laisser de trace. Ce test verrouille le **seul** semis autorisé.
    """
    command.upgrade(_alembic_config(), "head")

    roles = _lignes(
        sqlite_url,
        "SELECT slug, is_system, is_superuser, organisation_id FROM roles ORDER BY slug",
    )

    assert [ligne[0] for ligne in roles] == ["admin", "moderator", "validator"]
    assert all(ligne[1] for ligne in roles), "un rôle semé n'est pas is_system"
    assert all(ligne[3] is None for ligne in roles), "un rôle semé n'est pas global"


def test_admin_est_le_seul_superutilisateur_et_ne_porte_aucun_code(sqlite_url):
    """`is_superuser` franchit tout pouvoir, **y compris ceux pas encore écrits**.

    Lui coller les neuf codes du jour le figerait au jour d'aujourd'hui — c'est
    exactement ce que ce booléen évite (FR-014).
    """
    command.upgrade(_alembic_config(), "head")

    superutilisateurs = _lignes(sqlite_url, "SELECT slug FROM roles WHERE is_superuser")
    assert superutilisateurs == [("admin",)]

    codes_admin = _lignes(
        sqlite_url,
        "SELECT permission_code FROM role_permissions"
        " JOIN roles ON roles.id = role_permissions.role_id WHERE roles.slug = 'admin'",
    )
    assert codes_admin == []


def test_moderator_porte_ses_deux_codes_couples(sqlite_url):
    """Instruire un signalement sans pouvoir lire la liste n'a pas de sens.

    C'est la raison d'être du semis de ce rôle : l'oubli du pouvoir de lecture
    est le bug attendu d'une composition à la main.
    """
    command.upgrade(_alembic_config(), "head")

    codes = _lignes(
        sqlite_url,
        "SELECT permission_code FROM role_permissions"
        " JOIN roles ON roles.id = role_permissions.role_id"
        " WHERE roles.slug = 'moderator' ORDER BY permission_code",
    )

    assert codes == [("pending_providers:handle",), ("pending_providers:read",)]


def test_validator_porte_le_seul_pouvoir_de_qualite(sqlite_url):
    command.upgrade(_alembic_config(), "head")

    codes = _lignes(
        sqlite_url,
        "SELECT permission_code FROM role_permissions"
        " JOIN roles ON roles.id = role_permissions.role_id WHERE roles.slug = 'validator'",
    )

    assert codes == [("quality:override",)]


def test_l_organisation_du_club_est_semee(sqlite_url):
    """`user_roles.organisation_id` est non nul : sans elle, aucune attribution."""
    command.upgrade(_alembic_config(), "head")

    assert _lignes(sqlite_url, "SELECT slug FROM organisations") == [("tcn",)]


def test_le_renommage_de_is_reliable_conserve_les_donnees(sqlite_url):
    """`alter_column`, pas `drop`/`add` — le verdict calculé survit à la montée.

    C'est le seul point de cette révision qui porte des données en place, et
    celui qu'un `drop_column`/`add_column` aurait perdu sans bruit.
    """
    cfg = _alembic_config()
    command.upgrade(cfg, "d5e6f7a8b9c0")  # révision précédant le RBAC

    engine = sa.create_engine(sqlite_url)
    try:
        with engine.begin() as connexion:
            connexion.execute(
                sa.text(
                    "INSERT INTO courses (name, source_url, provider, event_type,"
                    " is_relay, is_reliable, scraped_at, created_at)"
                    " VALUES ('Épreuve', '', '', '', 0, 1, '2026-01-01', '2026-01-01')"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(cfg, "head")

    assert _lignes(sqlite_url, "SELECT is_reliable_computed, reliability_override FROM courses") == [
        (1, None)
    ]


def test_downgrade_puis_upgrade_du_rbac(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    command.downgrade(cfg, "d5e6f7a8b9c0")
    assert not {"organisations", "roles", "role_permissions", "user_roles"} & _tables(
        sqlite_url
    )
    assert "is_reliable" in _columns(sqlite_url, "courses")

    command.upgrade(cfg, "head")
    assert {"organisations", "roles", "role_permissions", "user_roles"} <= _tables(
        sqlite_url
    )


# --- Liste d'autorisation en base (#170) ------------------------------------


def test_la_table_des_adresses_autorisees_est_creee(sqlite_url):
    command.upgrade(_alembic_config(), "head")
    assert "allowed_emails" in _tables(sqlite_url)


def test_la_reprise_importe_les_adresses_de_l_environnement(sqlite_url, monkeypatch):
    """FR-013 : la production ne doit pas se retrouver liste vide au déploiement.

    Le `startCommand` de Render exécute `alembic upgrade head` avant `uvicorn` :
    la reprise a donc lieu **avant** la première requête, sans fenêtre pendant
    laquelle un contributeur autorisé se verrait refuser la connexion (SC-005).

    La migration lit `os.environ` et non `Settings` : le réglage a disparu de la
    configuration dans la même livraison. L'exception est bornée à ce fichier.
    """
    monkeypatch.setenv(
        "AUTH_ALLOWED_EMAILS", " A@Exemple.FR ,b@exemple.fr,a@exemple.fr "
    )

    command.upgrade(_alembic_config(), "head")

    assert _lignes(sqlite_url, "SELECT email FROM allowed_emails ORDER BY email") == [
        ("a@exemple.fr",),
        ("b@exemple.fr",),
    ]


def test_la_reprise_n_ecrit_rien_sans_variable(sqlite_url, monkeypatch):
    """Base neuve : la variable est absente, et c'est le cas nominal."""
    monkeypatch.delenv("AUTH_ALLOWED_EMAILS", raising=False)

    command.upgrade(_alembic_config(), "head")

    assert _lignes(sqlite_url, "SELECT email FROM allowed_emails") == []


def test_downgrade_puis_upgrade_des_adresses_autorisees(sqlite_url, monkeypatch):
    monkeypatch.delenv("AUTH_ALLOWED_EMAILS", raising=False)
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    # Cible **nommée**, et c'est la révision qui précède immédiatement celle des
    # adresses autorisées — `7f53922f6c73` depuis le rebasage sur #197. Un `-1`
    # se serait décalé à la première migration insérée entre-temps, et
    # descendrait alors autre chose sans que l'assertion cesse de passer.
    command.downgrade(cfg, "7f53922f6c73")
    assert "allowed_emails" not in _tables(sqlite_url)
    assert "groups" in _tables(sqlite_url), "la descente ne doit pas emporter #197"

    command.upgrade(cfg, "head")
    assert "allowed_emails" in _tables(sqlite_url)


# --- Sources d'une épreuve (#278) -------------------------------------------

#: Révision qui précède immédiatement la table des sources. **Nommée** : un `-1`
#: se décalerait à la première migration insérée entre-temps.
_BEFORE_COURSE_SOURCES = "bf114c4206a4"

_SEED_COURSES = (
    "INSERT INTO courses (name, source_url, provider, event_type, is_relay,"
    " scraped_at, created_at) VALUES"
    " ('Mesquer', 'https://klikego.test/mesquer', 'klikego', 'triathlon-s', 0,"
    "  '2026-01-01', '2026-01-01'),"
    " ('Mesquer', 'https://klikego.test/mesquer', 'klikego', 'swimrun-m', 0,"
    "  '2026-01-01', '2026-01-01'),"
    " ('Saisie manuelle', '', '', 'triathlon-m', 0, '2026-01-01', '2026-01-01')"
)


def _seed_courses(url: str) -> None:
    engine = sa.create_engine(url)
    try:
        with engine.begin() as connexion:
            connexion.execute(sa.text(_SEED_COURSES))
    finally:
        engine.dispose()


def test_upgrade_head_creates_the_course_sources_table(sqlite_url):
    command.upgrade(_alembic_config(), "head")

    assert _columns(sqlite_url, "course_sources") == {
        "id",
        "course_id",
        "url",
        "provider",
        "is_active",
        "created_at",
        "created_by_user_id",
        "last_scraped_at",
    }


def test_the_data_migration_gives_each_imported_course_one_active_source(sqlite_url):
    """AC2 — et deux épreuves partageant une URL (heats) en reçoivent chacune une.

    C'est ce qu'un `UNIQUE(url)` aurait interdit : les deux lignes ci-dessous
    sortent du même lien Klikego.
    """
    cfg = _alembic_config()
    command.upgrade(cfg, _BEFORE_COURSE_SOURCES)
    _seed_courses(sqlite_url)

    command.upgrade(cfg, "head")

    assert _lignes(
        sqlite_url,
        "SELECT courses.event_type, course_sources.url, course_sources.provider,"
        " course_sources.is_active FROM course_sources"
        " JOIN courses ON courses.id = course_sources.course_id"
        " ORDER BY courses.event_type",
    ) == [
        ("swimrun-m", "https://klikego.test/mesquer", "klikego", 1),
        ("triathlon-s", "https://klikego.test/mesquer", "klikego", 1),
    ]


def test_a_course_without_source_url_gets_no_source(sqlite_url):
    """Une saisie manuelle n'a pas de source — état légitime, pas un trou."""
    cfg = _alembic_config()
    command.upgrade(cfg, _BEFORE_COURSE_SOURCES)
    _seed_courses(sqlite_url)

    command.upgrade(cfg, "head")

    orphelines = _lignes(
        sqlite_url,
        "SELECT name FROM courses WHERE id NOT IN (SELECT course_id FROM course_sources)",
    )
    assert orphelines == [("Saisie manuelle",)]


# --- Saisie manuelle des résultats (#270) -----------------------------------

#: Révision qui précède immédiatement les colonnes de validation manuelle.
#: **Nommée** : un `-1` se décalerait à la première migration insérée entre-temps.
_BEFORE_MANUAL_VALIDATION = "9427c6c5e84a"


def test_upgrade_head_adds_manual_result_validation_columns(sqlite_url):
    command.upgrade(_alembic_config(), "head")

    assert {"is_pending_validation", "team_name", "evidence_url"} <= _columns(
        sqlite_url, "participations"
    )
    assert "format_label" in _columns(sqlite_url, "courses")


def test_les_participations_existantes_ne_deviennent_pas_pendantes(sqlite_url):
    """`server_default="false"` : aucun backfill, aucune ligne marquée à tort.

    Lu via l'ORM et non par `sa.text()` brut : `server_default='false'` produit
    en SQLite le littéral texte `'false'`, pas l'entier `0` — même artefact que
    porte déjà `is_relay` sur ce patron. C'est ce que l'application observe qui
    compte, pas la représentation du pilote.
    """
    cfg = _alembic_config()
    command.upgrade(cfg, _BEFORE_MANUAL_VALIDATION)

    engine = sa.create_engine(sqlite_url)
    try:
        with engine.begin() as connexion:
            connexion.execute(
                sa.text(
                    "INSERT INTO athletes (nom, prenom, gender, created_at)"
                    " VALUES ('DUPONT', 'Jean', '', '2026-01-01')"
                )
            )
            connexion.execute(
                sa.text(
                    "INSERT INTO courses (name, event_type, is_relay, scraped_at,"
                    " created_at) VALUES ('Tri', 'triathlon-m', 0, '2026-01-01',"
                    " '2026-01-01')"
                )
            )
            connexion.execute(
                sa.text(
                    "INSERT INTO participations (athlete_id, course_id, status,"
                    " is_relay, created_at) VALUES (1, 1, 'finisher', 0, '2026-01-01')"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(cfg, "head")

    from sqlalchemy.orm import sessionmaker

    from app.models.participation import Participation

    engine = sa.create_engine(sqlite_url)
    try:
        session = sessionmaker(bind=engine)()
        participation = session.query(Participation).one()
        assert participation.is_pending_validation is False
        session.close()
    finally:
        engine.dispose()


def test_downgrade_puis_upgrade_de_la_validation_manuelle(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    command.downgrade(cfg, _BEFORE_MANUAL_VALIDATION)
    assert not {"is_pending_validation", "team_name", "evidence_url"} & _columns(
        sqlite_url, "participations"
    )
    assert "format_label" not in _columns(sqlite_url, "courses")

    command.upgrade(cfg, "head")
    assert {"is_pending_validation", "team_name", "evidence_url"} <= _columns(
        sqlite_url, "participations"
    )
    assert "format_label" in _columns(sqlite_url, "courses")


def test_downgrade_then_upgrade_of_the_course_sources_table(sqlite_url):
    """AC1 — la descente ne perd rien : `courses.source_url` reste la source de vérité.

    C'est ce qui rend la remontée reconstituante à l'identique, et c'est pour
    cela que #278 ne supprime pas encore la colonne (#279 s'en charge).
    """
    cfg = _alembic_config()
    command.upgrade(cfg, _BEFORE_COURSE_SOURCES)
    _seed_courses(sqlite_url)
    command.upgrade(cfg, "head")

    command.downgrade(cfg, _BEFORE_COURSE_SOURCES)
    assert "course_sources" not in _tables(sqlite_url)
    assert _lignes(sqlite_url, "SELECT count(*) FROM courses") == [(3,)]

    command.upgrade(cfg, "head")
    assert _lignes(sqlite_url, "SELECT count(*) FROM course_sources WHERE is_active") == [
        (2,)
    ]
