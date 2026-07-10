"""
Engine et session SQLAlchemy.

La création des tables est gérée par Alembic (plus de `create_all()` au démarrage).
"""
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()


def _unicode_lower(value: str | None) -> str | None:
    return value.lower() if value is not None else None


def _unicode_upper(value: str | None) -> str | None:
    return value.upper() if value is not None else None


@event.listens_for(Engine, "connect")
def _register_sqlite_unicode_case(dbapi_connection, _connection_record) -> None:
    """Rend `lower()`/`upper()` sensibles aux accents sur SQLite (dev et tests).

    SQLite ne les applique qu'à l'ASCII : `lower('LEMÉE')` renvoie `'lemÉe'`.
    `get_by_identity` comparait donc cette valeur à `'lemée'` calculé en Python,
    ne retrouvait jamais un athlète au nom accentué et le recréait à chaque
    import. PostgreSQL (prod) est déjà Unicode-aware et n'est pas concerné :
    ce listener ne s'applique qu'aux connexions SQLite.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.create_function("lower", 1, _unicode_lower, deterministic=True)
        dbapi_connection.create_function("upper", 1, _unicode_upper, deterministic=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.is_sqlite else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dépendance FastAPI : fournit une session, la ferme en fin de requête."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
