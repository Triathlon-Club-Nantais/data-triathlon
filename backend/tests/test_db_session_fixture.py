"""Le `db_session` SQLite tient sa transaction annulée de bout en bout (#1706).

Une seconde `Session` ouverte sur `db.get_bind()` (batch, `_bump_last_seen`)
rejoignait la transaction du worker en mode `rollback_only` : son `rollback()`
l'annulait, et le test commitait ensuite pour de vrai dans la base partagée.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session


def test_a_second_session_rollback_keeps_the_per_test_transaction(db_session):
    connection = db_session.get_bind()

    with Session(bind=connection) as other:
        other.execute(select(1))
        other.rollback()

    assert connection.in_transaction()
