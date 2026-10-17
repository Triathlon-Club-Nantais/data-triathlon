import pytest
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.repositories.dialect import dialect_insert, is_postgres


def test_sqlite_session_is_not_postgres_and_gets_the_sqlite_insert(db_session):
    if db_session.get_bind().dialect.name == "postgresql":
        pytest.skip("SQLite branch only")
    assert not is_postgres(db_session)
    assert dialect_insert(db_session) is sqlite_insert
