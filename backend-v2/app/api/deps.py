"""Dépendances FastAPI partagées."""
from app.core.config import Settings, get_settings


def settings_dep() -> Settings:
    """Injecte les réglages applicatifs dans les routers."""
    return get_settings()
