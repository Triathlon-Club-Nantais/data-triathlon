from dataclasses import dataclass, field
from datetime import date
from typing import Any

# Statuts sportifs d'une participation. Centralisés ici (couche la plus basse,
# importée par les scrapers ET par services/mapping) pour éviter les chaînes
# magiques disséminées.
STATUS_FINISHER = "finisher"
STATUS_DNF = "DNF"  # abandon (Did Not Finish)
STATUS_DNS = "DNS"  # non-partant (Did Not Start)
STATUS_DSQ = "DSQ"  # disqualifié


@dataclass
class ScrapedResult:
    source_url: str
    provider: str
    athlete_name: str = ""
    athlete_firstname: str = ""
    club: str = ""
    category: str = ""
    gender: str = ""
    bib_number: str = ""
    event_name: str = ""
    event_date: date | None = None
    event_type: str = ""
    rank_overall: int | None = None
    rank_category: int | None = None
    rank_gender: int | None = None
    total_time: str = ""
    # Slots positionnels génériques (5 max), ré-étiquetés par sport dans
    # `services/mapping.build_splits` (ex. duathlon → course1/course2). Le nommage
    # triathlon est conventionnel, pas une contrainte de sport.
    swim_time: str = ""
    t1_time: str = ""
    bike_time: str = ""
    t2_time: str = ""
    run_time: str = ""
    # Chemin générique optionnel : liste ordonnée de segments (label, temps). Si
    # renseigné, il prime sur les 5 slots positionnels et lève leur plafond de 5
    # (ex. swimrun multi-legs, étiquettes arbitraires).
    segments: list[tuple[str, str]] | None = None
    # Kilométrage de l'épreuve si connu/extrait. Sinon mapping l'extrait du nom.
    distance_km: float | None = None
    is_relay: bool = False
    # "" = le scraper ne se prononce pas → l'infra retombe sur l'heuristique.
    # Un scraper qui sait (prolivesport) le renseigne explicitement.
    status: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class FanoutTrace:
    """Compteurs de fan-out remontés par un scraper à sous-unités (#156, #195).

    **Une seule définition**, ici : quatre modules la redéclaraient à l'identique
    (klikego, wiclax, chronoplace, chronoweb) pendant que trois autres — oktime,
    sporthive, raceresult — empruntaient celle de klikego. Le contrat était donc
    partagé sans domicile, jusque dans `import_service`, annoté
    `registry.klikego.FanoutTrace`. Cinq champs, un seul endroit où les changer.

    Le vocabulaire « heat » est conventionnel : la sous-unité est un heat chez
    Klikego (`?heat=`), un parcours chez Wiclax (attribut `p` du `.clax`), une
    épreuve chez Chronoplace, un contest chez RaceResult, une race chez Chronoweb
    et Sporthive, une course chez ok-time. Le patron, lui, est le même partout.

    `heats_imported` est **laissé à 0 côté scraper** : `import_service` le dérive
    via l'invariant `enumerated = imported + cached + len(failures)`.

    `cached_urls` liste les sous-unités sautées parce que jugées fraîches par
    `cache_probe`. `import_service` les résout en `Course` déjà en base pour
    étoffer le sélecteur de fin d'import : sans elles, un ré-import sur un
    événement partiellement caché n'exposerait dans le `done` que les courses
    re-scrapées, et l'opérateur perdrait l'accès aux sous-unités déjà en cache.
    """
    heats_enumerated: int = 0
    heats_cached: int = 0
    heats_imported: int = 0
    failures: list[dict] = field(default_factory=list)
    cached_urls: list[str] = field(default_factory=list)
