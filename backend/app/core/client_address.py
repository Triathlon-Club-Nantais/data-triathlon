"""Adresse du client derrière Vercel, Cloudflare et Render (#1533).

`request.client.host` est la clé de tous les plafonds par IP (`api/deps.py`,
`POST /feedback`) : ce middleware décide quelle adresse y entre, et un appelant
ne doit pas pouvoir la choisir.

Mesuré sur la preview le 16/10/2026, `X-Forwarded-For` arrive sous la forme
`<ce qu'a écrit l'appelant>, <IP vue par Cloudflare>, <bord Cloudflare>,
<saut interne Render>`. Chaque proxy **ajoute** à droite : seules les
`trusted_proxy_count` dernières entrées sont posées par la plateforme, et la
plus à gauche d'entre elles est l'adresse qui s'est connectée à Cloudflare.
Tout ce qui précède vient de l'appelant, y compris à travers le rewrite Vercel,
qui transmet l'en-tête reçu sans le réécrire.

Par le rewrite `/api/*` du front, cette adresse est celle de sortie de Vercel,
qui change d'une requête à l'autre. L'IP du visiteur n'y est fiable que dans
`X-Vercel-Forwarded-For`, que Vercel écrase, et seulement si la requête vient
bien de Vercel : un appel direct peut poser cet en-tête. `frontend/proxy.ts`
le prouve par un secret partagé (`FRONTEND_PROXY_SECRET`). **Sans ce secret,
les plafonds ne tiennent pas par le front** : chaque appel y tombe dans le seau
d'une IP de sortie Vercel tirée d'un pool (mesuré : 31 appels, aucun 429), d'où
l'avertissement au démarrage.
"""
import hmac
import ipaddress
import logging

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

SECRET_HEADER = b"x-frontend-proxy-secret"


def _header(scope: Scope, name: bytes) -> list[str]:
    return [value.decode("latin1") for key, value in scope["headers"] if key == name]


def _ip(value: str) -> str | None:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


class ClientAddressMiddleware:
    def __init__(self, app: ASGIApp, *, settings) -> None:
        # L'objet et non ses valeurs : lu à chaque requête, comme les plafonds.
        self.app = app
        self.settings = settings
        if settings.trusted_proxy_count > 0 and not settings.frontend_proxy_secret:
            logger.warning(
                "FRONTEND_PROXY_SECRET is unset: per-IP rate limits do not hold "
                "for requests through the Vercel rewrite (#1533)"
            )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            proto = ",".join(_header(scope, b"x-forwarded-proto")).split(",")[-1].strip()
            if proto in ("http", "https"):
                scope["scheme"] = proto if scope["type"] == "http" else proto.replace("http", "ws")
            host = self._client_host(scope)
            if host:
                scope["client"] = (host, 0)
        await self.app(scope, receive, send)

    def _client_host(self, scope: Scope) -> str | None:
        secret = self.settings.frontend_proxy_secret
        sent = _header(scope, SECRET_HEADER)
        if secret and len(sent) == 1 and hmac.compare_digest(sent[0].encode(), secret.encode()):
            vercel = _header(scope, b"x-vercel-forwarded-for")
            if len(vercel) == 1 and (host := _ip(vercel[0])):
                return host

        count = self.settings.trusted_proxy_count
        chain = [entry for line in _header(scope, b"x-forwarded-for") for entry in line.split(",")]
        if count <= 0 or len(chain) < count:
            return None
        host = _ip(chain[-count])
        # Sur les deux chemins mesurés, l'entrée retenue est le pair de
        # Cloudflare : un écart signale un saut ajouté ou retiré par la plateforme.
        cloudflare = _header(scope, b"cf-connecting-ip")
        if len(cloudflare) == 1 and _ip(cloudflare[0]) != host:
            # Sans valeur de `settings` dans le message : CodeQL tient tout
            # l'objet pour secret, à cause de `frontend_proxy_secret`.
            logger.warning(
                "X-Forwarded-For entry %s differs from CF-Connecting-IP %s: "
                "re-measure TRUSTED_PROXY_COUNT (#1533)",
                host,
                cloudflare[0],
            )
        return host
