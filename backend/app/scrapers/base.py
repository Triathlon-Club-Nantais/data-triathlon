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
