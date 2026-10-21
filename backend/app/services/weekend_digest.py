"""Récap Slack des résultats TCN d'un week-end (#1363)."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.gender import is_gender_podium
from app.core.youth import is_youth
from app.repositories import course_repository, participation_repository
from app.scrapers.base import STATUS_FINISHER
from app.services.club_service import best_rank
from app.services.opposition_service import is_anonymous

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
_SCOPE_LABELS = {"overall": "scratch", "gender": "classement par sexe", "category": "catégorie"}


@dataclass(frozen=True)
class DigestPodium:
    name: str
    rank: int
    scope: str


@dataclass(frozen=True)
class DigestCourse:
    course_id: int
    name: str
    finishers: int
    podiums: list[DigestPodium]


def weekend_before(day: date) -> tuple[date, date]:
    """Samedi et dimanche du week-end qui précède `day` (un samedi ou un dimanche vise le précédent)."""
    sunday = day - timedelta(days=(day.weekday() + 1) % 7 or 7)
    return sunday - timedelta(days=1), sunday


def collect(db: Session, saturday: date, sunday: date) -> list[DigestCourse]:
    courses = course_repository.list_all(
        db, club_only=True, date_from=saturday, date_to=sunday, page_size=500, hide_pending_only=True
    )
    rows_by_course = defaultdict(list)
    for row in participation_repository.weekend_digest_rows(db, [course.id for course in courses]):
        rows_by_course[row.course_id].append(row)

    digest = []
    for course in courses:
        finishers = 0
        podiums = []
        for row in rows_by_course[course.id]:
            if row.status.lower() == STATUS_FINISHER and row.rank_overall is not None:
                finishers += 1
            best = best_rank({
                "overall": row.rank_overall,
                "gender": row.rank_gender if is_gender_podium(row.rank_gender, row.gender) else None,
                "category": row.rank_category,
            })
            # Opposition (#1172) et jeunes : comptés, jamais nommés.
            if best is None or is_anonymous(row.prenom, row.nom):
                continue
            if is_youth(course.name, row.category, event_year=course.event_date.year):
                continue
            scope, rank = best
            podiums.append(DigestPodium(f"{row.prenom} {row.nom}".strip(), rank, scope))
        podiums.sort(key=lambda podium: (podium.rank, podium.name))
        digest.append(DigestCourse(course.id, course.name, finishers, podiums))
    return digest


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(courses: list[DigestCourse], *, saturday: date, sunday: date, base_url: str) -> str:
    lines = [f"*Résultats TCN du week-end des {saturday:%d/%m} et {sunday:%d/%m/%Y}*"]
    for course in courses:
        name = _escape(course.name)
        title = f"<{base_url}/courses/{course.course_id}|{name}>" if base_url else name
        plural = "s" if course.finishers > 1 else ""
        lines.append(f"• {title} : {course.finishers} TCN classé{plural}")
        lines.extend(
            f"    {_MEDALS[podium.rank]} {_escape(podium.name)} ({_SCOPE_LABELS[podium.scope]})"
            for podium in course.podiums
        )
    return "\n".join(lines)
