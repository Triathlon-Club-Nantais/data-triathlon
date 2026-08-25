"""Dimensionnement du pool de connexions de l'engine (#585)."""

from app.core.config import Settings
from app.core.database import _create_engine


def test_engine_reprend_le_dimensionnement_des_reglages(tmp_path):
    """`pool_size`/`max_overflow`/`pool_timeout` viennent de `Settings`, pas des
    défauts muets de SQLAlchemy — condition pour pouvoir les aligner un jour sur
    le plafond réel de la base (#585)."""
    db_path = tmp_path / "pool_check.db"
    settings = Settings(
        database_url=f"sqlite:///{db_path}",
        db_pool_size=7,
        db_max_overflow=3,
        db_pool_timeout_seconds=12,
    )

    engine = _create_engine(settings)
    with engine.connect():
        pass

    assert engine.pool.size() == 7
    assert engine.pool._max_overflow == 3
    assert engine.pool._timeout == 12
