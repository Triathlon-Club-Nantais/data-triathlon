"""PostgreSQL URLs resolve to the psycopg 3 driver (#1136)."""

import pytest
from sqlalchemy.engine import make_url

from app.core.config import Settings


@pytest.mark.parametrize(
    "url",
    [
        "postgres://u:p@db.example.org:5432/app",
        "postgresql://u:p@db.example.org:5432/app",
        "postgresql+psycopg2://u:p@db.example.org:5432/app",
    ],
)
def test_postgres_urls_use_the_psycopg_driver(url):
    """SQLAlchemy 2.0 maps a bare `postgresql://` to psycopg2 and 2.1 to
    psycopg: pinning the driver keeps both, and every PaaS spelling, on the
    one package installed."""
    parsed = make_url(Settings(database_url=url).database_url)

    assert parsed.drivername == "postgresql+psycopg"
    assert parsed.host == "db.example.org"
    assert parsed.database == "app"


def test_sqlite_urls_are_left_untouched():
    assert Settings(database_url="sqlite:///./x.db").database_url == "sqlite:///./x.db"
