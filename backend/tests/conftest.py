"""
Fixtures partagées des tests.

Base SQLite en mémoire isolée par test + TestClient FastAPI avec la dépendance
`get_db` surchargée pour pointer sur cette base.
"""
import atexit
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
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


def load_klikego_fixture(name: str) -> str:
    """Charge un HTML de test Klikego depuis backend/tests/fixtures/klikego/.

    Utilisé par les tests offline du scraper Klikego (fan-out, énumération de
    heats) — Principe III, aucun accès réseau dans la suite unitaire.
    """
    return (_FIXTURES_DIR / "klikego" / name).read_text(encoding="utf-8")


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


@pytest.fixture
def db_session():
    """Session SQLAlchemy sur une base SQLite en mémoire, schéma créé via les modèles."""
    import app.models  # noqa: F401 — enregistre toutes les tables sur Base.metadata
    from app.core.database import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def db_session_fk():
    """Comme `db_session`, mais avec `PRAGMA foreign_keys=ON` : les FK s'y
    vérifient comme en PostgreSQL, là où `database.py` les laisse inertes."""
    from sqlalchemy import event

    import app.models  # noqa: F401
    from app.core.database import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _foreign_keys_on(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


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
