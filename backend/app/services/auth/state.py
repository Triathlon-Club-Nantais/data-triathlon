"""Jeton d'état du parcours — preuve d'origine, signée en JWS HS256 (`joserfc`).

L'état ne crée **aucune ligne en base** : il vit dans un cookie court, signé.
C'est ce qui rend l'endpoint d'entrée quasi gratuit et supprime tout levier de
croissance illimitée offert à un anonyme.

Le `provider` fait partie de la charge signée : un état émis pour A n'est pas
recevable au retour de B (FR-021, FR-022).
"""
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC

from joserfc import jwt
from joserfc.jwk import OctKey

from app.core.config import get_settings
from app.core.time import utcnow
from app.services.auth.errors import LoginError

ALGORITHM = "HS256"


@dataclass(frozen=True)
class StatePayload:
    provider: str
    state: str
    round_trip: dict[str, str] = field(default_factory=dict)


def new_state() -> str:
    """Valeur imprévisible liant le retour au parcours qui l'a initié (FR-020)."""
    return secrets.token_urlsafe(32)


def sign(*, provider: str, state: str, round_trip: Mapping[str, str]) -> str:
    """Signe la preuve d'origine. `round_trip` est recopié **sans être lu**."""
    settings = get_settings()
    maintenant = _now()
    charge = {
        "provider": provider,
        "state": state,
        "round_trip": dict(round_trip),
        "iat": maintenant,
        "exp": maintenant + settings.auth_state_ttl_seconds,
    }
    return jwt.encode({"alg": ALGORITHM}, charge, _key(settings.auth_session_secret_key))


def read(token: str) -> StatePayload:
    """Relit la preuve. Lève `LoginError("state_mismatch")` sur **tout** défaut.

    Un seul code pour toutes les formes de refus (absente, altérée, expirée,
    signée d'une autre clé) : distinguer les causes renseignerait un attaquant
    sans aider personne d'autre.
    """
    settings = get_settings()
    if not token or not settings.auth_session_secret_key:
        raise LoginError("state_mismatch")

    try:
        jeton = jwt.decode(token, _key(settings.auth_session_secret_key), algorithms=[ALGORITHM])
        jwt.JWTClaimsRegistry(exp={"essential": True}).validate(jeton.claims)
    except Exception as refus:
        raise LoginError("state_mismatch") from refus

    charge = jeton.claims
    aller_retour = charge.get("round_trip")
    if not isinstance(charge.get("provider"), str) or not isinstance(charge.get("state"), str):
        raise LoginError("state_mismatch")

    return StatePayload(
        provider=charge["provider"],
        state=charge["state"],
        round_trip=aller_retour if isinstance(aller_retour, dict) else {},
    )


def _key(secret: str) -> OctKey:
    return OctKey.import_key(secret)


def _now() -> int:
    """Horodatage `NumericDate` (secondes depuis l'époque, en UTC).

    `utcnow()` rend un datetime **naïf** — c'est la convention des colonnes du
    projet — et `datetime.timestamp()` interprète un naïf en heure **locale**.
    Sans le `replace(tzinfo=UTC)`, un serveur à UTC+2 émettait donc un `exp`
    daté de deux heures dans le passé, et **tout** parcours échouait en
    `state_mismatch`.
    """
    return int(utcnow().replace(tzinfo=UTC).timestamp())
