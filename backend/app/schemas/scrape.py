"""Schémas Pydantic pour le scraping (requête d'import + résultat)."""
from pydantic import BaseModel, HttpUrl


class ScrapeRequest(BaseModel):
    #: `HttpUrl` et non `str` : rejette `file://`, `gopher://`, `javascript:` et
    #: les URLs sans host dès la porte de l'API, en 422 (#49). Mais `HttpUrl`
    #: normalise, il ne se contente pas de valider — mesuré sur pydantic
    #: 2.13.4 : port par défaut supprimé (`:443` disparaît), espaces et
    #: caractères non-ASCII percent-encodés dans le chemin, et une limite de
    #: 2083 caractères (422 au-delà, `url_too_long`). `my.raceresult.com:443`
    #: (cf. `_ROUTAGE_LEGITIME` dans `test_registry.py`) est donc bien réécrite.
    #: Conséquence réelle, bornée : `course_repository.get_or_create` apparie
    #: par identité (`name`, `event_date`, `event_type`, `is_relay`), donc
    #: **aucun doublon de course n'est créé** ; mais `get_latest_by_source_url`
    #: rate sur ces URLs et, `get_or_create` ne réécrivant pas le `source_url`
    #: d'une ligne existante, le cache TTL reste durablement inefficace pour
    #: elles (re-scrape à chaque import, jamais de doublon).
    #: Il ne dispense pas de `import_service._validate_url`, qui couvre la CLI.
    url: HttpUrl


class ImportedCourse(BaseModel):
    """Course touchée par un import — sert à câbler « Voir les résultats » (#135).

    `is_relay` sert au sélecteur de fin d'import à distinguer deux Course de
    même nom et même discipline qui ne différeraient que par le drapeau relais
    (issue #195/#203 : Chronoplace publie parfois indiv + relais dans la même
    sous-unité, Klikego les publie sur deux heats homonymes).
    """
    id: int
    name: str
    event_type: str
    is_relay: bool = False


class ImportResult(BaseModel):
    imported: int
    updated: int = 0
    skipped: int
    cached: bool = False
    #: Épreuve unique = 1 entrée. Multi (heats Klikego, listes RaceResult,
    #: événements Chronoplace) : autant d'entrées que de `Course` touchées.
    courses: list[ImportedCourse] = []
