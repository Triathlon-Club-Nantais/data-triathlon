"""Aides communes aux tests de la CLI de batch.

`session_scope` est importé **par valeur** dans chaque module de commande
(`from app.core.database import session_scope`) : chaque module en tient donc sa
propre liaison, et brancher la base de test suppose de patcher le module visé,
pas la source. C'est pourquoi la fixture prend le module en argument — recopiée
à l'identique dans trois modules jusqu'à #590.
"""
from contextlib import contextmanager

import pytest


@pytest.fixture
def brancher_session(monkeypatch, db_session):
    """Fait rendre la session de test au `session_scope` du module de commande."""

    def _brancher(module) -> None:
        @contextmanager
        def _session():
            yield db_session

        monkeypatch.setattr(module, "session_scope", _session)

    return _brancher
