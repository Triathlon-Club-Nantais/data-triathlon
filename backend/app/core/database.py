"""
Engine et session SQLAlchemy.

La création des tables est gérée par Alembic (plus de `create_all()` au démarrage).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()

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
