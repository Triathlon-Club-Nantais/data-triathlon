"""Agrégations statistiques (club / tableau de bord)."""
from sqlalchemy.orm import Session

from app.repositories import participation_repository


def _athlete_key(part) -> str:
    a = part.athlete
    return f"{a.nom}||{a.prenom}" if a else f"id:{part.athlete_id}"


def get_stats(db: Session, club: str | None = None) -> dict:
    """Stats agrégées : total, athlètes, épreuves, répartition par type/mois, récents."""
    parts = participation_repository.for_stats(db, club)
    if not parts:
        return {"total": 0, "athletes": 0, "events": 0, "by_type": {}, "by_month": {}, "recent": []}

    athlete_set = {_athlete_key(p) for p in parts}
    event_set = {p.course.name for p in parts if p.course and p.course.name}

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


def list_events(db: Session, **filters) -> list[dict]:
    """Épreuves distinctes avec compteurs (total + membres TCN)."""
    rows = participation_repository.events_with_counts(db, **filters)
    return [
        {
            "event_name": r.event_name or "",
            "event_date": r.event_date.isoformat() if r.event_date else None,
            "event_type": r.event_type or "",
            "total": r.total,
            "tcn_count": int(r.tcn_count or 0),
        }
        for r in rows
    ]
