"""Les cas d'identité qu'un admin tranche (#908, #967, epic #1146).

Calculés à la volée depuis les données, sur le modèle des épreuves en doublon
(`course_duplicates`) : aucune table de cas à tenir synchrone, seulement les
paires qu'un admin a écartées (`ignored_athlete_pairs`).

Cinq motifs, dans cet ordre :

- `same_course_bibs` : une fiche du club porte deux résultats sur une même
  épreuve individuelle (deux personnes fusionnées avant #967) ;
- `club_homonym` : des homonymes distingués dont l'un relève du club (Q1 : hors
  club, la mention au rapport d'import suffit) ;
- `swapped`, `concatenated` : nom et prénom inversés, ou nom complet face à une
  fiche découpée, que la reprise ne fusionnerait pas d'elle-même
  (`recovery_would_merge`, Q3) ;
- `alias_collision` : une fiche recréée sur une graphie qu'une fusion avait
  rattachée à une autre.
"""
from collections import defaultdict

from sqlalchemy.orm import Session

from app.core.club import normalize_club
from app.core.exceptions import DomainError, DuplicateError, NotFoundError
from app.models.athlete import Athlete
from app.repositories import athlete_repository, ignored_athlete_pair_repository
from app.services import audit

REASONS = {
    "same_course_bibs": "Deux résultats sur une même épreuve",
    "club_homonym": "Homonymes, dont un du club",
    "swapped": "Nom et prénom inversés",
    "concatenated": "Nom complet face à une fiche découpée",
    "alias_collision": "Fiche recréée sur une graphie fusionnée",
}


def recovery_would_merge(first: Athlete, second: Athlete, *, shared_course: bool) -> bool:
    """La règle de fusion automatique de la reprise (Q3) : même club ou même genre,
    renseigné des deux côtés, et jamais sur une même épreuve. Deux valeurs vides ne
    sont pas un signal."""
    if shared_course:
        return False
    same_club = bool(normalize_club(first.club)) and normalize_club(first.club) == normalize_club(second.club)
    same_gender = bool(first.gender) and first.gender == second.gender
    return same_club or same_gender


def _brief(athlete: Athlete, results: list) -> dict:
    return {
        "id": athlete.id,
        "nom": athlete.nom,
        "prenom": athlete.prenom,
        "club": athlete.club,
        "gender": athlete.gender,
        "categories": sorted({row.category for row in results if row.category}),
        "participations": len(results),
        "homonym_rank": athlete.homonym_rank,
    }


def _conflicts(courses: list[int], results_by_course: dict[int, list]) -> list[dict]:
    conflicts = []
    for course_id in courses:
        rows = results_by_course[course_id]
        conflicts.append({
            "course_id": course_id,
            "course_name": rows[0].name,
            "event_date": rows[0].event_date,
            "entries": [
                {
                    "participation_id": row.id, "athlete_id": row.athlete_id, "bib": row.bib_number,
                    "category": row.category, "total_time": row.total_time,
                }
                for row in rows
            ],
        })
    return conflicts


def find_candidates(db: Session) -> list[dict]:
    """Les cas à trancher, dans un ordre stable : par motif, puis par plus petit id."""
    two_results = athlete_repository.club_records_with_two_results_on_a_race(db)
    homonyms = athlete_repository.homonym_groups_touching_the_club(db)
    pairs = {
        "swapped": athlete_repository.swapped_pairs(db),
        "concatenated": athlete_repository.concatenated_pairs(db),
        "alias_collision": athlete_repository.alias_collisions(db),
    }
    ids = {athlete_id for athlete_id, _ in two_results} | {i for group in homonyms for i in group}
    ids |= {i for found in pairs.values() for pair in found for i in pair}
    athletes, results = athlete_repository.review_details(db, list(ids))
    by_athlete: dict[int, list] = defaultdict(list)
    for row in results:
        by_athlete[row.athlete_id].append(row)
    ignored = ignored_athlete_pair_repository.all_pairs(db)

    candidates: list[tuple[int, int, dict]] = []

    def add(reason: str, athlete_ids: list[int], conflict_courses: list[int]) -> None:
        on_courses: dict[int, list] = defaultdict(list)
        for athlete_id in athlete_ids:
            for row in by_athlete[athlete_id]:
                if row.course_id in conflict_courses:
                    on_courses[row.course_id].append(row)
        candidates.append((list(REASONS).index(reason), min(athlete_ids), {
            "reason": reason,
            "reason_label": REASONS[reason],
            "athletes": [_brief(athletes[i], by_athlete[i]) for i in athlete_ids],
            "conflicts": _conflicts(sorted(conflict_courses), on_courses),
        }))

    courses_by_athlete: dict[int, list[int]] = defaultdict(list)
    for athlete_id, course_id in two_results:
        courses_by_athlete[athlete_id].append(course_id)
    for athlete_id, courses in courses_by_athlete.items():
        add("same_course_bibs", [athlete_id], courses)

    for group in homonyms:
        if len(group) == 2 and ignored_athlete_pair_repository.normalized(*group) in ignored:
            continue
        add("club_homonym", group, [])

    for reason, found in pairs.items():
        for first_id, second_id in found:
            if ignored_athlete_pair_repository.normalized(first_id, second_id) in ignored:
                continue
            shared = sorted(
                {row.course_id for row in by_athlete[first_id]} & {row.course_id for row in by_athlete[second_id]}
            )
            if reason != "alias_collision" and recovery_would_merge(
                athletes[first_id], athletes[second_id], shared_course=bool(shared)
            ):
                continue
            add(reason, [first_id, second_id], shared)

    return [candidate for _, _, candidate in sorted(candidates, key=lambda item: item[:2])]


def ignore_pair(db: Session, *, athlete_id_a: int, athlete_id_b: int, user_id: int) -> dict:
    """Écarte une paire de la revue : l'admin les juge distinctes. `flush` sans commit."""
    if athlete_id_a == athlete_id_b:
        raise DomainError("Une fiche ne forme pas une paire avec elle-même.")
    for athlete_id in (athlete_id_a, athlete_id_b):
        if athlete_repository.get(db, athlete_id) is None:
            raise NotFoundError("Athlète introuvable.")
    if ignored_athlete_pair_repository.exists(db, athlete_id_a=athlete_id_a, athlete_id_b=athlete_id_b):
        raise DuplicateError("Cette paire est déjà écartée.")
    ignored = ignored_athlete_pair_repository.create(
        db, athlete_id_a=athlete_id_a, athlete_id_b=athlete_id_b, user_id=user_id
    )
    audit.record(
        db, user_id, action="athlete_identity.ignore", entity_type="athlete", entity_id=ignored.athlete_id_low,
        payload={"athlete_id_a": ignored.athlete_id_low, "athlete_id_b": ignored.athlete_id_high},
    )
    return {
        "athlete_id_a": ignored.athlete_id_low,
        "athlete_id_b": ignored.athlete_id_high,
        "ignored_at": ignored.ignored_at,
    }
