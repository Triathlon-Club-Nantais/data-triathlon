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
le prouve par un secret partagé (`FRONTEND_PROXY_SECRET`) ; sans lui, une visite
par le front compte sous l'IP de sortie de Vercel, plus grossier mais jamais
choisi par l'appelant.
"""
import hmac
import ipaddress

from starlette.types import ASGIApp, Receive, Scope, Send

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

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            proto = "".join(_header(scope, b"x-forwarded-proto")).strip()
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
        return _ip(chain[-count])
