"""Agrégations statistiques (club / tableau de bord)."""
from sqlalchemy.orm import Session

from app.core import season as season_module
from app.repositories import participation_repository


def _athlete_key(part) -> int:
    # Utiliser l'id DB pour éviter les collisions entre homonymes.
    return part.athlete_id


def get_stats(db: Session, club: str | None = None, seasons: list[int] | None = None) -> dict:
    """Stats agrégées : total, athlètes, épreuves, répartition par type/mois, récents."""
    parts = participation_repository.for_stats(db, club, seasons=seasons)
    if not parts:
        return {"total": 0, "athletes": 0, "events": 0, "by_type": {}, "by_month": {}, "recent": []}

    athlete_set = {p.athlete_id for p in parts}
    event_set = {p.course_id for p in parts}
    by_type: dict[str, int] = {}
    by_month: dict[str, int] = {}
    for p in parts:
        course = p.course
        if course and course.event_type:
            by_type[course.event_type] = by_type.get(course.event_type, 0) + 1
        if course and course.event_date:
            key = str(course.event_date)[:7]  # YYYY-MM
            by_month[key] = by_month.get(key, 0) + 1

    recent = sorted(
        (p for p in parts if p.created_at),
        key=lambda p: p.created_at,
        reverse=True,
    )[:20]

    return {
        "total": len(parts),
        "athletes": len(athlete_set),
        "events": len(event_set),
        "by_type": dict(sorted(by_type.items(), key=lambda x: -x[1])),
        "by_month": dict(sorted(by_month.items())),
        "recent": [
            {
                "id": p.id,
                "athlete_name": p.athlete.nom if p.athlete else "",
                "athlete_firstname": p.athlete.prenom if p.athlete else "",
                "club": p.club or "",
                "event_name": p.course.name if p.course else "",
                "event_type": p.course.event_type if p.course else "",
                "event_date": p.course.event_date.isoformat()
                if p.course and p.course.event_date
                else None,
                "total_time": p.total_time or "",
                "scraped_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in recent
        ],
    }


def list_seasons(db: Session, club: str | None = None) -> list[dict]:
    """Saisons disponibles pour le sélecteur.

    Saisons ayant ≥ 1 résultat daté + saison en cours toujours présente (à 0 si
    absente), enrichies de `label`/`is_current`, triées par année décroissante.
    """
    rows = participation_repository.distinct_seasons(db, club)
    by_year = {r["start_year"]: r for r in rows}

    current = season_module.current_season()
    by_year.setdefault(
        current, {"start_year": current, "event_count": 0, "participation_count": 0}
    )

    out = []
    for year in sorted(by_year, reverse=True):
        entry = by_year[year]
        out.append(
            {
                "start_year": year,
                "event_count": entry["event_count"],
                "participation_count": entry["participation_count"],
                "label": season_module.season_label(year),
                "is_current": year == current,
            }
        )
    return out


def _event_row(r) -> dict:
    return {
        "id": r.course_id,
        "event_name": r.event_name or "",
        "event_date": r.event_date.isoformat() if r.event_date else None,
        "event_type": r.event_type or "",
        "is_relay": bool(r.is_relay),
        "distance_km": r.distance_km,
        "total": r.total,
        "tcn_count": int(r.tcn_count or 0),
    }


def list_events(db: Session, **filters) -> dict:
    """Page d'épreuves (scroll infini) + compteurs globaux du filtre."""
    page = participation_repository.events_page(db, **filters)
    return {
        "items": [_event_row(r) for r in page["items"]],
        "total_events": page["total_events"],
        "total_participations": page["total_participations"],
    }
