"""En-têtes de sécurité posés sur toute réponse HTTP (#396, constats A05-2 et A02-1).

Middleware **ASGI pur**, comme `SqlStatsMiddleware` : il n'importe ni FastAPI ni
Starlette et ne manipule que des dicts et des callables, donc il n'introduit
aucun couplage web dans `app/core/`.

Pourquoi le poser côté API alors que le front en pose déjà : les deux backends
Render sont joignables **directement** depuis Internet (`ipAllowList: 0.0.0.0/0`
de `render.yaml`), pas seulement à travers le proxy Vercel. Ce qui n'est encadré
que dans `next.config.ts` ne couvre pas l'API.

La CSP n'est **pas** ici : Next.js et PostHog demandent un `nonce`, ce qui est le
seul point du constat A05-2 à coûter plus qu'une ligne, et il est traité à part.
"""

# Valeurs constantes, pré-encodées en octets : le protocole ASGI transporte les
# en-têtes en `bytes`, et rien ici ne dépend de la requête.
_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    # Ferme la déduction de type de contenu — un JSON d'erreur ou un fichier
    # scrapé rendu tel quel ne peut plus être requalifié en HTML par le
    # navigateur.
    (b"x-content-type-options", b"nosniff"),
    # Le référent complet porte des identifiants de ressource (`/athletes/1234`)
    # et n'a aucune raison de sortir vers une origine tierce.
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    # L'API n'a aucune page à encadrer légitimement. `/docs` en est une : #399 la
    # ferme en production, elle reste servie là où `DOCS_ENABLED` la laisse.
    (b"x-frame-options", b"DENY"),
)

# Deux ans, `includeSubDomains`, sans `preload` : la valeur du front Vercel moins
# la demande d'inscription à la liste de préchargement, qui ne s'obtient que pour
# un domaine apex — l'API vit sous un sous-domaine `onrender.com`, où la
# directive n'est que du bruit.
_HSTS: tuple[bytes, bytes] = (
    b"strict-transport-security",
    b"max-age=63072000; includeSubDomains",
)


class SecurityHeadersMiddleware:
    """Ajoute les en-têtes de sécurité à chaque réponse HTTP.

    **À monter en premier** dans `create_app()`, donc au plus près du routeur :
    `add_middleware` empile à l'envers, et HSTS se décide sur `scope["scheme"]`,
    que `ProxyHeadersMiddleware` ne réécrit depuis `X-Forwarded-Proto` qu'en
    amont. Monté en dernier, le middleware verrait `http` en production et
    n'émettrait jamais HSTS.

    Limite assumée du même arbitrage : la réponse 500 fabriquée par
    `ServerErrorMiddleware`, qui enveloppe toute la pile, ne passe pas par ici.
    Elle ne rend que `{"detail": "Internal Server Error"}` en JSON.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.extend(_HEADERS)
                # RFC 6797 §8.1 : un HSTS reçu hors transport sûr doit être
                # ignoré par le client. L'omettre en clair ne perd donc rien et
                # garde le développement local lisible.
                if scope.get("scheme") == "https":
                    headers.append(_HSTS)
            await send(message)

        await self.app(scope, receive, send_with_headers)
