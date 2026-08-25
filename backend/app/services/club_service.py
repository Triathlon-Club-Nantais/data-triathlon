"""Synthèse club : roster et podiums calculés côté serveur (#581).

Le bucketing par mode de rang reprend la sémantique déjà posée par
`stats_service._rank_counters` (#376) et, avant elle, par
`frontend/lib/utils/club-aggregate.ts` (`bestRank`/`listPodiums`) : « all »
retient le meilleur des trois rangs, départagé overall > gender > category
à égalité.
"""
from sqlalchemy.orm import Session

from app.repositories import athlete_repository, participation_repository
from app.schemas.club import ClubPodiumEntry, ClubPodiums, ClubRosterEntry, ClubSummary

_SCOPES = ("overall", "gender", "category")


def _meilleur(rangs: dict[str, int | None]) -> tuple[str, int] | None:
    valides = [(s, r) for s, r in rangs.items() if r is not None and 1 <= r <= 3]
    if not valides:
        return None
    return min(valides, key=lambda item: (item[1], _SCOPES.index(item[0])))


def _entree(row, scope: str, rang: int) -> ClubPodiumEntry:
    (pid, _rank_overall, _rank_gender, _rank_category, total_time,
     athlete_id, prenom, nom, event_name, event_type, is_relay, event_date) = row
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
        _, rank_overall, rank_gender, rank_category, *_ = row
        if rank_overall is not None and 1 <= rank_overall <= 3:
            buckets["scratch"].append(_entree(row, "overall", rank_overall))
        if rank_category is not None and 1 <= rank_category <= 3:
            buckets["category"].append(_entree(row, "category", rank_category))
        if rank_gender is not None and 1 <= rank_gender <= 3:
            buckets["gender"].append(_entree(row, "gender", rank_gender))
        meilleur = _meilleur(
            {"overall": rank_overall, "gender": rank_gender, "category": rank_category}
        )
        if meilleur:
            scope, rang = meilleur
            buckets["all"].append(_entree(row, scope, rang))
    return ClubPodiums(**{k: _trier(v) for k, v in buckets.items()})


def get_club_summary(db: Session, *, federal_only: bool = False) -> ClubSummary:
    """Roster (top 12) et podiums (4 modes de rang) du club, agrégés côté serveur."""
    roster_rows = athlete_repository.club_roster(db, federal_only=federal_only)
    podium_rows = participation_repository.club_podiums(db, federal_only=federal_only)
    roster = [
        ClubRosterEntry(
            athlete_id=a.id, prenom=a.prenom, nom=a.nom,
            count=count, podiums=podiums,
            podiums_overall=po, podiums_gender=pg, podiums_category=pc,
        )
        for a, count, podiums, po, pg, pc in roster_rows
    ]
    return ClubSummary(roster=roster, podiums=_bucket_podiums(podium_rows))
