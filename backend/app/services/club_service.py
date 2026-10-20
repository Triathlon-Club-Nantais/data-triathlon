"""Synthèse club : roster et podiums calculés côté serveur (#581).

Le bucketing par mode de rang reprend la sémantique déjà posée par
`stats_service._rank_counters` (#376) et, avant elle, par
`frontend/lib/utils/club-aggregate.ts` (`bestRank`/`listPodiums`) : « all »
retient le meilleur des trois rangs, départagé overall > gender > category
à égalité.
"""
import statistics
from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from app.core.gender import is_gender_podium
from app.core.season import current_season
from app.core.splits_reliability import is_stats_eligible
from app.repositories import athlete_repository, club_member_repository, participation_repository
from app.schemas.club import (
    ClubBestTime,
    ClubComposition,
    ClubLicensees,
    ClubPodiumEntry,
    ClubPodiums,
    ClubPodiumTotals,
    ClubRosterEntry,
    ClubSplitMedians,
    ClubSummary,
    DisciplinePodiumCounts,
)
from app.scrapers.utils import to_seconds
from app.services import split_gap

_SCOPES = ("overall", "gender", "category")


def _best(ranks: dict[str, int | None]) -> tuple[str, int] | None:
    valid = [(s, r) for s, r in ranks.items() if r is not None and 1 <= r <= 3]
    if not valid:
        return None
    return min(valid, key=lambda item: (item[1], _SCOPES.index(item[0])))


def _entry(row, scope: str, rank: int, teammates: dict[int, list[str]]) -> ClubPodiumEntry:
    (pid, _rank_overall, _rank_gender, _rank_category, total_time,
     athlete_id, first_name, last_name, event_name, event_type, is_relay, event_date,
     _gender) = row
    return ClubPodiumEntry(
        participation_id=pid,
        athlete_id=athlete_id,
        athlete_name=f"{first_name} {last_name}".strip(),
        event_name=event_name or "",
        event_type=event_type or "",
        is_relay=bool(is_relay),
        event_date=event_date.isoformat() if event_date else None,
        rank=rank,
        scope=scope,
        total_time=total_time,
        teammate_names=teammates.get(pid, []),
    )


def _sort_entries(entries: list[ClubPodiumEntry]) -> list[ClubPodiumEntry]:
    # Stable : trier d'abord par date décroissante, puis par rang croissant —
    # à rang égal, l'ordre par date décroissante posé au premier passage survit.
    # Départage final par id : `club_podiums` n'a pas d'ORDER BY, et l'aperçu
    # (`?podiums=preview`) doit être le début exact de la liste complète (#1354).
    by_id = sorted(entries, key=lambda e: e.participation_id)
    by_date = sorted(by_id, key=lambda e: e.event_date or "", reverse=True)
    return sorted(by_date, key=lambda e: e.rank)


def _bucket_podiums(rows, teammates: dict[int, list[str]]) -> ClubPodiums:
    buckets: dict[str, list[ClubPodiumEntry]] = {
        "scratch": [], "category": [], "gender": [], "all": [],
    }
    for row in rows:
        _, rank_overall, rank_gender, rank_category, *_, gender = row
        if rank_overall is not None and 1 <= rank_overall <= 3:
            buckets["scratch"].append(_entry(row, "overall", rank_overall, teammates))
        if rank_category is not None and 1 <= rank_category <= 3:
            buckets["category"].append(_entry(row, "category", rank_category, teammates))
        # Même règle que le KPI et le roster (`core.gender`, #581, #936).
        if is_gender_podium(rank_gender, gender):
            buckets["gender"].append(_entry(row, "gender", rank_gender, teammates))
        best = _best(
            {"overall": rank_overall, "gender": rank_gender, "category": rank_category}
        )
        if best:
            scope, rank = best
            buckets["all"].append(_entry(row, scope, rank, teammates))
    return ClubPodiums(**{k: _sort_entries(v) for k, v in buckets.items()})


def _bucket_podiums_by_discipline(rows) -> dict[str, DisciplinePodiumCounts]:
    """Décompte de podiums par discipline (#642, US10) — mêmes conditions que
    `_bucket_podiums`, mais on ne garde que les compteurs, tally par
    `event_type` plutôt qu'une liste d'entrées : `DisciplinePerformance`
    (front) n'a besoin que des totaux, jamais du détail participation par
    participation.
    """
    counters: dict[str, dict[str, int]] = defaultdict(
        lambda: {"overall": 0, "gender": 0, "category": 0, "all": 0}
    )
    for row in rows:
        (_, rank_overall, rank_gender, rank_category, *_, event_type, _is_relay,
         _event_date, gender) = row
        c = counters[event_type or ""]
        if rank_overall is not None and 1 <= rank_overall <= 3:
            c["overall"] += 1
        if rank_category is not None and 1 <= rank_category <= 3:
            c["category"] += 1
        if is_gender_podium(rank_gender, gender):
            c["gender"] += 1
        if _best({"overall": rank_overall, "gender": rank_gender, "category": rank_category}):
            c["all"] += 1
    return {discipline: DisciplinePodiumCounts(**c) for discipline, c in counters.items()}


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


#: Taille de l'aperçu des podiums, celle que `PodiumsList` affiche replié (#1354).
PODIUMS_PREVIEW = 6


def get_club_podiums(
    db: Session, *, federal_only: bool = False, seasons: list[int] | None = None, gender: str | None = None
) -> ClubPodiums:
    """Les podiums complets des quatre modes, chargés au dépliage de la liste (#1354)."""
    rows = participation_repository.club_podiums(db, federal_only=federal_only, seasons=seasons, gender=gender)
    return _bucket_podiums(rows, participation_repository.teammate_names(db, (row[0] for row in rows)))


def get_club_summary(
    db: Session,
    *,
    federal_only: bool = False,
    podiums_preview: bool = False,
    seasons: list[int] | None = None,
    gender: str | None = None,
) -> ClubSummary:
    """Roster (top 12), podiums (4 modes de rang), podiums par discipline et
    composition (genre/catégorie) du club, agrégés côté serveur.

    `podiums_preview` ne garde que les `PODIUMS_PREVIEW` premiers de chaque
    mode : la liste complète pesait 215 ko de la charge de `/club` (#1354)."""
    roster_rows = athlete_repository.club_roster(db, federal_only=federal_only, seasons=seasons, gender=gender)
    podium_rows = participation_repository.club_podiums(db, federal_only=federal_only, seasons=seasons, gender=gender)
    composition_rows = athlete_repository.club_composition(db, federal_only=federal_only, seasons=seasons, gender=gender)
    roster = [
        ClubRosterEntry(
            athlete_id=a.id, prenom=a.prenom, nom=a.nom,
            count=count, podiums=podiums,
            podiums_overall=po, podiums_gender=pg, podiums_category=pc,
        )
        for a, count, podiums, po, pg, pc in roster_rows
    ]
    podiums = _bucket_podiums(
        podium_rows,
        participation_repository.teammate_names(db, (row[0] for row in podium_rows)),
    )
    totals = ClubPodiumTotals(**{mode: len(getattr(podiums, mode)) for mode in ClubPodiumTotals.model_fields})
    if podiums_preview:
        podiums = ClubPodiums(
            **{mode: getattr(podiums, mode)[:PODIUMS_PREVIEW] for mode in ClubPodiumTotals.model_fields}
        )
    season = max(seasons) if seasons else current_season()
    activity = club_member_repository.licensee_activity(db, season, gender)
    return ClubSummary(
        roster=roster,
        podiums=podiums,
        podiums_totals=totals,
        podiums_by_discipline=_bucket_podiums_by_discipline(podium_rows),
        composition=_bucket_composition(composition_rows),
        licensees=ClubLicensees(season=season, total=activity[0], raced=activity[1]) if activity else None,
    )


_GENDER_ORDER = ("F", "M")


def get_club_best_times(
    db: Session, *, season: int | None = None, federal_only: bool = False
) -> list[ClubBestTime]:
    """Meilleur temps du club par format calibré et par genre (#1588), toutes
    saisons sans `season`. À temps égal, la première épreuve courue garde la ligne."""
    best = {}
    for row in participation_repository.club_best_time_rows(db, season=season, federal_only=federal_only):
        seconds = to_seconds(row.total_time, strict=True)
        if not seconds:
            continue
        key = (row.event_type, row.gender)
        order = (seconds, row.event_date or date.max, row.participation_id)
        if key not in best or order < best[key][0]:
            best[key] = (order, row)

    def position(row):
        discipline, size = row.event_type.rsplit("-", 1)
        return discipline, participation_repository.SIZES.index(size), _GENDER_ORDER.index(row.gender)

    return [
        ClubBestTime(
            participation_id=row.participation_id,
            course_id=row.course_id,
            athlete_id=row.athlete_id,
            athlete_name=f"{row.prenom} {row.nom}".strip(),
            event_name=row.event_name or "",
            event_type=row.event_type,
            event_date=row.event_date.isoformat() if row.event_date else None,
            gender=row.gender,
            total_time=row.total_time,
        )
        for row in sorted((row for _, row in best.values()), key=position)
    ]


def get_club_split_medians(
    db: Session, *, event_type: str, federal_only: bool = False, seasons: list[int] | None = None
) -> ClubSplitMedians:
    """Médiane club des temps de natation, vélo et course d'un format (#1699).

    Ne retient que les lignes dont les splits sont fiables et évaluables, hors lignes
    aberrantes face à la médiane d'écart de leur épreuve. `sample` compte ces lignes.
    La médiane d'écart de référence porte sur toutes les lignes de l'épreuve, pas sur le club seul.
    """
    rows = [
        row
        for row in participation_repository.club_split_rows(
            db, event_type=event_type, federal_only=federal_only, seasons=seasons
        )
        if is_stats_eligible(row.course)
    ]
    gaps = {
        row.id: split_gap.gap(row.total_time, row.splits, event_type=event_type, is_relay=False) for row in rows
    }
    by_course = defaultdict(list)
    for course_id, total_time, splits in participation_repository.course_split_gap_rows(
        db, sorted({row.course_id for row in rows})
    ):
        by_course[course_id].append(split_gap.gap(total_time, splits, event_type=event_type, is_relay=False))
    values = {key: [] for key in ("swim", "bike", "run")}
    sample = 0
    for row in rows:
        gap = gaps[row.id]
        if gap is None:
            continue
        course_gaps = by_course[row.course_id]
        if split_gap.is_outlier(
            gap,
            median=split_gap.median(course_gaps),
            evaluated_rows=sum(1 for value in course_gaps if value is not None),
            total_seconds=to_seconds(row.total_time, strict=True),
        ):
            continue
        sample += 1
        for key, seconds in values.items():
            seconds.append(to_seconds(row.splits.get(key), strict=True))
    medians = {key: _format_seconds(statistics.median(v)) if (v := [x for x in seconds if x]) else None
               for key, seconds in values.items()}
    return ClubSplitMedians(event_type=event_type, sample=sample, **medians)


def _format_seconds(seconds: float) -> str:
    total = round(seconds)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"
