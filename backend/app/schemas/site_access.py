"""DTO de l'ouverture de session du mot de passe site (#509)."""
from pydantic import BaseModel, Field


class SiteAccessLogin(BaseModel):
    """Corps de `POST /site-access/session`.

    `max_length` (revue finale, § Plafond de débit du design) : cette route
    déclenche `hashlib.scrypt` sur `password` avant même de savoir s'il est
    correct, en plus du plafond de débit par IP (`public_write_rate_limit`) —
    borner la taille du corps évite de lui tendre un `password` arbitrairement
    long sans raison. 200, même ordre de grandeur que les autres champs libres
    bornés du dépôt (`schemas/feedback.py`).
    """

    password: str = Field(max_length=200)
