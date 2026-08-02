"""Orchestration du parcours de connexion.

Ce module n'ouvre aucune connexion et ne construit aucune requête : il enchaîne
registre, état, provisionnement et session. Toute la sortie réseau vit dans le
fournisseur, tout le SQL dans les repositories.

**L'ordre de `complete_login` est contractuel** (FR-025) : validation locale
d'abord, réseau ensuite. Ce n'est pas une préférence de style — le limiteur de
threads AnyIO est mesuré à 40 et toutes les routes du projet sont `def` : un
retour de parcours coûteux est un levier de déni de service **sur le site
public**.
"""
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User
from app.services.auth import provisioning, session, state
from app.services.auth.errors import LoginError
from app.services.auth.idp import registry

logger = logging.getLogger(__name__)


def start_login(provider_slug: str) -> tuple[str, str]:
    """Prépare le départ : rend l'URL du fournisseur et le jeton d'état signé.

    Aucune ligne n'est créée en base — l'état vit dans le cookie signé.
    """
    provider = registry.get(provider_slug)
    if provider is None:
        raise LoginError("unknown_provider")
    # Les deux gardes, et dans cet ordre : le socle (clé de signature, liste
    # d'autorisation) **puis** le fournisseur. Sans le premier, `joserfc` levait
    # un `ValueError` nu sur une clé vide, qui remontait au handler global en
    # 500 — une page technique dans un navigateur en pleine navigation.
    if not get_settings().auth_is_configured or not provider.is_configured():
        raise LoginError("not_configured")

    value = state.new_state()
    request = provider.authorize(state=value)
    state_token = state.sign(
        provider=provider.slug, state=value, round_trip=request.round_trip
    )
    return request.url, state_token


def complete_login(
    db: Session,
    *,
    provider_slug: str,
    state_token: str | None,
    state_param: str | None,
    code: str | None,
    error: str | None,
) -> tuple[str, User]:
    """Achève le parcours : rend le jeton de session brut et son utilisateur.

    Lève `LoginError` sur tout refus. Les trois premières vérifications sont
    **locales** : aucun octet ne part tant qu'elles n'ont pas toutes abouti.
    """
    provider = registry.get(provider_slug)
    if provider is None:
        raise LoginError("unknown_provider")

    payload = state.read(state_token or "")
    if payload.provider != provider_slug or not state_param or payload.state != state_param:
        # Un état émis pour A n'est pas recevable au retour de B : c'est la
        # confusion de fournisseur que ferme le `provider` dans la charge signée.
        raise LoginError("state_mismatch")

    if error or not code:
        # Refus de consentement, ou retour inexploitable. Le message du
        # fournisseur n'est **jamais** repris : seul un code fermé sort d'ici.
        logger.info("Provider %s returned no usable code", provider_slug)
        raise LoginError("provider_error")

    if not provider.is_configured():
        raise LoginError("not_configured")

    identity = provider.fetch_identity(code=code, round_trip=payload.round_trip)
    user = provisioning.resolve_user(db, identity)
    return session.open_for(db, user), user
