"""
Vérifie que la chaîne Alembic s'applique de bout en bout sur une base vierge.

Les fixtures de test construisent le schéma via `Base.metadata.create_all` : sans
ce test, une migration qui dépend du modèle ORM courant peut casser
`alembic upgrade head` (et donc `scripts/reset_db.py`, la CI, tout nouveau
déploiement) sans qu'aucun test ne s'en aperçoive.
"""
import json
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


@pytest.fixture(scope="module")
def base_migree(tmp_path_factory):
    """Base SQLite montée à `head` **une fois par worker** pour tout le module.

    « Une fois » et non « une seule fois » : le `--dist load` par défaut de xdist
    éparpille les tests d'un module sur plusieurs workers, et chacun monte donc sa
    propre base — mesuré, deux montées à `-n 4`, deux à `-n 8`. C'est aussi ce qui
    rend toute collision de chemin impossible, chaque worker ayant son `basetemp`.

    Les 13 tests qui la prennent ne font qu'**inspecter le schéma** : aucun
    n'écrit. Répéter `upgrade head` pour chacun coûtait ~0,6 s par test sans rien
    vérifier de plus, la montée étant identique à chaque fois (#508).

    Celui qui aurait besoin d'écrire, de semer à une révision intermédiaire ou de
    descendre reprend `sqlite_url`, qui rend une base neuve par test.

    `DATABASE_URL` n'est posée que le temps de la montée : `alembic/env.py` la lit
    via `get_settings()`, mais les inspections passent ensuite par l'URL explicite.
    La laisser en place à portée module la ferait fuir vers les autres tests
    exécutés par le même worker xdist.
    """
    url = f"sqlite:///{tmp_path_factory.mktemp('migrations') / 'migration.db'}"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATABASE_URL", url)
        get_settings.cache_clear()
        command.upgrade(_alembic_config(), "head")
    get_settings.cache_clear()
    return url


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


def test_upgrade_head_creates_the_group_tables(base_migree):
    """#197 — les deux tables, et surtout ce qu'elles **ne** portent pas.

    Les absences sont assertées plutôt que supposées : un `is_superuser` sur
    `groups` ferait entrer un groupe dans la décision d'accès (FR-017), et un
    `organisation_id` sur `user_groups` rendrait représentable une appartenance
    dont le club contredit celui du groupe.
    """
    assert _columns(base_migree, "groups") == {
        "id",
        "organisation_id",
        "slug",
        "name",
        "description",
        "created_at",
    }
    assert _columns(base_migree, "user_groups") == {
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


def test_les_tables_d_authentification_sont_creees(base_migree):
    assert {"users", "identities", "user_sessions"} <= _tables(base_migree)


def test_users_ne_porte_aucune_colonne_de_role(base_migree):
    """FR-041 / SC-014, vérifié sur le **schéma appliqué**, pas sur le modèle.

    Le rôle de #115 est relatif à une organisation et vivra dans une
    association ; un scalaire posé ici serait à défaire par une migration
    destructive.
    """
    assert not {nom for nom in _columns(base_migree, "users") if "role" in nom}


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


def test_downgrade_puis_upgrade_de_club_locked(sqlite_url):
    """#439 — sans ce test, le `downgrade` de la révision ne serait jamais exécuté.

    Ce fichier ne couvre l'aller-retour que **révision par révision** : seul
    `test_upgrade_head_sur_base_vierge` est générique, aucun `downgrade` ne l'est.
    """
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    # Cible nommée, comme pour l'indice de fiabilité : `-1` désignerait autre
    # chose dès qu'une migration s'ajoute au-dessus.
    command.downgrade(cfg, "d25f17b925d4")
    assert "club_locked" not in _columns(sqlite_url, "athletes")

    command.upgrade(cfg, "head")
    assert "club_locked" in _columns(sqlite_url, "athletes")

    # C'est la **base** qui remplit la colonne, pas Python : une fiche insérée en
    # SQL brut — ce que sont les lignes déjà en production au moment de la
    # migration — doit en ressortir non verrouillée.
    engine = sa.create_engine(sqlite_url)
    try:
        with engine.begin() as connexion:
            connexion.execute(
                sa.text(
                    "INSERT INTO athletes (nom, prenom, gender, created_at) "
                    "VALUES ('MIGRE', 'Mia', 'F', '2026-08-20 00:00:00')"
                )
            )
            verrou = connexion.execute(sa.text("SELECT club_locked FROM athletes")).scalar()
    finally:
        engine.dispose()
    assert verrou in (0, False)


def test_les_tables_du_rbac_sont_creees(base_migree):
    assert {
        "organisations",
        "roles",
        "role_permissions",
        "user_roles",
    } <= _tables(base_migree)


def _lignes(url: str, requete: str) -> list[tuple]:
    engine = sa.create_engine(url)
    try:
        with engine.connect() as connexion:
            return [tuple(ligne) for ligne in connexion.execute(sa.text(requete))]
    finally:
        engine.dispose()


def test_la_migration_seme_exactement_trois_roles_systeme(base_migree):
    """FR-041 — et ce semis ne se rejoue **jamais**.

    Aucune migration ultérieure ne doit recomposer ces trois lignes : leur
    composition devient une donnée d'exploitation dès la première édition à
    chaud, et une migration qui la réécrirait effacerait une décision humaine
    sans laisser de trace. Ce test verrouille le **seul** semis autorisé.
    """
    roles = _lignes(
        base_migree,
        "SELECT slug, is_system, is_superuser, organisation_id FROM roles ORDER BY slug",
    )

    assert [ligne[0] for ligne in roles] == ["admin", "moderator", "validator"]
    assert all(ligne[1] for ligne in roles), "un rôle semé n'est pas is_system"
    assert all(ligne[3] is None for ligne in roles), "un rôle semé n'est pas global"


def test_admin_est_le_seul_superutilisateur_et_ne_porte_aucun_code(base_migree):
    """`is_superuser` franchit tout pouvoir, **y compris ceux pas encore écrits**.

    Lui coller les neuf codes du jour le figerait au jour d'aujourd'hui — c'est
    exactement ce que ce booléen évite (FR-014).
    """
    superutilisateurs = _lignes(base_migree, "SELECT slug FROM roles WHERE is_superuser")
    assert superutilisateurs == [("admin",)]

    codes_admin = _lignes(
        base_migree,
        "SELECT permission_code FROM role_permissions"
        " JOIN roles ON roles.id = role_permissions.role_id WHERE roles.slug = 'admin'",
    )
    assert codes_admin == []


def test_moderator_porte_ses_deux_codes_couples(base_migree):
    """Instruire un signalement sans pouvoir lire la liste n'a pas de sens.

    C'est la raison d'être du semis de ce rôle : l'oubli du pouvoir de lecture
    est le bug attendu d'une composition à la main.
    """
    codes = _lignes(
        base_migree,
        "SELECT permission_code FROM role_permissions"
        " JOIN roles ON roles.id = role_permissions.role_id"
        " WHERE roles.slug = 'moderator' ORDER BY permission_code",
    )

    assert codes == [("pending_providers:handle",), ("pending_providers:read",)]


def test_validator_porte_le_seul_pouvoir_de_qualite(base_migree):
    codes = _lignes(
        base_migree,
        "SELECT permission_code FROM role_permissions"
        " JOIN roles ON roles.id = role_permissions.role_id WHERE roles.slug = 'validator'",
    )

    assert codes == [("quality:override",)]


def test_l_organisation_du_club_est_semee(base_migree):
    """`user_roles.organisation_id` est non nul : sans elle, aucune attribution."""
    assert _lignes(base_migree, "SELECT slug FROM organisations") == [("tcn",)]


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


def test_la_table_des_adresses_autorisees_est_creee(base_migree):
    assert "allowed_emails" in _tables(base_migree)


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


def test_upgrade_head_creates_the_course_sources_table(base_migree):
    assert _columns(base_migree, "course_sources") == {
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


def test_upgrade_head_adds_manual_result_validation_columns(base_migree):
    assert {"is_pending_validation", "team_name", "evidence_url"} <= _columns(
        base_migree, "participations"
    )
    assert "format_label" in _columns(base_migree, "courses")


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


_BEFORE_BENEVOLE_SEED = "05094fea3bc2"


def _user_emails(url: str) -> set[str]:
    engine = sa.create_engine(url)
    try:
        with engine.connect() as connexion:
            return {row[0] for row in connexion.execute(sa.text("SELECT email FROM users"))}
    finally:
        engine.dispose()


def test_downgrade_puis_upgrade_du_semis_benevoles(sqlite_url):
    """Le compte système « Bénévoles (accès partagé) » (#271) : une ligne, pas un schéma."""
    from app.models.user import SYSTEM_USER_EMAIL

    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    assert SYSTEM_USER_EMAIL in _user_emails(sqlite_url)

    command.downgrade(cfg, _BEFORE_BENEVOLE_SEED)
    assert SYSTEM_USER_EMAIL not in _user_emails(sqlite_url)

    command.upgrade(cfg, "head")
    assert SYSTEM_USER_EMAIL in _user_emails(sqlite_url)


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


# --- Purge totale des résultats (#384) ------------------------------------

#: Révision qui précède immédiatement la nullabilité de `scraped_at`. **Nommée** :
#: un `-1` se décalerait à la première migration insérée entre-temps.
_BEFORE_SCRAPED_AT_NULLABLE = "05094fea3bc2"


def _nullable(url: str, table: str, column: str) -> bool:
    engine = sa.create_engine(url)
    try:
        colonnes = {c["name"]: c for c in sa.inspect(engine).get_columns(table)}
        return bool(colonnes[column]["nullable"])
    finally:
        engine.dispose()


def test_scraped_at_devient_nullable(base_migree):
    assert _nullable(base_migree, "courses", "scraped_at") is True


def test_downgrade_puis_upgrade_de_la_nullabilite_de_scraped_at(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    command.downgrade(cfg, _BEFORE_SCRAPED_AT_NULLABLE)
    assert _nullable(sqlite_url, "courses", "scraped_at") is False

    command.upgrade(cfg, "head")
    assert _nullable(sqlite_url, "courses", "scraped_at") is True


# --- Géocodage persisté des épreuves (#579) ---------------------------------


def test_upgrade_head_adds_course_geocoding_columns(base_migree):
    assert {"latitude", "longitude", "geocoded_at"} <= _columns(base_migree, "courses")


def test_downgrade_puis_upgrade_du_geocodage(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    # Cible nommée : `-1` se décalerait à la première migration insérée
    # entre-temps — même précaution que les autres tests de ce fichier.
    command.downgrade(cfg, "50b1c877b851")
    assert not {"latitude", "longitude", "geocoded_at"} & _columns(sqlite_url, "courses")

    command.upgrade(cfg, "head")
    assert {"latitude", "longitude", "geocoded_at"} <= _columns(sqlite_url, "courses")


def test_la_migration_ne_remplit_rien(sqlite_url):
    """Colonnes vides sur l'existant : le remplissage est le rôle de `geocode-courses`.

    Une épreuve insérée en SQL brut avant la migration — ce que sont les
    lignes déjà en production au moment de la montée — doit en ressortir
    sans coordonnées.
    """
    cfg = _alembic_config()
    command.upgrade(cfg, "50b1c877b851")

    engine = sa.create_engine(sqlite_url)
    try:
        with engine.begin() as connexion:
            connexion.execute(
                sa.text(
                    "INSERT INTO courses (name, event_type, is_relay, scraped_at,"
                    " created_at) VALUES ('Épreuve', 'triathlon-m', 0, '2026-01-01',"
                    " '2026-01-01')"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(cfg, "head")

    assert _lignes(
        sqlite_url, "SELECT latitude, longitude, geocoded_at FROM courses"
    ) == [(None, None, None)]


# --- Portée des compteurs en base (#95) --------------------------------------

_BEFORE_COUNTER_SCOPE = "1df0635fc2fd"


def test_la_table_de_portee_des_compteurs_est_creee(base_migree):
    assert "counter_scope_entries" in _tables(base_migree)


def test_l_amorcage_vaut_exactement_les_defauts_du_registre(base_migree):
    """Le garde-fou contre la divergence entre migration et code.

    Les douze valeurs sont écrites **en littéral** dans la migration — une
    migration doit rester lisible telle quelle des années après, indépendamment
    de ce que le code est devenu. Le prix de ce choix est deux sources pour la
    même valeur ; ce test est ce qui les empêche de diverger.
    """
    from app.core import counter_scope
    from app.models.counter_scope_entry import CLUB_LABEL, NON_FEDERAL_DISCIPLINE

    semees = _lignes(
        base_migree, "SELECT kind, value, created_by_user_id FROM counter_scope_entries"
    )

    par_nature = {CLUB_LABEL: set(), NON_FEDERAL_DISCIPLINE: set()}
    for kind, value, _ in semees:
        par_nature[kind].add(value)

    assert par_nature[NON_FEDERAL_DISCIPLINE] == set(
        counter_scope.DEFAULT_NON_FEDERAL_DISCIPLINES
    )
    assert par_nature[CLUB_LABEL] == set(counter_scope.DEFAULT_TCN_CLUB_LABELS)
    assert all(auteur is None for _, _, auteur in semees), (
        "une ligne d'amorçage porte un auteur"
    )


def test_downgrade_puis_upgrade_de_la_portee_des_compteurs(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    # La révision **nommée**, comme les sept autres descentes de ce fichier :
    # un `-1` se décalerait à la première migration insérée entre-temps, et
    # rougirait sans que le coupable soit lisible.
    command.downgrade(cfg, _BEFORE_COUNTER_SCOPE)
    assert "counter_scope_entries" not in _tables(sqlite_url)

    command.upgrade(cfg, "head")
    assert _lignes(sqlite_url, "SELECT COUNT(*) FROM counter_scope_entries") == [(12,)]


def test_upgrade_head_adds_participation_validation_timestamp_columns(base_migree):
    assert {"validated_at", "rejected_at"} <= _columns(base_migree, "participations")


def test_downgrade_puis_upgrade_des_timestamps_de_validation(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    # Cible nommée : `-1` se décalerait à la première migration insérée
    # entre-temps — même précaution que les autres tests de ce fichier.
    command.downgrade(cfg, "05de2237111f")
    assert not {"validated_at", "rejected_at"} & _columns(sqlite_url, "participations")

    command.upgrade(cfg, "head")
    assert {"validated_at", "rejected_at"} <= _columns(sqlite_url, "participations")


def _index_names(url: str, table: str) -> set[str]:
    engine = sa.create_engine(url)
    try:
        return {i["name"] for i in sa.inspect(engine).get_indexes(table)}
    finally:
        engine.dispose()


def test_course_names_are_cleaned_unless_the_clean_name_collides(sqlite_url):
    """Scrapers and manual entry now clean names: stale rows would duplicate (#1088)."""
    cfg = _alembic_config()
    command.upgrade(cfg, "9f2e3d4c5b6a")
    noms = [
        ("Embrunman - {EN:Quarter|FR:Quart}", "2026-08-15"),
        ("TRIATHLON DES SABLES D'OLONNE  - SPRINT", "2026-06-01"),
        ("Swimrun Dinard ", "2026-05-01"),
        ("Déjà propre ", "2026-04-01"),
        ("Déjà propre", "2026-04-01"),
        # Même règle que `qualify_event_name` : un qualifiant déjà dans le nom
        # n'est pas ré-ajouté, sans quoi le prochain rescrape recréerait l'épreuve.
        ("Embrunman Quart - {EN:Quarter|FR:Quart}", "2026-08-16"),
        ("Tri - {fr:Sprint}", "2026-07-01"),
        ("Tri Vide - {FR:|EN:}", "2026-07-02"),
    ]
    engine = sa.create_engine(sqlite_url)
    try:
        with engine.begin() as connexion:
            for nom, jour in noms:
                connexion.execute(
                    sa.text(
                        "INSERT INTO courses (name, event_date, event_type, is_relay, scraped_at,"
                        " created_at) VALUES (:nom, :jour, 'triathlon-m', 0, '2026-01-01',"
                        " '2026-01-01')"
                    ),
                    {"nom": nom, "jour": jour},
                )
    finally:
        engine.dispose()

    command.upgrade(cfg, "head")

    assert sorted(n for (n,) in _lignes(sqlite_url, "SELECT name FROM courses")) == sorted([
        "Embrunman - Quart",
        "TRIATHLON DES SABLES D'OLONNE - SPRINT",
        "Swimrun Dinard",
        "Déjà propre ",  # le nom propre existe déjà : on ne crée pas de collision
        "Déjà propre",
        "Embrunman Quart",
        "Tri - Sprint",
        "Tri Vide - {FR:|EN:}",  # variantes vides : gardé intact, comme au runtime
    ])


def test_user_sessions_token_hash_keeps_only_its_unique_index(sqlite_url):
    """The unique constraint already indexes the column (#1061)."""
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    assert "ix_user_sessions_token_hash" not in _index_names(sqlite_url, "user_sessions")

    command.downgrade(cfg, "8e1d2c3b4a5f")
    assert "ix_user_sessions_token_hash" in _index_names(sqlite_url, "user_sessions")

    command.upgrade(cfg, "head")
    assert "ix_user_sessions_token_hash" not in _index_names(sqlite_url, "user_sessions")


def test_downgrade_then_upgrade_of_the_course_source_url_index(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    assert "ix_course_sources_url_active" in _index_names(sqlite_url, "course_sources")

    command.downgrade(cfg, "c10f3d7ae85e")
    assert "ix_course_sources_url_active" not in _index_names(sqlite_url, "course_sources")

    command.upgrade(cfg, "head")
    assert "ix_course_sources_url_active" in _index_names(sqlite_url, "course_sources")


def test_volunteer_declarations_downgrade_renders_valid_postgresql_types(monkeypatch):
    """#1060 : le downgrade autogénéré contre SQLite émettait `DATETIME`, inconnu de PostgreSQL."""
    import io

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pwd@localhost/offline")
    get_settings.cache_clear()
    buffer = io.StringIO()
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"), output_buffer=buffer)
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    try:
        command.downgrade(cfg, "5b766a96b2a4:b8a572868051", sql=True)
    finally:
        get_settings.cache_clear()

    sql = buffer.getvalue()
    assert "CREATE TABLE volunteer_declarations" in sql
    assert "DATETIME" not in sql
    assert "created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL" in sql


def test_course_model_declares_the_postgresql_trigram_index():
    """#1023 : sans déclaration au modèle, `alembic check` sous PostgreSQL proposait de le supprimer."""
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateIndex

    from app.models.course import Course

    index = next(i for i in Course.__table__.indexes if i.name == "ix_courses_name_trgm")
    ddl = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
    assert "USING gin (name gin_trgm_ops)" in ddl

    engine = sa.create_engine("sqlite://")
    try:
        Course.__table__.create(engine)
        assert "ix_courses_name_trgm" not in {i["name"] for i in sa.inspect(engine).get_indexes("courses")}
    finally:
        engine.dispose()


def test_alembic_check_finds_no_drift_on_sqlite(sqlite_url):
    """#1023 : l'index trigram, propre à PostgreSQL, ne doit pas apparaître comme à créer."""
    command.upgrade(_alembic_config(), "head")
    command.check(_alembic_config())


_BEFORE_IDENTITY_KEY = "d49e03833de6"
_IDENTITY_KEY_MIGRATION = BACKEND_ROOT / "alembic" / "versions" / "b7e41c9d2a58_athlete_identity_key.py"


def _insert_athletes(url: str, identities: list[tuple[str, str]]) -> None:
    engine = sa.create_engine(url)
    with engine.begin() as connexion:
        for nom, prenom in identities:
            connexion.execute(
                sa.text(
                    "INSERT INTO athletes (nom, prenom, gender, club_locked, created_at)"
                    " VALUES (:nom, :prenom, '', 0, '2026-01-01')"
                ),
                {"nom": nom, "prenom": prenom},
            )
    engine.dispose()


def test_the_identity_key_migration_backfills_keys_and_ranks_duplicates(sqlite_url):
    """#907 : les doublons existants reçoivent un rang au lieu de faire échouer
    la contrainte, sinon le déploiement Render (migrations au démarrage) casserait."""
    cfg = _alembic_config()
    command.upgrade(cfg, _BEFORE_IDENTITY_KEY)
    _insert_athletes(sqlite_url, [
        ("LETORT", "Leo"), ("LETORT", "Léo"), ("?", ""), ("DUPONT JEAN", ""), ("CIC 7", ""), ("", "Jean Dupont")
    ])

    command.upgrade(cfg, "head")

    assert _lignes(
        sqlite_url,
        "SELECT last_name_key, first_name_key, homonym_rank FROM athletes ORDER BY id",
    ) == [
        ("letort", "leo", 0), ("letort", "leo", 1), (None, None, 0), ("dupontjean", "", 0), ("cic7", "", 0),
        ("jeandupont", "", 0),
    ]


def test_the_identity_constraint_rejects_a_second_principal_record(sqlite_url):
    command.upgrade(_alembic_config(), "head")
    _insert_athletes(sqlite_url, [("LETORT", "Leo")])
    engine = sa.create_engine(sqlite_url)
    try:
        with engine.begin() as connexion:
            connexion.execute(sa.text("UPDATE athletes SET last_name_key = 'letort', first_name_key = 'leo'"))
        with pytest.raises(sa.exc.IntegrityError), engine.begin() as connexion:
            connexion.execute(
                sa.text(
                    "INSERT INTO athletes (nom, prenom, gender, club_locked, created_at,"
                    " last_name_key, first_name_key, homonym_rank)"
                    " VALUES ('LETORT', 'Léo', '', 0, '2026-01-01', 'letort', 'leo', 0)"
                )
            )
    finally:
        engine.dispose()


def test_the_identity_key_migration_drops_the_old_identity(base_migree):
    engine = sa.create_engine(base_migree)
    try:
        inspector = sa.inspect(engine)
        uniques = {u["name"]: u["column_names"] for u in inspector.get_unique_constraints("athletes")}
        with engine.connect() as connection:
            old_index = connection.execute(
                sa.text("SELECT sql FROM sqlite_master WHERE name = 'ix_athletes_identity'")
            ).scalar()
    finally:
        engine.dispose()
    assert uniques["uq_athlete_identity"] == ["last_name_key", "first_name_key", "homonym_rank"]
    assert old_index is None


def test_the_frozen_migration_rule_matches_the_application_key():
    """La règle est recopiée dans la migration pour qu'un rejeu futur donne le même
    résultat : ce test empêche les deux copies de diverger aujourd'hui."""
    import importlib.util

    from app.core.athlete_identity import identity_key

    spec = importlib.util.spec_from_file_location("identity_key_migration", _IDENTITY_KEY_MIGRATION)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    for raw in ["Léo", "L'APPARTIEN", "LE GLOANIC", "Œuvray", "Lætitia", "Strauß", "Søren", "Łukasz", "Đorđe",
                "CIC 7", "Иванов", "?", "", None]:
        assert migration._identity_key(raw) == identity_key(raw)


def test_downgrade_of_the_identity_key_names_the_duplicates(sqlite_url):
    """L'ancienne contrainte `(nom, prenom, birth_date)` ne heurte que deux fiches
    datées identiques : des NULL ne se comparent pas."""
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    _insert_athletes_after_keys(sqlite_url, [
        ("LETORT", "Léo", "letort", "leo", 0), ("LETORT", "Léo", "letort", "leo", 1)
    ])

    with pytest.raises(RuntimeError, match="LETORT"):
        command.downgrade(cfg, _BEFORE_IDENTITY_KEY)


_BEFORE_SOURCE_IDENTITY = "b7e41c9d2a58"


def test_the_source_identity_migration_backfills_each_participation(sqlite_url):
    """#896 : chaque résultat retient l'identité de la ligne source, ici celle de sa fiche."""
    cfg = _alembic_config()
    command.upgrade(cfg, _BEFORE_SOURCE_IDENTITY)
    _insert_athletes(sqlite_url, [("LE GLOANIC", "Léo"), ("?", "")])
    engine = sa.create_engine(sqlite_url)
    with engine.begin() as connexion:
        connexion.execute(sa.text(
            "UPDATE athletes SET last_name_key = 'legloanic', first_name_key = 'leo' WHERE nom = 'LE GLOANIC'"
        ))
        connexion.execute(sa.text(
            "INSERT INTO courses (name, event_date, event_type, is_relay, created_at)"
            " VALUES ('Tri', '2026-05-16', 'triathlon-m', 0, '2026-01-01')"
        ))
        for athlete_id, bib in [(1, "1"), (2, "2")]:
            connexion.execute(
                sa.text(
                    "INSERT INTO participations (athlete_id, course_id, bib_number, status, created_at)"
                    " VALUES (:athlete_id, 1, :bib, 'finisher', '2026-01-01')"
                ),
                {"athlete_id": athlete_id, "bib": bib},
            )
    engine.dispose()

    command.upgrade(cfg, "head")

    assert _lignes(
        sqlite_url, "SELECT source_identity_key, athlete_locked FROM participations ORDER BY id"
    ) == [("legloanic|leo", 0), (None, 0)]


_BEFORE_ALIASES = "c3a9d1e7f520"


def test_the_alias_table_keeps_one_owner_per_spelling(sqlite_url):
    """#908 : une variante n'appartient qu'à une fiche."""
    command.upgrade(_alembic_config(), "head")
    _insert_athletes(sqlite_url, [("DUPONT", "Jean"), ("MARTIN", "Paul")])
    engine = sa.create_engine(sqlite_url)
    try:
        insert = sa.text(
            "INSERT INTO athlete_aliases (last_name_key, first_name_key, athlete_id, created_at)"
            " VALUES ('dupomt', 'jean', :athlete_id, '2026-10-02')"
        )
        with engine.begin() as connexion:
            connexion.execute(insert, {"athlete_id": 1})
        with pytest.raises(sa.exc.IntegrityError), engine.begin() as connexion:
            connexion.execute(insert, {"athlete_id": 2})
    finally:
        engine.dispose()


_BEFORE_IGNORED_PAIRS = "d8b2f4a6c1e3"


def test_downgrade_then_upgrade_of_the_ignored_athlete_pairs(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    engine = sa.create_engine(sqlite_url)
    try:
        uniques = {u["name"]: u["column_names"] for u in sa.inspect(engine).get_unique_constraints("ignored_athlete_pairs")}
    finally:
        engine.dispose()
    assert uniques["uq_ignored_athlete_pair"] == ["athlete_id_low", "athlete_id_high"]
    command.downgrade(cfg, _BEFORE_IGNORED_PAIRS)
    command.upgrade(cfg, "head")


def test_downgrade_then_upgrade_of_the_alias_table(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, _BEFORE_ALIASES)
    engine = sa.create_engine(sqlite_url)
    try:
        assert "athlete_aliases" not in sa.inspect(engine).get_table_names()
    finally:
        engine.dispose()
    command.upgrade(cfg, "head")


def test_downgrade_then_upgrade_of_the_source_identity(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, _BEFORE_SOURCE_IDENTITY)
    assert "source_identity_key" not in _columns(sqlite_url, "participations")
    command.upgrade(cfg, "head")
    assert {"source_identity_key", "athlete_locked"} <= _columns(sqlite_url, "participations")


def test_downgrade_then_upgrade_of_the_identity_key(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, _BEFORE_IDENTITY_KEY)
    assert "last_name_key" not in _columns(sqlite_url, "athletes")
    command.upgrade(cfg, "head")
    assert {"last_name_key", "first_name_key", "homonym_rank"} <= _columns(sqlite_url, "athletes")


def _insert_athletes_after_keys(url: str, rows: list[tuple[str, str, str, str, int]]) -> None:
    engine = sa.create_engine(url)
    with engine.begin() as connexion:
        for nom, prenom, last_key, first_key, rank in rows:
            connexion.execute(
                sa.text(
                    "INSERT INTO athletes (nom, prenom, gender, club_locked, created_at, birth_date,"
                    " last_name_key, first_name_key, homonym_rank)"
                    " VALUES (:nom, :prenom, '', 0, '2026-01-01', '1990-01-01', :last_key, :first_key, :rank)"
                ),
                {"nom": nom, "prenom": prenom, "last_key": last_key, "first_key": first_key, "rank": rank},
            )
    engine.dispose()


_BEFORE_GENDER_NORMALIZATION = "7dfd2effc405"


def test_the_data_migration_normalizes_athlete_gender(sqlite_url):
    """#936 : `H`, `Homme`, `F ()`, `W` deviennent `M`/`F`, le reste devient vide."""
    cfg = _alembic_config()
    command.upgrade(cfg, _BEFORE_GENDER_NORMALIZATION)
    engine = sa.create_engine(sqlite_url)
    with engine.begin() as connexion:
        for index, genre in enumerate(["M", "H", "Homme", "F", "F ()", "W", "X", "", "1"]):
            connexion.execute(
                sa.text(
                    "INSERT INTO athletes (nom, prenom, gender, club_locked, created_at)"
                    " VALUES (:nom, 'P', :genre, 0, '2026-01-01')"
                ),
                {"nom": f"N{index}", "genre": genre},
            )
    engine.dispose()

    command.upgrade(cfg, "head")

    assert _lignes(sqlite_url, "SELECT gender FROM athletes ORDER BY id") == [
        ("M",), ("M",), ("M",), ("F",), ("F",), ("F",), ("",), ("",), ("",),
    ]


# --- Rattrapage du club actuel (#965) ----------------------------------------

_BEFORE_CURRENT_CLUB_BACKFILL = "d49e03833de6"


def _seed_club_history(url: str) -> None:
    """Sept fiches, chacune un cas de la règle de #965.

    `club` porte la valeur qu'a laissée l'ancien import, qui suivait l'ordre de
    traitement et non la date d'épreuve.
    """
    athletes = [
        # (nom, club actuel en base, verrouillé)
        ("ORDRE", "CAROTTES", False),     # l'épreuve la plus récente annonce TCN
        ("VERROU", "MANUEL", True),      # corrigé par un humain : intouchable
        ("ATTENTE", "Y", False),          # la plus récente est une déclaration en attente
        ("SANSDATE", "W", False),         # aucune épreuve datée : rien ne prouve un club
        ("VIDE", "B", False),             # la plus récente ne publie aucun club
        ("EGALITE", "P1", False),         # deux épreuves le même jour : la dernière importée
        ("EQUIPIER", "PERSO", False),     # la plus récente est un relais composé (#895)
    ]
    courses = [
        # (id, date)
        (1, "2025-02-01"),
        (2, "2026-05-01"),
        (3, None),
    ]
    participations = [
        # (athlète, course, club, en attente)
        ("ORDRE", 2, "TCN", False),
        ("ORDRE", 1, "CAROTTES", False),
        ("VERROU", 2, "TCN", False),
        ("ATTENTE", 1, "Y", False),
        ("ATTENTE", 2, "X", True),
        ("SANSDATE", 3, "Z", False),
        ("VIDE", 1, "A", False),
        ("VIDE", 2, "", False),
        ("EGALITE", 2, "P1", False),
        ("EGALITE", 2, "P2", False),
        ("EQUIPIER", 1, "PERSO", False),
        ("EQUIPIER", 2, "EQUIPE", False),
    ]
    engine = sa.create_engine(url)
    try:
        with engine.begin() as connexion:
            for nom, club, verrou in athletes:
                connexion.execute(
                    sa.text(
                        "INSERT INTO athletes (nom, prenom, gender, club, club_locked, created_at)"
                        " VALUES (:nom, 'P', '', :club, :verrou, '2026-01-01')"
                    ),
                    {"nom": nom, "club": club, "verrou": verrou},
                )
            for course_id, event_date in courses:
                connexion.execute(
                    sa.text(
                        "INSERT INTO courses (id, name, event_type, event_date, is_relay,"
                        " scraped_at, created_at) VALUES (:id, :nom, 'triathlon-m', :date, :relais,"
                        " '2026-01-01', '2026-01-01')"
                    ),
                    {"id": course_id, "nom": f"Tri {course_id}", "date": event_date, "relais": False},
                )
            for nom, course_id, club, attente in participations:
                connexion.execute(
                    sa.text(
                        "INSERT INTO participations (course_id, athlete_id, club,"
                        " is_pending_validation, status, created_at)"
                        " SELECT :course, id, :club, :attente, 'finisher', '2026-01-01'"
                        " FROM athletes WHERE nom = :nom"
                    ),
                    {"course": course_id, "club": club, "attente": attente, "nom": nom},
                )
            # Une ligne de relais composée porte le club de l'équipe, rattachée à
            # son premier équipier : ce n'est pas le club de l'équipier.
            connexion.execute(
                sa.text(
                    "INSERT INTO participation_teammates (participation_id, athlete_id, position)"
                    " SELECT p.id, p.athlete_id, 0 FROM participations p"
                    " WHERE p.club = 'EQUIPE'"
                )
            )
    finally:
        engine.dispose()


def test_the_data_migration_sets_the_current_club_from_the_latest_dated_race(sqlite_url):
    """#965 : le club actuel de l'existant suit l'épreuve datée la plus récente."""
    cfg = _alembic_config()
    command.upgrade(cfg, _BEFORE_CURRENT_CLUB_BACKFILL)
    _seed_club_history(sqlite_url)

    command.upgrade(cfg, "head")

    assert dict(_lignes(sqlite_url, "SELECT nom, club FROM athletes")) == {
        "ORDRE": "TCN",
        "VERROU": "MANUEL",
        "ATTENTE": "Y",
        "SANSDATE": "W",
        "VIDE": "A",
        "EGALITE": "P2",
        "EQUIPIER": "PERSO",
    }


# --- Splits tout à zéro (#971) ------------------------------------------------

_BEFORE_ZERO_SPLITS_CLEANUP = "8a22b130deca"


def test_the_data_migration_empties_splits_made_only_of_zero_segments(sqlite_url):
    """#971 : `00:00:00` est un point de passage non franchi. Un rescrape ne vide
    pas une ligne dont tous les segments sont écartés (« vide n'écrase pas »)."""
    cfg = _alembic_config()
    command.upgrade(cfg, _BEFORE_ZERO_SPLITS_CLEANUP)
    splits = [
        {"swim": "00:00:00", "bike": "00:00:00", "run": "0:00:00"},
        {"swim": "00:00", "run": " 00:00:00 "},
        {"swim": "00:12:00", "bike": "00:00:00"},
        {"swim": "FRA", "bike": "00:00:00"},
        {},
        None,
    ]
    engine = sa.create_engine(sqlite_url)
    try:
        with engine.begin() as connexion:
            connexion.execute(
                sa.text(
                    "INSERT INTO athletes (nom, prenom, gender, club_locked, created_at)"
                    " VALUES ('DUPONT', 'P', '', :faux, '2026-01-01')"
                ),
                {"faux": False},
            )
            connexion.execute(
                sa.text(
                    "INSERT INTO courses (id, name, event_type, is_relay, scraped_at, created_at)"
                    " VALUES (1, 'Tri', 'triathlon-m', :faux, '2026-01-01', '2026-01-01')"
                ),
                {"faux": False},
            )
            for valeur in splits:
                connexion.execute(
                    sa.text(
                        "INSERT INTO participations (course_id, athlete_id, status, splits,"
                        " is_pending_validation, created_at)"
                        " VALUES (1, 1, 'finisher', :splits, :faux, '2026-01-01')"
                    ),
                    {"splits": None if valeur is None else json.dumps(valeur), "faux": False},
                )
    finally:
        engine.dispose()

    command.upgrade(cfg, "50f5db3c0a88")

    restants = [
        None if valeur is None else json.loads(valeur)
        for (valeur,) in _lignes(sqlite_url, "SELECT splits FROM participations ORDER BY id")
    ]
    assert restants == [
        None,
        None,
        {"swim": "00:12:00", "bike": "00:00:00"},
        {"swim": "FRA", "bike": "00:00:00"},
        {},
        None,
    ]


# --- Splits sans aucun segment réel (#1194) ----------------------------------

_BEFORE_UNREADABLE_SPLITS_CLEANUP = "c1a11e9e1008"


def test_the_data_migration_empties_splits_without_any_real_segment(sqlite_url):
    """#1194 : la nationalité lue comme la natation (`{"swim": "FRA"}`) sur les
    aquathlons Sport Innovation de Carnac. L'import écarte « FRA » depuis #971,
    mais un rescrape qui n'écrit aucun segment ne vide pas la ligne."""
    cfg = _alembic_config()
    command.upgrade(cfg, _BEFORE_UNREADABLE_SPLITS_CLEANUP)
    splits = [
        {"swim": "FRA"},
        {"swim": "FRA", "bike": "00:00:00"},
        {"swim": "FRA", "run": "00:21:30"},
        {"swim": "00:12:00"},
        {},
        None,
    ]
    engine = sa.create_engine(sqlite_url)
    try:
        with engine.begin() as connexion:
            connexion.execute(
                sa.text(
                    "INSERT INTO athletes (nom, prenom, gender, club_locked, created_at)"
                    " VALUES ('DUPONT', 'P', '', :faux, '2026-01-01')"
                ),
                {"faux": False},
            )
            connexion.execute(
                sa.text(
                    "INSERT INTO courses (id, name, event_type, is_relay, scraped_at, created_at)"
                    " VALUES (1, 'Aquathlon', 'aquathlon-xs', :faux, '2026-01-01', '2026-01-01')"
                ),
                {"faux": False},
            )
            for valeur in splits:
                connexion.execute(
                    sa.text(
                        "INSERT INTO participations (course_id, athlete_id, status, splits,"
                        " is_pending_validation, created_at)"
                        " VALUES (1, 1, 'finisher', :splits, :faux, '2026-01-01')"
                    ),
                    {"splits": None if valeur is None else json.dumps(valeur), "faux": False},
                )
    finally:
        engine.dispose()

    command.upgrade(cfg, "head")

    restants = [
        None if valeur is None else json.loads(valeur)
        for (valeur,) in _lignes(sqlite_url, "SELECT splits FROM participations ORDER BY id")
    ]
    assert restants == [
        None,
        None,
        {"swim": "FRA", "run": "00:21:30"},
        {"swim": "00:12:00"},
        {},
        None,
    ]


# --- Clé d'identité des libellés d'équipe (#1192) ----------------------------

_BEFORE_TEAM_KEYS = "eead8cc8c19d"


def test_the_data_migration_gives_team_labels_a_team_key(sqlite_url):
    """#1192 : « ARNAUD & VINCENT » portait la clé de la personne « ARNAUD Vincent ».
    Deux graphies d'une même équipe se départagent par leur rang d'homonyme."""
    cfg = _alembic_config()
    command.upgrade(cfg, _BEFORE_TEAM_KEYS)
    fiches = [
        ("ARNAUD", "Vincent", "arnaud", "vincent", 0),
        ("ARNAUD", "& VINCENT .", "arnaud", "vincent", 1),
        ("ARNAUD &", "VINCENT", "arnaud", "vincent", 2),
        ("BRETON", "Etienne", "breton", "etienne", 0),
    ]
    engine = sa.create_engine(sqlite_url)
    try:
        with engine.begin() as connexion:
            for nom, prenom, cle_nom, cle_prenom, rang in fiches:
                connexion.execute(
                    sa.text(
                        "INSERT INTO athletes (nom, prenom, gender, club_locked, created_at,"
                        " last_name_key, first_name_key, homonym_rank)"
                        " VALUES (:nom, :prenom, '', :faux, '2026-01-01', :cn, :cp, :rang)"
                    ),
                    {"nom": nom, "prenom": prenom, "faux": False, "cn": cle_nom, "cp": cle_prenom, "rang": rang},
                )
            connexion.execute(
                sa.text(
                    "INSERT INTO courses (id, name, event_type, is_relay, scraped_at, created_at)"
                    " VALUES (1, 'Duathlon', 'duathlon-s', :vrai, '2026-01-01', '2026-01-01')"
                ),
                {"vrai": True},
            )
            # Le résultat d'équipe garde la clé source d'avant ; celui de la
            # personne, rattaché ailleurs, ne bouge pas.
            for athlete_id, cle in ((2, "arnaud|vincent"), (1, "arnaud|vincent")):
                connexion.execute(
                    sa.text(
                        "INSERT INTO participations (course_id, athlete_id, status,"
                        " is_pending_validation, created_at, source_identity_key)"
                        " VALUES (1, :athlete, 'finisher', :faux, '2026-01-01', :cle)"
                    ),
                    {"athlete": athlete_id, "faux": False, "cle": cle},
                )
    finally:
        engine.dispose()

    command.upgrade(cfg, "head")

    assert _lignes(
        sqlite_url,
        "SELECT nom, prenom, last_name_key, first_name_key, homonym_rank FROM athletes ORDER BY id",
    ) == [
        ("ARNAUD", "Vincent", "arnaud", "vincent", 0),
        ("ARNAUD", "& VINCENT .", "arnaud&vincent", "", 0),
        ("ARNAUD &", "VINCENT", "arnaud&vincent", "", 1),
        ("BRETON", "Etienne", "breton", "etienne", 0),
    ]
    assert _lignes(
        sqlite_url, "SELECT athlete_id, source_identity_key FROM participations ORDER BY athlete_id"
    ) == [(1, "arnaud|vincent"), (2, "arnaud&vincent|")]


_BEFORE_COUNTS_FOR_TCN = "baef0d35bb4f"


def test_counts_for_tcn_backfill_applies_the_rule(sqlite_url, monkeypatch):
    """#1206: `tcn` becomes ambiguous; a bare `TCN` counts only when the athlete
    has another validated result under a clear label."""
    monkeypatch.setenv("DATABASE_URL", sqlite_url)
    get_settings.cache_clear()
    cfg = _alembic_config()
    command.upgrade(cfg, _BEFORE_COUNTS_FOR_TCN)
    engine = sa.create_engine(sqlite_url)
    with engine.begin() as connexion:
        connexion.execute(sa.text(
            "INSERT INTO athletes (id, nom, prenom, gender, club_locked, created_at, homonym_rank)"
            " VALUES (1, 'MARTIN', 'Anne', '', 0, '2026-01-01', 0),"
            " (2, 'DURAND', 'Paul', '', 0, '2026-01-01', 0)"
        ))
        connexion.execute(sa.text(
            "INSERT INTO courses (id, name, event_date, event_type, is_relay, ranked_by_laps,"
            " created_at, participation_count, tcn_count)"
            " VALUES (1, 'A', '2026-05-01', 'triathlon-m', 0, 0, '2026-01-01', 0, 0),"
            " (2, 'B', '2026-06-01', 'triathlon-m', 0, 0, '2026-01-01', 0, 0)"
        ))
        connexion.execute(sa.text(
            "INSERT INTO participations (id, athlete_id, course_id, club, bib_number, status,"
            " is_relay, is_pending_validation, is_rejected, athlete_locked, created_at) VALUES"
            " (1, 1, 1, 'TCN', '1', 'finisher', 0, 0, 0, 0, '2026-01-01'),"
            " (2, 1, 2, 'Triathlon Club Nantais', '1', 'finisher', 0, 0, 0, 0, '2026-01-01'),"
            " (3, 2, 1, 'TCN', '2', 'finisher', 0, 0, 0, 0, '2026-01-01')"
        ))
    engine.dispose()

    command.upgrade(cfg, "head")
    get_settings.cache_clear()

    assert _lignes(
        sqlite_url, "SELECT value, ambiguous FROM counter_scope_entries"
        " WHERE kind = 'tcn_club_label' ORDER BY value"
    ) == [("tcn", 1), ("tri club nantais", 0), ("triathlon club nantais", 0)]
    assert _lignes(
        sqlite_url, "SELECT id, counts_for_tcn FROM participations ORDER BY id"
    ) == [(1, 1), (2, 1), (3, 0)]
    assert _lignes(sqlite_url, "SELECT id, tcn_count FROM courses ORDER BY id") == [(1, 1), (2, 1)]


def test_downgrade_then_upgrade_of_counts_for_tcn(sqlite_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", sqlite_url)
    get_settings.cache_clear()
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, _BEFORE_COUNTS_FOR_TCN)
    assert "counts_for_tcn" not in _columns(sqlite_url, "participations")
    assert "ambiguous" not in _columns(sqlite_url, "counter_scope_entries")
    command.upgrade(cfg, "head")
    get_settings.cache_clear()
    assert "counts_for_tcn" in _columns(sqlite_url, "participations")


def test_club_members_table_is_created(base_migree):
    assert _columns(base_migree, "club_members") == {
        "id", "season", "licence_id", "nom", "prenom", "gender", "last_name_key",
        "first_name_key", "athlete_id", "link_status", "source", "created_at",
    }


def test_downgrade_then_upgrade_of_club_members(sqlite_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", sqlite_url)
    get_settings.cache_clear()
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "c4f1a7d2e9b3")
    assert "club_members" not in _tables(sqlite_url)
    command.upgrade(cfg, "head")
    assert "club_members" in _tables(sqlite_url)
