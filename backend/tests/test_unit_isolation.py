"""Garde-fous : la suite unitaire ne lit jamais `backend/.env` (#911).

Sans cela, un `.env` pointant vers la base de production faisait ouvrir au
lifespan de chaque `TestClient` une connexion vers Azure, et un jeton PostHog
renseigné envoyait les événements des routes testées vers le vrai projet.
"""
from app.core import database
from app.core.config import Settings, get_settings


def test_settings_ignore_the_dotenv_of_the_working_directory(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "DATABASE_URL=postgresql://u:p@prod.example/x\nPOSTHOG_PROJECT_TOKEN=phc_real\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    settings = Settings()

    assert not settings.database_url.startswith("postgresql")
    assert settings.posthog_project_token.get_secret_value() == ""


def test_the_global_engine_is_a_throwaway_sqlite():
    url = database.engine.url

    assert url.get_backend_name() == "sqlite"
    assert url.database and not url.database.endswith("triathlon.db")


def test_posthog_is_off_for_the_unit_suite():
    assert get_settings().posthog_project_token.get_secret_value() == ""
