"""Synthèse club : roster et podiums calculés côté serveur (#581).

Le bucketing par mode de rang reprend la sémantique déjà posée par
`stats_service._rank_counters` (#376) et, avant elle, par
`frontend/lib/utils/club-aggregate.ts` (`bestRank`/`listPodiums`) : « all »
retient le meilleur des trois rangs, départagé overall > gender > category
à égalité.
"""
from collections import defaultdict

from sqlalchemy.orm import Session

from app.repositories import athlete_repository, participation_repository
from app.schemas.club import (
    ClubComposition,
    ClubPodiumEntry,
    ClubPodiums,
    ClubRosterEntry,
    ClubSummary,
    DisciplinePodiumCounts,
)

_SCOPES = ("overall", "gender", "category")


def _meilleur(rangs: dict[str, int | None]) -> tuple[str, int] | None:
    valides = [(s, r) for s, r in rangs.items() if r is not None and 1 <= r <= 3]
    if not valides:
        return None
    return min(valides, key=lambda item: (item[1], _SCOPES.index(item[0])))


def _entree(row, scope: str, rang: int) -> ClubPodiumEntry:
    (pid, _rank_overall, _rank_gender, _rank_category, total_time,
     athlete_id, prenom, nom, event_name, event_type, is_relay, event_date,
     _gender) = row
    return ClubPodiumEntry(
        participation_id=pid,
        athlete_id=athlete_id,
        athlete_name=f"{prenom} {nom}".strip(),
        event_name=event_name or "",
        event_type=event_type or "",
        is_relay=bool(is_relay),
        event_date=event_date.isoformat() if event_date else None,
        rank=rang,
        scope=scope,
        total_time=total_time,
    )


def _trier(entries: list[ClubPodiumEntry]) -> list[ClubPodiumEntry]:
    # Stable : trier d'abord par date décroissante, puis par rang croissant —
    # à rang égal, l'ordre par date décroissante posé au premier passage survit.
    par_date = sorted(entries, key=lambda e: e.event_date or "", reverse=True)
    return sorted(par_date, key=lambda e: e.rank)


def _bucket_podiums(rows) -> ClubPodiums:
    buckets: dict[str, list[ClubPodiumEntry]] = {
        "scratch": [], "category": [], "gender": [], "all": [],
    }
    for row in rows:
        _, rank_overall, rank_gender, rank_category, *_, gender = row
        if rank_overall is not None and 1 <= rank_overall <= 3:
            buckets["scratch"].append(_entree(row, "overall", rank_overall))
        if rank_category is not None and 1 <= rank_category <= 3:
            buckets["category"].append(_entree(row, "category", rank_category))
        # Miroir de stats_service._rank_counters (#376) : un podium de genre
        # n'est compté que pour un athlète F ou M, jamais genre vide/hors
        # binaire — sans quoi le KPI "Podiums" (rank_counters) et cette liste
        # divergent en mode genre (relevé en revue finale de branche, #581).
        if (
            rank_gender is not None and 1 <= rank_gender <= 3
            and (gender or "").upper() in ("F", "M")
        ):
            buckets["gender"].append(_entree(row, "gender", rank_gender))
        meilleur = _meilleur(
            {"overall": rank_overall, "gender": rank_gender, "category": rank_category}
        )
        if meilleur:
            scope, rang = meilleur
            buckets["all"].append(_entree(row, scope, rang))
    return ClubPodiums(**{k: _trier(v) for k, v in buckets.items()})


def _bucket_podiums_par_discipline(rows) -> dict[str, DisciplinePodiumCounts]:
    """Décompte de podiums par discipline (#642, US10) — mêmes conditions que
    `_bucket_podiums`, mais on ne garde que les compteurs, tally par
    `event_type` plutôt qu'une liste d'entrées : `DisciplinePerformance`
    (front) n'a besoin que des totaux, jamais du détail participation par
    participation.
    """
    compteurs: dict[str, dict[str, int]] = defaultdict(
        lambda: {"overall": 0, "gender": 0, "category": 0, "all": 0}
    )
    for row in rows:
        (_, rank_overall, rank_gender, rank_category, *_, event_type, _is_relay,
         _event_date, gender) = row
        c = compteurs[event_type or ""]
        if rank_overall is not None and 1 <= rank_overall <= 3:
            c["overall"] += 1
        if rank_category is not None and 1 <= rank_category <= 3:
            c["category"] += 1
        if (
            rank_gender is not None and 1 <= rank_gender <= 3
            and (gender or "").upper() in ("F", "M")
        ):
            c["gender"] += 1
        if _meilleur({"overall": rank_overall, "gender": rank_gender, "category": rank_category}):
            c["all"] += 1
    return {discipline: DisciplinePodiumCounts(**c) for discipline, c in compteurs.items()}


def _bucket_composition(rows: list[tuple[str, str | None]]) -> ClubComposition:
    """Répartition genre/catégorie du club entier (#642), un couple par athlète
    (`athlete_repository.club_composition`) — une clé vide couvre le genre ou
    la catégorie non renseignés, même convention que l'ancien `buildRoster`
    (front, `?? ""`)."""
    gender_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for gender, category in rows:
        gender_counts[gender or ""] = gender_counts.get(gender or "", 0) + 1
        category_counts[category or ""] = category_counts.get(category or "", 0) + 1
    return ClubComposition(gender=gender_counts, category=category_counts)


def get_club_summary(db: Session, *, federal_only: bool = False) -> ClubSummary:
    """Roster (top 12), podiums (4 modes de rang), podiums par discipline et
    composition (genre/catégorie) du club, agrégés côté serveur."""
    roster_rows = athlete_repository.club_roster(db, federal_only=federal_only)
    podium_rows = participation_repository.club_podiums(db, federal_only=federal_only)
    composition_rows = athlete_repository.club_composition(db, federal_only=federal_only)
    roster = [
        ClubRosterEntry(
            athlete_id=a.id, prenom=a.prenom, nom=a.nom,
            count=count, podiums=podiums,
            podiums_overall=po, podiums_gender=pg, podiums_category=pc,
        )
        for a, count, podiums, po, pg, pc in roster_rows
    ]
    return ClubSummary(
        roster=roster,
        podiums=_bucket_podiums(podium_rows),
        podiums_by_discipline=_bucket_podiums_par_discipline(podium_rows),
        composition=_bucket_composition(composition_rows),
    )
