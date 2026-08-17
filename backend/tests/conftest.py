"""
Fixtures partagées des tests.

Base SQLite en mémoire isolée par test + TestClient FastAPI avec la dépendance
`get_db` surchargée pour pointer sur cette base.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
def client(db_session):
    """TestClient avec `get_db` surchargé pour utiliser la base de test."""
    from app.core.database import get_db
    from app.main import app

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
