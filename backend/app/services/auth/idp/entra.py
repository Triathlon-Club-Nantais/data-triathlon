"""Fournisseur d'identité Entra External ID (#1323) : Google et code par e-mail.

OIDC par code d'autorisation + PKCE sur `authlib.integrations.httpx_client`,
dont le client hérite de `httpx.Client` : découverte, JWKS et jeton passent
tous par `transport=`, donc par le contrôle de destination du projet (FR-022).

Ce client n'a pas de `parse_id_token` (il n'existe que dans les intégrations de
framework) : l'`id_token` est vérifié par `joserfc` (signature) puis par
`CodeIDToken` d'Authlib (émetteur, audience, nonce, expiration). Rationale :
`specs/20261011-155714-comptes-membres-socle/research.md` R2 et R3.
"""
import logging
import secrets
import time
from collections.abc import Callable, Mapping
from urllib.parse import urlparse

import httpx
from authlib.integrations.httpx_client import OAuth2Client
from authlib.oidc.core import CodeIDToken
from joserfc import jwt
from joserfc.errors import InvalidKeyIdError, JoseError
from joserfc.jwk import KeySet

from app.core import http
from app.core.config import get_settings
from app.services.auth.errors import LoginError
from app.services.auth.idp.base import AuthorizationRequest, ExternalIdentity

logger = logging.getLogger(__name__)

SCOPE = "openid profile email"
TIMEOUT = httpx.Timeout(10.0)
CACHE_TTL_SECONDS = 3600
LEEWAY_SECONDS = 120


class EntraIdentityProvider:
    """Parcours OIDC + PKCE chez Entra External ID."""

    slug = "entra"
    label = "Google ou code par e-mail"

    def __init__(
        self, transport_factory: Callable[[], httpx.BaseTransport] | None = None
    ) -> None:
        # Une fabrique, pas un transport : même raison que pour GitHub.
        self._transport_factory = transport_factory or http.guarded_transport
        self._cache: dict[str, tuple[float, dict]] = {}

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(
            settings.auth_entra_subdomain
            and settings.auth_entra_tenant_id
            and settings.auth_entra_client_id
            and settings.auth_entra_client_secret
        )

    def _authority(self) -> str:
        settings = get_settings()
        return f"https://{settings.auth_entra_subdomain}.ciamlogin.com/{settings.auth_entra_tenant_id}"

    def _client(self) -> OAuth2Client:
        settings = get_settings()
        return OAuth2Client(
            client_id=settings.auth_entra_client_id,
            client_secret=settings.auth_entra_client_secret.get_secret_value(),
            scope=SCOPE,
            redirect_uri=f"{settings.auth_redirect_base_url}/api/v1/auth/{self.slug}/callback",
            token_endpoint_auth_method="client_secret_post",  # noqa: S106 (nom de méthode, pas un secret)
            code_challenge_method="S256",
            follow_redirects=False,
            timeout=TIMEOUT,
            transport=self._transport_factory(),
        )

    def authorize(self, *, state: str) -> AuthorizationRequest:
        """Points de terminaison construits, pas découverts : aucune sortie réseau."""
        verifier = secrets.token_urlsafe(48)
        nonce = secrets.token_urlsafe(32)
        with self._client() as client:
            url, _ = client.create_authorization_url(
                f"{self._authority()}/oauth2/v2.0/authorize",
                state=state,
                code_verifier=verifier,
                nonce=nonce,
            )
        return AuthorizationRequest(url=url, round_trip={"verifier": verifier, "nonce": nonce})

    def fetch_identity(
        self, *, code: str, round_trip: Mapping[str, str]
    ) -> ExternalIdentity:
        nonce = round_trip.get("nonce", "")
        if not nonce:
            # `CodeIDToken` saute la vérification du nonce quand on n'en attend aucun.
            raise LoginError("provider_error")

        with self._client() as client:
            token = self._fetch_token(client, code=code, verifier=round_trip.get("verifier", ""))
            claims = self._validated_claims(client, token, nonce=nonce)

        # Entra n'émet pas `email_verified` : `xms_edov` vaut vrai pour une
        # adresse venue de Google ou du code e-mail. Absent ou faux, l'adresse
        # n'est pas certifiée et le provisionnement refuse (FR-021 avant production).
        email = str(claims.get("email") or "").strip()
        verified = bool(email) and claims.get("xms_edov") is True
        return ExternalIdentity(
            provider=self.slug,
            subject=claims["oid"],
            email=email,
            email_verified=verified,
            display_name=str(claims.get("name") or ""),
            verified_emails=(email,) if verified else (),
        )

    def _fetch_token(self, client: OAuth2Client, *, code: str, verifier: str) -> dict:
        try:
            token = client.fetch_token(
                f"{self._authority()}/oauth2/v2.0/token",
                code=code,
                code_verifier=verifier,
                grant_type="authorization_code",
            )
        except httpx.HTTPError as failure:
            logger.warning("Entra token exchange failed: %s", type(failure).__name__)
            raise LoginError("provider_unavailable") from failure
        except Exception as rejection:
            logger.warning("Entra rejected the authorization code: %s", type(rejection).__name__)
            raise LoginError("provider_error") from rejection
        if not token.get("id_token"):
            logger.warning("Entra returned a token response without id_token")
            raise LoginError("provider_error")
        return token

    def _validated_claims(self, client: OAuth2Client, token: dict, *, nonce: str) -> dict:
        settings = get_settings()
        discovery = self._cached(client, f"{self._authority()}/v2.0/.well-known/openid-configuration")
        issuer, jwks_uri = discovery.get("issuer"), discovery.get("jwks_uri")
        if not (_in_tenant(issuer, settings.auth_entra_tenant_id) and _in_tenant(
            jwks_uri, settings.auth_entra_tenant_id
        )):
            logger.warning("Entra discovery document points outside the tenant")
            raise LoginError("provider_error")

        try:
            try:
                decoded = jwt.decode(
                    token["id_token"], self._keys(client, jwks_uri), algorithms=["RS256"]
                )
            except InvalidKeyIdError:
                # Rotation des clés : un seul rafraîchissement, jamais une boucle.
                decoded = jwt.decode(
                    token["id_token"],
                    self._keys(client, jwks_uri, refresh=True),
                    algorithms=["RS256"],
                )
            CodeIDToken(
                decoded.claims,
                decoded.header,
                {
                    "iss": {"essential": True, "value": issuer},
                    # Sans valeur attendue, l'audience n'est pas vérifiée.
                    "aud": {"essential": True, "value": settings.auth_entra_client_id},
                },
                {
                    "nonce": nonce,
                    "client_id": settings.auth_entra_client_id,
                    "access_token": token.get("access_token"),
                },
            ).validate(leeway=LEEWAY_SECONDS)
        except (JoseError, ValueError) as invalid:
            logger.warning("Entra id_token rejected: %s", type(invalid).__name__)
            raise LoginError("provider_error") from invalid
        # `sub` est propre à chaque inscription d'application : la recréer
        # rendrait orphelins tous les comptes. `oid` est stable dans le tenant.
        if not isinstance(decoded.claims.get("oid"), str) or not decoded.claims["oid"]:
            logger.warning("Entra id_token carries no oid")
            raise LoginError("provider_error")
        return decoded.claims

    def _keys(self, client: OAuth2Client, jwks_uri: str, *, refresh: bool = False) -> KeySet:
        jwks = self._cached(client, jwks_uri, refresh=refresh)
        try:
            return KeySet.import_key_set(jwks)
        except (JoseError, ValueError, TypeError, KeyError) as unreadable:
            logger.warning("Entra JWKS is unreadable: %s", type(unreadable).__name__)
            raise LoginError("provider_error") from unreadable

    def _cached(self, client: OAuth2Client, url: str, *, refresh: bool = False) -> dict:
        """Document JSON public (découverte, JWKS), gardé une heure en mémoire."""
        hit = self._cache.get(url)
        if hit and not refresh and hit[0] > time.monotonic():
            return hit[1]
        try:
            response = client.get(url)
            response.raise_for_status()
            document = response.json()
        except httpx.HTTPError as failure:
            logger.warning("Entra metadata request failed: %s", type(failure).__name__)
            raise LoginError("provider_unavailable") from failure
        except ValueError as unreadable:
            logger.warning("Entra returned a non-JSON metadata payload")
            raise LoginError("provider_error") from unreadable
        if not isinstance(document, dict):
            raise LoginError("provider_error")
        self._cache[url] = (time.monotonic() + CACHE_TTL_SECONDS, document)
        return document


def _in_tenant(url: object, tenant_id: str) -> bool:
    """Défense en profondeur sur la découverte : hôte `*.ciamlogin.com` et
    identifiant du tenant dans l'URL. L'hôte exact de l'émetteur varie selon les
    tenants (sous-domaine ou identifiant), d'où un suffixe plutôt qu'une égalité."""
    if not isinstance(url, str) or not url:
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and host.endswith(".ciamlogin.com")
        and tenant_id.lower() in url.lower()
    )
