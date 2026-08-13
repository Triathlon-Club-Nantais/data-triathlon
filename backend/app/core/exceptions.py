"""
Exceptions domaine et handlers FastAPI associés.

Les services lèvent ces exceptions métier ; les handlers les convertissent en
réponses HTTP JSON cohérentes. Les routers n'ont plus à manipuler `HTTPException`
pour les cas métier.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Base de toutes les erreurs métier."""

    status_code: int = 400
    message: str = "Erreur"

    def __init__(self, message: str | None = None, *, headers: dict[str, str] | None = None):
        if message:
            self.message = message
        # Une erreur peut devoir porter des en-têtes de réponse : le 401 de
        # `/auth/me` doit rester `no-store`, et il sort d'ici, pas du endpoint —
        # donc hors de portée de la dépendance de router qui les pose (#114).
        self.headers = headers or {}
        super().__init__(self.message)


class InvalidUrlError(DomainError):
    status_code = 400
    message = "URL invalide"


class ProviderNotSupportedError(DomainError):
    status_code = 422
    message = "Fournisseur de chronométrage non supporté"


class ScraperError(DomainError):
    status_code = 422
    message = "Erreur lors du scraping"


class BlockedTargetError(DomainError):
    """Destination réseau refusée par le garde de `core/http` (SSRF, #101).

    Ne dérive **pas** de `ValueError` : `import_service._scrape_all` attrape
    `ValueError` pour dire « fournisseur non supporté », et une destination
    refusée s'y afficherait comme un problème de fournisseur. Elle tombe donc
    dans le `except Exception` qui suit, et ressort en `ScraperError` avec sa
    cause — visible dans le détail des épreuves en erreur des bilans CLI.
    """

    status_code = 422
    message = "Destination réseau refusée"


class AuthUnavailableError(DomainError):
    """L'authentification n'est pas configurée sur cette installation (#114).

    503 et non 500 : ce n'est pas une panne, c'est une absence de configuration
    — un déploiement sans secrets OAuth est un état légitime, où le site public
    reste intégralement fonctionnel (FR-036).
    """

    status_code = 503
    message = "L'authentification n'est pas configurée sur ce site."


class TooManyRequestsError(DomainError):
    """Limitation de débit dépassée (#267, FR-011)."""

    status_code = 429
    message = "Trop de signalements envoyés récemment, réessayez plus tard."


class NotFoundError(DomainError):
    status_code = 404
    message = "Ressource introuvable"


class DuplicateError(DomainError):
    status_code = 409
    message = "Cette ressource existe déjà"


def register_exception_handlers(app: FastAPI) -> None:
    """Branche les handlers d'exceptions domaine sur l'application FastAPI."""

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
            headers=exc.headers or None,
        )
