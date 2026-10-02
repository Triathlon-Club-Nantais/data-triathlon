"""Les cas d'identité qu'un admin tranche (#908, #967, epic #1146).

Calculés à la volée depuis les données, sur le modèle des épreuves en doublon
(`course_duplicates`) : aucune table de cas à tenir synchrone, seulement les
paires qu'un admin a écartées (`ignored_athlete_pairs`).

Cinq motifs, dans cet ordre de priorité (une paire n'est listée qu'une fois,
sous le premier motif qui la retient) :

- `same_course_bibs` : une fiche du club porte deux dossards sur une même
  épreuve individuelle (deux personnes fusionnées avant #967) ;
- `club_homonym` : une paire d'homonymes distingués dont l'un relève du club
  (Q1 : hors club, la mention au rapport d'import suffit) ;
- `swapped`, `concatenated` : nom et prénom inversés, ou nom complet face à une
  fiche découpée, que la reprise ne fusionnerait pas d'elle-même
  (`recovery_would_merge`, Q3) ;
- `alias_collision` : une fiche recréée sur une graphie qu'une fusion avait
  rattachée à une autre.
"""
from collections import defaultdict
from itertools import combinations

from sqlalchemy.orm import Session

from app.core.club import normalize_club
from app.core.exceptions import DomainError, DuplicateError, NotFoundError
from app.models.athlete import Athlete
from app.repositories import athlete_repository, ignored_athlete_pair_repository
from app.services import audit

REASONS = {
    "same_course_bibs": "Deux dossards sur une même épreuve",
    "club_homonym": "Homonymes, dont un du club",
    "swapped": "Nom et prénom inversés",
    "concatenated": "Nom complet face à une fiche découpée",
    "alias_collision": "Fiche recréée sur une graphie fusionnée",
}


def recovery_would_merge(first: Athlete, second: Athlete, *, shared_course: bool, blocked: bool) -> bool:
    """La règle de fusion automatique de la reprise (Q3), partagée avec elle.

    Même club ou même genre, renseigné des deux côtés (deux valeurs vides ne sont
    pas un signal), jamais sur une même épreuve, et aucun des refus de la fusion
    (`blocked`, cf. `athlete_repository.pair_facts`) : une paire que la fusion
    refuserait reste en revue au lieu de disparaître de tous les circuits.
    """
    if shared_course or blocked:
        return False
    same_club = bool(normalize_club(first.club)) and normalize_club(first.club) == normalize_club(second.club)
    same_gender = bool(first.gender) and first.gender == second.gender
    return same_club or same_gender


def _cases(db: Session) -> list[tuple[str, list[int], list[int]]]:
    """`(motif, fiches, épreuves en conflit)`, dans l'ordre stable de la liste."""
    ignored = ignored_athlete_pair_repository.all_pairs(db)
    seen_pairs: set[tuple[int, int]] = set()
    cases: list[tuple[int, int, str, list[int], list[int]]] = []

    def keep_pair(first: int, second: int) -> bool:
        pair = ignored_athlete_pair_repository.normalized(first, second)
        if pair in ignored or pair in seen_pairs:
            return False
        seen_pairs.add(pair)
        return True

    courses_by_athlete: dict[int, list[int]] = defaultdict(list)
    for athlete_id, course_id in athlete_repository.club_records_with_two_bibs_on_a_race(db):
        courses_by_athlete[athlete_id].append(course_id)
    for athlete_id, courses in courses_by_athlete.items():
        cases.append((0, athlete_id, "same_course_bibs", [athlete_id], sorted(courses)))

    for group, touching in athlete_repository.homonym_groups(db):
        for first, second in combinations(group, 2):
            if (first in touching or second in touching) and keep_pair(first, second):
                cases.append((1, min(first, second), "club_homonym", [first, second], []))

    pairs = {
        "swapped": athlete_repository.swapped_pairs(db),
        "concatenated": athlete_repository.concatenated_pairs(db),
        "alias_collision": athlete_repository.alias_collisions(db),
    }
    all_pairs = [pair for found in pairs.values() for pair in found]
    facts = athlete_repository.pair_facts(db, all_pairs)
    athletes = athlete_repository.get_many(db, [i for pair in all_pairs for i in pair])
    for order, reason in enumerate(pairs, start=2):
        for first, second in pairs[reason]:
            fact = facts[(first, second)]
            if reason != "alias_collision" and recovery_would_merge(
                athletes[first], athletes[second], shared_course=bool(fact.shared_courses), blocked=fact.blocked
            ):
                continue
            if keep_pair(first, second):
                cases.append((order, min(first, second), reason, [first, second], fact.shared_courses))

    return [(reason, ids, courses) for _, _, reason, ids, courses in sorted(cases, key=lambda case: case[:2])]


def count(db: Session) -> int:
    """La taille de la liste, sans charger le détail des fiches ni de leurs résultats."""
    return len(_cases(db))


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


def find_candidates(db: Session) -> list[dict]:
    """Les cas à trancher, avec leurs fiches et les épreuves en conflit."""
    cases = _cases(db)
    athletes, results = athlete_repository.review_details(db, [i for _, ids, _ in cases for i in ids])
    by_athlete: dict[int, list] = defaultdict(list)
    for row in results:
        by_athlete[row.athlete_id].append(row)

    candidates = []
    for reason, ids, courses in cases:
        conflicts = []
        for course_id in courses:
            rows = [row for athlete_id in ids for row in by_athlete[athlete_id] if row.course_id == course_id]
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
        candidates.append({
            "reason": reason,
            "reason_label": REASONS[reason],
            "athletes": [_brief(athletes[i], by_athlete[i]) for i in ids],
            "conflicts": conflicts,
        })
    return candidates


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
