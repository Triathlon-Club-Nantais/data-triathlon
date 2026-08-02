"""Fournisseur d'identité GitHub, sur `authlib.integrations.httpx_client`.

Ce client **hérite de `httpx.Client`** : ses `**kwargs` descendent au constructeur
httpx, donc `transport=` s'y applique et l'intégralité du trafic OAuth traverse
le contrôle de destination du projet (#101, FR-039). C'est la raison — mesurée au
sondage du 2026-08-01 — pour laquelle Authlib a été retenu contre `fastapi-sso`
(client non injectable, flux GitHub livré sans PKCE ni validation d'état) et
`httpx-oauth` (dont le client GitHub court-circuite la fabrique sur deux
méthodes).
"""
import logging
import secrets
from collections.abc import Callable, Mapping

import httpx
from authlib.integrations.httpx_client import OAuth2Client

from app.core import http
from app.core.config import get_settings
from app.services.auth.errors import LoginError
from app.services.auth.idp.base import AuthorizationRequest, ExternalIdentity

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_URL = "https://api.github.com/user"
EMAILS_URL = "https://api.github.com/user/emails"

#: `read:user` pour l'identité, `user:email` pour le repli sur les adresses —
#: GitHub masque l'adresse publique par défaut, c'est le cas majoritaire.
SCOPE = "read:user user:email"

TIMEOUT = httpx.Timeout(10.0)


class GithubIdentityProvider:
    """Parcours OAuth 2.0 + PKCE chez GitHub."""

    slug = "github"
    label = "GitHub"

    def __init__(
        self, transport_factory: Callable[[], httpx.BaseTransport] | None = None
    ) -> None:
        # Une **fabrique**, pas un transport : le registre tient un singleton de
        # module, et un transport construit ici serait un pool de connexions à
        # l'échelle du processus. Les tests y injectent un `MockTransport`.
        self._transport_factory = transport_factory or http.guarded_transport

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.auth_github_client_id and settings.auth_github_client_secret)

    def _client(self) -> OAuth2Client:
        settings = get_settings()
        return OAuth2Client(
            client_id=settings.auth_github_client_id,
            client_secret=settings.auth_github_client_secret,
            scope=SCOPE,
            redirect_uri=f"{settings.auth_redirect_base_url}/api/v1/auth/{self.slug}/callback",
            # Sans ce paramètre, `create_authorization_url` ignore
            # **silencieusement** le `code_verifier` et n'émet aucun
            # `code_challenge` (mesuré : l'appel ne lève pas).
            code_challenge_method="S256",
            # httpx réémet le corps de la requête sur une redirection 307/308, et
            # ce corps porte le `client_secret`.
            follow_redirects=False,
            timeout=TIMEOUT,
            transport=self._transport_factory(),
        )

    def authorize(self, *, state: str) -> AuthorizationRequest:
        """Prépare le départ. Aucune sortie réseau — c'est ce qui rend
        `GET /auth/{provider}/authorize` quasi gratuit pour un anonyme."""
        verifier = secrets.token_urlsafe(48)
        with self._client() as client:
            url, _ = client.create_authorization_url(
                AUTHORIZE_URL, state=state, code_verifier=verifier
            )
        return AuthorizationRequest(url=url, round_trip={"verifier": verifier})

    def fetch_identity(
        self, *, code: str, round_trip: Mapping[str, str]
    ) -> ExternalIdentity:
        """Échange le code puis lit l'identité — **au plus deux** allers-retours."""
        with self._client() as client:
            self._fetch_token(client, code=code, verifier=round_trip.get("verifier", ""))
            profil = self._get_json(client, USER_URL)
            subject = profil.get("id")
            if subject is None:
                # Réponse 200 mais inexploitable : sans `id`, il n'y a pas
                # d'identité — et surtout pas de clé de résolution.
                logger.warning("GitHub returned a profile without an id")
                raise LoginError("provider_error")

            # La certification vient **toujours** de `/user/emails`, jamais de
            # la présence du champ `email` sur `/user` : GitHub publie l'adresse
            # de profil même lorsqu'elle n'a pas été confirmée. L'inférer
            # laissait quelqu'un enregistrer un compte portant l'adresse d'un
            # contributeur autorisé, sans jamais la confirmer, et obtenir une
            # session (FR-005).
            #
            # Le prix est un troisième aller-retour, là où le plan en visait deux
            # au plus. C'est un objectif de performance, pas un contrat public,
            # et il ne pèse rien face à une certification devinée.
            email, verified = self._certified_email(client)
            if not email:
                email = (profil.get("email") or "").strip()

            return ExternalIdentity(
                provider=self.slug,
                subject=str(subject),
                email=email,
                email_verified=verified,
                display_name=profil.get("login") or profil.get("name") or "",
            )

    def _fetch_token(self, client: OAuth2Client, *, code: str, verifier: str) -> None:
        try:
            client.fetch_token(
                TOKEN_URL,
                code=code,
                code_verifier=verifier,
                grant_type="authorization_code",
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as panne:
            # Une redirection 307 non suivie ressort ici : `follow_redirects=False`
            # laisse Authlib échouer sur une réponse sans jeton plutôt que de
            # réémettre le `client_secret` vers la cible du `Location`.
            logger.warning("GitHub token exchange failed: %s", type(panne).__name__)
            raise LoginError("provider_unavailable") from panne
        except Exception as refus:
            logger.warning("GitHub rejected the authorization code: %s", type(refus).__name__)
            raise LoginError("provider_error") from refus

    def _get_json(self, client: OAuth2Client, url: str):
        try:
            reponse = client.get(url, headers={"Accept": "application/vnd.github+json"})
            reponse.raise_for_status()
            return reponse.json()
        except httpx.HTTPError as panne:
            logger.warning("GitHub request failed: %s", type(panne).__name__)
            raise LoginError("provider_unavailable") from panne
        except ValueError as illisible:
            logger.warning("GitHub returned a non-JSON payload")
            raise LoginError("provider_error") from illisible

    def _certified_email(self, client: OAuth2Client) -> tuple[str, bool]:
        """Adresse **certifiée** par le fournisseur, lue sur `/user/emails`.

        Le champ qui décide est `verified`, **jamais** `primary` seul : une
        adresse primaire non vérifiée ne certifie rien (FR-005). À défaut
        d'adresse primaire vérifiée, on prend la première vérifiée — et si
        aucune ne l'est, on rend ce que le fournisseur donne, non certifié, pour
        que le refus soit prononcé par la politique et non ici.
        """
        adresses = self._get_json(client, EMAILS_URL)
        if not isinstance(adresses, list):
            raise LoginError("provider_error")

        verifiees = [a for a in adresses if isinstance(a, dict) and a.get("verified")]
        for candidate in verifiees:
            if candidate.get("primary"):
                return str(candidate.get("email") or ""), True
        if verifiees:
            return str(verifiees[0].get("email") or ""), True

        premiere = adresses[0] if adresses and isinstance(adresses[0], dict) else {}
        return str(premiere.get("email") or ""), False
