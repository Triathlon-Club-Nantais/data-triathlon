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


class MultipleMatchesError(DomainError):
    """Plusieurs athlètes correspondent — l'appelant doit choisir un dossard."""

    status_code = 300  # Multiple Choices

    def __init__(self, candidates: list[dict]):
        self.candidates = candidates
        super().__init__(f"{len(candidates)} athlètes trouvés")


class NotFoundError(DomainError):
    status_code = 404
    message = "Ressource introuvable"


class DuplicateError(DomainError):
    status_code = 409
    message = "Cette ressource existe déjà"


def register_exception_handlers(app: FastAPI) -> None:
    """Branche les handlers d'exceptions domaine sur l'application FastAPI."""

    @app.exception_handler(MultipleMatchesError)
    async def _multiple_matches(request: Request, exc: MultipleMatchesError):
        return JSONResponse(
            status_code=200,
            content={"multiple_matches": True, "candidates": exc.candidates},
        )

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )
