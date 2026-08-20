"""DTO de l'ouverture de session du mot de passe site (#509)."""
from pydantic import BaseModel


class SiteAccessLogin(BaseModel):
    """Corps de `POST /site-access/session`."""

    password: str
