"""
Indice de fiabilité d'une course, calculé à l'import.

La base est alimentée par scraping : rien ne garantit que les résultats d'une
course soient complets ni cohérents. Après persistance, on confronte les
participations en base aux lignes réellement scrapées et on relève les anomalies
listées ci-dessous. Le rapport est stocké sur `Course` (`is_reliable` +
`quality_issues`) pour repérer les courses à revalider — l'admin sait alors
*pourquoi* une course est suspecte, et pas seulement *qu'elle* l'est.

Une course est fiable si, et seulement si, aucune anomalie n'est relevée : c'est
un signal de revue humaine, pas une note. Tout seuil de tolérance serait arbitraire.
"""
from collections.abc import Iterable
from dataclasses import dataclass

from app.scrapers.base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, STATUS_FINISHER

# Lignes scrapées jetées : deux lignes de la source partagent un dossard, la
# seconde n'atteint jamais la base (cf. `import_service._Persister.add`).
ANOMALY_DUPLICATE_BIB = "duplicate_bib"
# Statut hors nomenclature (« DQ », « OTL », « Abandon »…) : atterrit dans les
# indéterminés côté front.
ANOMALY_UNKNOWN_STATUS = "unknown_status"
# Deux finishers partagent un `rank_overall`.
ANOMALY_DUPLICATE_RANK = "duplicate_rank"
# Trous dans le classement des finishers (rangs non contigus depuis 1).
ANOMALY_RANK_GAP = "rank_gap"
# Finisher dont le temps total est vide ou nul.
ANOMALY_FINISHER_WITHOUT_TIME = "finisher_without_time"
# Course importée sans aucune participation.
ANOMALY_NO_PARTICIPATION = "no_participation"

KNOWN_STATUSES = frozenset(
    s.lower() for s in (STATUS_FINISHER, STATUS_DNF, STATUS_DNS, STATUS_DSQ)
)

# Un temps total « zéro » vaut temps absent : les chronos le rendent de plusieurs façons.
_ZERO_TIMES = frozenset({"", "00:00:00", "0:00:00", "00:00", "0:00", "0"})


@dataclass(frozen=True)
class QualityReport:
    is_reliable: bool
    anomalies: dict[str, int]


def _normalized_status(participation) -> str:
    return (participation.status or "").strip().lower()


def _has_no_time(participation) -> bool:
    return (participation.total_time or "").strip() in _ZERO_TIMES


def _rank_anomalies(finishers: list) -> dict[str, int]:
    """Doublons et trous dans le classement des finishers.

    Solos et relais sont classés séparément (TimePulse mélange les deux dans une
    même course) : deux « rang 1 » n'y sont pas un doublon.
    """
    anomalies: dict[str, int] = {}
    for is_relay in (False, True):
        ranks = [
            p.rank_overall
            for p in finishers
            if bool(p.is_relay) is is_relay and p.rank_overall
        ]
        if not ranks:
            continue
        distinct = set(ranks)
        duplicates = len(ranks) - len(distinct)
        # Un classement sain va de 1 à N sans trou : `max` borne le nombre attendu.
        gaps = max(distinct) - len(distinct)
        if duplicates:
            anomalies[ANOMALY_DUPLICATE_RANK] = anomalies.get(ANOMALY_DUPLICATE_RANK, 0) + duplicates
        if gaps:
            anomalies[ANOMALY_RANK_GAP] = anomalies.get(ANOMALY_RANK_GAP, 0) + gaps
    return anomalies


def analyze(participations: Iterable, *, duplicate_bibs: int = 0) -> QualityReport:
    """Rapport de fiabilité d'une course.

    `participations` = celles réellement persistées ; `duplicate_bibs` = les lignes
    scrapées jetées faute de dossard unique, connues du seul `import_service`.
    """
    participations = list(participations)
    anomalies: dict[str, int] = {}

    if duplicate_bibs:
        anomalies[ANOMALY_DUPLICATE_BIB] = duplicate_bibs

    if not participations:
        anomalies[ANOMALY_NO_PARTICIPATION] = 1
        return QualityReport(is_reliable=False, anomalies=anomalies)

    unknown = sum(1 for p in participations if _normalized_status(p) not in KNOWN_STATUSES)
    if unknown:
        anomalies[ANOMALY_UNKNOWN_STATUS] = unknown

    finishers = [p for p in participations if _normalized_status(p) == STATUS_FINISHER]
    without_time = sum(1 for p in finishers if _has_no_time(p))
    if without_time:
        anomalies[ANOMALY_FINISHER_WITHOUT_TIME] = without_time

    anomalies.update(_rank_anomalies(finishers))

    return QualityReport(is_reliable=not anomalies, anomalies=anomalies)
