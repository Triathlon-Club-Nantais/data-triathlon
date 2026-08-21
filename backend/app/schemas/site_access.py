"""DTO de l'ouverture de session du mot de passe site (#509)."""
from pydantic import BaseModel, Field

#: Longueur maximale du mot de passe du site, **définie une seule fois** et
#: partagée par les deux bouts : la connexion (`SiteAccessLogin`, ici) et le
#: remplacement (`SiteAccessReplaceIn`, `schemas/site_access_config.py`).
#:
#: Deux bornes indépendantes avaient divergé (relevé en revue de #513) : le
#: remplacement n'en avait aucune, donc un `PUT` de 201 caractères réussissait
#: — le secret tournait, toutes les sessions ouvertes tombaient, et la
#: connexion rendait ensuite 422 sur le seul mot de passe qui aurait marché.
#: Les poser à deux endroits, c'est accepter qu'elles se séparent à nouveau.
#:
#: 200 : cette route déclenche `hashlib.scrypt` sur `password` avant même de
#: savoir s'il est correct (revue finale de #509, § Plafond de débit du
#: design) — borner la taille du corps évite de lui tendre un `password`
#: arbitrairement long, en plus du plafond de débit par IP. Même ordre de
#: grandeur que les autres champs libres bornés du dépôt
#: (`schemas/feedback.py`).
MAX_PASSWORD_LENGTH = 200


class SiteAccessLogin(BaseModel):
    """Corps de `POST /site-access/session`."""

    password: str = Field(max_length=MAX_PASSWORD_LENGTH)
