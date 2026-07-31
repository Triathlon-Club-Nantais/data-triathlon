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

    def __init__(self, message: str | None = None):
        if message:
            self.message = message
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
        )
