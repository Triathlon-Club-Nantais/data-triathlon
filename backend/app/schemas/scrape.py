"""Schémas Pydantic pour le scraping (requête d'import + résultat)."""
from pydantic import BaseModel, HttpUrl


class ScrapeRequest(BaseModel):
    #: `HttpUrl` et non `str` : rejette `file://`, `gopher://`, `javascript:` et
    #: les URLs sans host dès la porte de l'API, en 422 (#49). Mesuré sur nos
    #: URLs de chronométrage : il ne réécrit que le host en minuscules et
    #: n'ajoute un `/` final qu'à un domaine nu — aucune n'est dans ce cas, la
    #: clé de cache `source_url` ne dérive pas.
    #: Il ne dispense pas de `import_service._validate_url`, qui couvre la CLI.
    url: HttpUrl


class ImportResult(BaseModel):
    imported: int
    updated: int = 0
    skipped: int
    cached: bool = False
