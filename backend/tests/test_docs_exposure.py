"""Exposition de `/docs`, `/redoc` et `/openapi.json` (#399, constat A05-1).

Les trois chemins tiennent au même réglage : les tester ensemble est ce qui
empêche d'en refermer un et d'oublier les deux autres — `/redoc` sert le même
schéma que `/docs`, et `/openapi.json` est ce que les deux consomment.
"""
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings

CHEMINS = ["/docs", "/redoc", "/openapi.json"]


@pytest.fixture
def application(monkeypatch, request):
    """Application construite avec `DOCS_ENABLED` forcé à la valeur demandée.

    `get_settings()` est en lru_cache et `create_app()` la lit : forcer la
    variable *avant* l'appel, et vider le cache de part et d'autre pour ne pas
    le laisser pollué pour les tests suivants.
    """
    monkeypatch.setenv("DOCS_ENABLED", request.param)
    get_settings.cache_clear()
    from app.main import create_app

    yield create_app()
    get_settings.cache_clear()


@pytest.mark.parametrize("application", ["false"], indirect=True)
@pytest.mark.parametrize("chemin", CHEMINS)
def test_documentation_fermee(application, chemin):
    assert TestClient(application).get(chemin).status_code == 404


@pytest.mark.parametrize("application", ["true"], indirect=True)
@pytest.mark.parametrize("chemin", CHEMINS)
def test_documentation_ouverte(application, chemin):
    assert TestClient(application).get(chemin).status_code == 200


def test_defaut_ferme():
    """Sans réglage, la documentation est fermée.

    `_env_file=None` : le défaut testé est celui du code, pas celui du `.env`
    local du poste qui lance la suite.
    """
    assert Settings(_env_file=None).docs_enabled is False
