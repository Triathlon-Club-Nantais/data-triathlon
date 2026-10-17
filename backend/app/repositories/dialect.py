"""Le moteur derrière une session : PostgreSQL (prod, preview) ou SQLite (dev, tests)."""
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session


def is_postgres(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def dialect_insert(db: Session):
    """L'`insert` du moteur, seul à porter `on_conflict_do_nothing`."""
    return postgresql_insert if is_postgres(db) else sqlite_insert
