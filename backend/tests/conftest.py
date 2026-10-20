"""
Fixtures partagées des tests.

Base SQLite en mémoire, schéma posé une fois par worker et chaque test dans une
transaction annulée (#1706) + TestClient FastAPI avec la dépendance `get_db`
surchargée pour pointer sur cette base.
"""
import atexit
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import config as _config

# Isolation de `backend/.env` (#911), avant que quoi que ce soit n'importe
# `core/database.py` : son moteur global se construit à l'import, et le lifespan
# de chaque `TestClient` s'y connecte et initialise PostHog. Les variables
# d'environnement priment sur `.env`, mais celui-ci resterait lu pour tout le
# reste : on coupe sa lecture.
_config.Settings.model_config["env_file"] = None
_UNIT_DB_DIR = tempfile.mkdtemp(prefix="unit-suite-")
atexit.register(shutil.rmtree, _UNIT_DB_DIR, ignore_errors=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_UNIT_DB_DIR}/unit.db"
os.environ["POSTHOG_PROJECT_TOKEN"] = ""
_config.get_settings.cache_clear()

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def pytest_addoption(parser):
    parser.addoption(
        "--migrations",
        action="store_true",
        help="Inclut les tests marqués `migrations` (désélectionnés par défaut, lancés en CI).",
    )


def pytest_collection_modifyitems(config, items):
    # Désélection explicite plutôt que `-m "not migrations"` : elle tient quel que
    # soit le `-m` passé en ligne de commande.
    if config.getoption("--migrations"):
        return
    deselected = [item for item in items if item.get_closest_marker("migrations")]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = [item for item in items if item not in deselected]


def load_klikego_fixture(name: str) -> str:
    """Charge un HTML de test Klikego depuis backend/tests/fixtures/klikego/.

    Utilisé par les tests offline du scraper Klikego (fan-out, énumération de
    heats) — Principe III, aucun accès réseau dans la suite unitaire.
    """
    return (_FIXTURES_DIR / "klikego" / name).read_text(encoding="utf-8")


def save_entry(db, scraped):
    """Arrange a row through the public manual entry path and return the ORM row.

    Imports are local: `app.services` must not load before the settings isolation above.
    """
    from app.repositories import participation_repository
    from app.services import scrape_service

    answer = scrape_service.save_public_entry(db, scraped)
    row = participation_repository.get(db, answer.id)
    assert row is not None, "identity opposed: save_public_entry rolled the row back"
    return row


@pytest.fixture(autouse=True)
def _compteurs_de_debit_vierges():
    """Les plafonds de débit (#395) comptent en mémoire du process.

    Sans cette remise à zéro, les appels d'un test se cumulent avec ceux du
    suivant — la suite compte plus d'un import d'épreuve — et l'ordre
    d'exécution déciderait qui prend un 429.
    """
    from app.api.deps import reset_rate_limits

    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture(autouse=True)
def _pastilles_sans_cache():
    """Les listes des revues vivent en mémoire du process (#1352, #1384) : un
    test lirait sinon la liste laissée par le précédent."""
    from app.services import athlete_identity_review, course_duplicates

    athlete_identity_review.candidates_cache.clear()
    course_duplicates.candidates_cache.clear()
    yield


@pytest.fixture(autouse=True)
def _portee_des_compteurs_par_defaut():
    """Le registre de `core/counter_scope` est un état de **processus** (#95).

    Même raison que les plafonds de débit juste au-dessus : sans cette remise à
    zéro, un test qui configure d'autres libellés de club les laisse au suivant,
    et l'ordre d'exécution déciderait quels résultats sont comptés comme
    résultats du club.

    Les défauts du registre sont les valeurs d'avant la bascule en base : la
    suite s'exécute donc sur la configuration livrée, sans avoir à semer quoi
    que ce soit — les fixtures montent leur schéma par `create_all`, jamais par
    les migrations qui portent l'amorçage.
    """
    from app.core import counter_scope

    counter_scope.reset()
    yield
    counter_scope.reset()


@pytest.fixture(autouse=True)
def _rejeux_klikego_sans_attente(request, monkeypatch):
    """Les rejeux 5xx de `klikego_platform.get_page` attendent (#943) : pas dans
    la suite unitaire. Un test `integration` garde l'attente, face au vrai site."""
    if request.node.get_closest_marker("integration"):
        return
    from app.scrapers import klikego_platform

    monkeypatch.setattr(klikego_platform, "_sleep", lambda _seconds: None)


@pytest.fixture(autouse=True)
def _sans_resolution_dns(request, monkeypatch):
    """Aucune résolution de nom en unitaire : `getaddrinfo` n'a pas de délai, et
    le garde SSRF de `core/http` résolvait les vrais hosts des tests qui ne
    bouchonnent pas `http._resolve` (`test_batch_runs` : 5 s par test, et un
    résolveur qui cale figeait la suite). Échec immédiat, comme un DNS mort ;
    l'encodage `idna` reste fait, `_resolve` en éprouve l'erreur. `localhost` et
    les adresses littérales restent résolus : ils ne sortent pas de la machine,
    et psycopg les résout ainsi pour le job PostgreSQL."""
    if request.node.get_closest_marker("integration"):
        return
    import ipaddress
    import socket

    reel = socket.getaddrinfo

    def _dns_mort(host, *args, **kwargs):
        if host in (None, "localhost"):
            return reel(host, *args, **kwargs)
        if isinstance(host, str):
            try:
                ipaddress.ip_address(host)
            except ValueError:
                host.encode("idna")
            else:
                return reel(host, *args, **kwargs)
        raise socket.gaierror(socket.EAI_NONAME, "aucune résolution DNS dans la suite unitaire")

    monkeypatch.setattr(socket, "getaddrinfo", _dns_mort)


@pytest.fixture(scope="session")
def _postgres_engine():
    """Le PostgreSQL de `TEST_POSTGRES_URL` (job CI dédié, #947), ou `None`.

    Schéma posé une fois par session (#1249) : le DDL par test coûtait
    l'essentiel de la durée du job. Séquentiel (`-n 0`) : les workers
    partageraient la même base.
    """
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        yield None
        return
    import app.models  # noqa: F401 — enregistre toutes les tables sur Base.metadata
    from app.core.database import Base

    # Same driver resolution as production (#1136).
    engine = create_engine(_config.Settings(database_url=url).database_url)
    with engine.begin() as connection:
        for extension in ("pg_trgm", "unaccent"):
            connection.exec_driver_sql(f"CREATE EXTENSION IF NOT EXISTS {extension}")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _sqlite_engine_with_schema(*, savepoints: bool, foreign_keys: bool = False):
    """Moteur SQLite mémoire, schéma posé par `create_all`."""
    import app.models  # noqa: F401 (enregistre toutes les tables sur Base.metadata)
    from app.core.database import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _connect(dbapi_connection, _record):
        if savepoints:
            # Contournement pysqlite de la documentation SQLAlchemy 2.0 (avec
            # l'événement `begin`) : sans lui, le pilote émet ses propres
            # BEGIN/COMMIT et les SAVEPOINT ne tiennent pas.
            dbapi_connection.isolation_level = None
        if foreign_keys:
            # Avant toute transaction : SQLite ignore ce PRAGMA à l'intérieur d'une.
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    if savepoints:
        @event.listens_for(engine, "begin")
        def _begin(connection):
            connection.exec_driver_sql("BEGIN")

    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="session")
def _sqlite_engine():
    """Schéma posé une fois par worker xdist (#1706)."""
    engine = _sqlite_engine_with_schema(savepoints=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def _sqlite_engine_fk():
    engine = _sqlite_engine_with_schema(savepoints=True, foreign_keys=True)
    yield engine
    engine.dispose()


@contextmanager
def _rolled_back_session(engine):
    """Une `Session` vierge dans une transaction annulée en fin de test : ses
    `commit()` et `rollback()` ne portent que sur des SAVEPOINT (recette SQLAlchemy
    « Joining a Session into an External Transaction »)."""
    with engine.connect() as connection:
        transaction = connection.begin()
        # Garde : une seconde `Session` sur `get_bind()` (mode par défaut) trouve
        # un SAVEPOINT ouvert et s'y imbrique, au lieu de rejoindre `transaction`
        # en `rollback_only`, où son `rollback()` l'annulerait.
        connection.begin_nested()
        session = Session(
            bind=connection, autoflush=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            session.close()
            assert transaction.is_active, "transaction du test perdue en cours de route"
            transaction.rollback()


@pytest.fixture
def db_session(request, _postgres_engine, _sqlite_engine):
    """Session SQLAlchemy sur une base jetable, schéma créé via les modèles.

    SQLite en mémoire par défaut, partagée par le worker : le test tourne dans
    une transaction annulée à la fin, ses `commit()` deviennent des SAVEPOINT.
    Un test qui observe ces frontières (il compte les instructions SQL, ou du
    code commite par une session à part) porte le marqueur `own_database` et
    reçoit sa propre base, comme avant #1706. Sous `TEST_POSTGRES_URL`, la base de la
    session, vidée en fin de test et ses séquences remises à 1 : les tests de
    concurrence commitent depuis plusieurs connexions, un rollback englobant ne
    les isolerait pas. `DELETE` plutôt que `TRUNCATE`, quatre fois plus lent sur
    des tables presque vides.
    """
    from app.core.database import Base

    if _postgres_engine is not None:
        session = sessionmaker(autocommit=False, autoflush=False, bind=_postgres_engine)()
        try:
            yield session
        finally:
            session.close()
            with _postgres_engine.begin() as connection:
                for table in reversed(Base.metadata.sorted_tables):
                    connection.execute(table.delete())
                connection.exec_driver_sql(
                    "SELECT setval(oid::regclass, 1, false) FROM pg_class WHERE relkind = 'S'"
                )
        return

    if request.node.get_closest_marker("own_database"):
        engine = _sqlite_engine_with_schema(savepoints=False)
        session = Session(bind=engine, autoflush=False)
        try:
            yield session
        finally:
            session.close()
            engine.dispose()
        return

    with _rolled_back_session(_sqlite_engine) as session:
        yield session


@pytest.fixture
def db_session_fk(_sqlite_engine_fk):
    """Comme `db_session`, mais avec `PRAGMA foreign_keys=ON` : les FK s'y
    vérifient comme en PostgreSQL, là où `database.py` les laisse inertes.
    SQLite seul, et sans le marqueur `own_database`, qu'il ignore."""
    with _rolled_back_session(_sqlite_engine_fk) as session:
        yield session


@pytest.fixture
def client(db_session):
    """TestClient avec `get_db` surchargé pour utiliser la base de test.

    Neutralise aussi `require_site_access` (#509) : la garde s'applique à
    quasiment tous les routers, et la quasi-totalité de la suite ne teste
    pas ce mécanisme — `test_site_access_gate.py` la retire explicitement
    pour l'éprouver.
    """
    from app.api.deps import require_site_access
    from app.core.database import get_db
    from app.main import app

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[require_site_access] = lambda: None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
