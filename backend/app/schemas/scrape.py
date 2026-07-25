"""Schémas Pydantic pour le scraping (requête d'import + résultat)."""
from pydantic import BaseModel


class ScrapeRequest(BaseModel):
    url: str


class ImportResult(BaseModel):
    imported: int
    updated: int = 0
    skipped: int
    cached: bool = False
