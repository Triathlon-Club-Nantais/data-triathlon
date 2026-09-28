"""Refus des écritures venues d'un autre site que l'interface (#946).

`SameSite=Lax` ne protège que du **cross-site** : une page servie par l'apex
`triathlon-club-nantais.com` (site vitrine sur un mutualisé hors de notre
contrôle) ou par un autre sous-domaine est du même site, et porte les cookies de
session sur un `<form>` ou un `fetch` en `no-cors`, sans preflight CORS.

Règle, pour `POST`/`PUT`/`PATCH`/`DELETE` :

- `Sec-Fetch-Site`, quand le navigateur l'envoie, tranche seul : `same-origin` et
  `none` (adresse tapée) passent, `same-site` et `cross-site` sont refusés. Un
  appel légitime passe par le rewrite `/api/*` du front : il est same-origin.
- Sinon, un `Origin` présent doit être celui de l'interface ou une origine CORS.
- Sans aucun des deux (serveur à serveur, CLI, tests), la requête passe.
"""
import json

from starlette.types import ASGIApp, Receive, Scope, Send

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_ALLOWED_FETCH_SITES = frozenset({"same-origin", "none"})
_BODY = json.dumps(
    {"detail": "Requête refusée : son origine n'est pas l'interface du site."}
).encode()


def _origin(value: str) -> str:
    return value.strip().rstrip("/").lower()


class OriginGuardMiddleware:
    def __init__(self, app: ASGIApp, *, allowed_origins: list[str]) -> None:
        self.app = app
        self.allowed = {_origin(o) for o in allowed_origins if o}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in _WRITE_METHODS and not self._allowed(scope):
            await send({
                "type": "http.response.start",
                "status": 403,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({"type": "http.response.body", "body": _BODY})
            return
        await self.app(scope, receive, send)

    def _allowed(self, scope: Scope) -> bool:
        headers = {name.decode("latin-1").lower(): value.decode("latin-1") for name, value in scope["headers"]}
        fetch_site = headers.get("sec-fetch-site")
        if fetch_site:
            return fetch_site.strip().lower() in _ALLOWED_FETCH_SITES
        origin = headers.get("origin")
        return origin is None or _origin(origin) in self.allowed
