def test_session_scope_yield_puis_ferme(monkeypatch):
    """session_scope() fournit une Session et la ferme à la sortie du bloc."""
    from app.core import database

    fermee = {"v": False}

    class FakeSession:
        def close(self):
            fermee["v"] = True

    monkeypatch.setattr(database, "SessionLocal", lambda: FakeSession())

    with database.session_scope() as db:
        assert isinstance(db, FakeSession)
        assert fermee["v"] is False

    assert fermee["v"] is True


def test_session_scope_ferme_meme_en_cas_d_erreur(monkeypatch):
    from app.core import database

    fermee = {"v": False}

    class FakeSession:
        def close(self):
            fermee["v"] = True

    monkeypatch.setattr(database, "SessionLocal", lambda: FakeSession())

    try:
        with database.session_scope():
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert fermee["v"] is True
