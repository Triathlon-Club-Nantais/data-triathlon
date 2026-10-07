"""Les cas d'identité qu'un admin tranche (#908, #967, epic #1146).

Calculés à la volée depuis les données, sur le modèle des épreuves en doublon
(`course_duplicates`) : aucune table de cas à tenir synchrone, seulement les
paires qu'un admin a écartées (`ignored_athlete_pairs`).

Six motifs, dans cet ordre de priorité (une paire n'est listée qu'une fois,
sous le premier motif qui la retient) :

- `same_course_bibs` : une fiche du club porte deux dossards sur une même
  épreuve individuelle (deux personnes fusionnées avant #967) ;
- `multi_club` : une fiche de membre dont les résultats portent un autre club,
  non confirmé, que les siens (#1209) ; l'admin sépare la fiche ou confirme le club ;
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

from app.core.club import (
    TCN_CANONICAL_NAME,
    canonical_club_key,
    is_significant_club,
    normalize_club,
)
from app.core.exceptions import DomainError, DuplicateError, NotFoundError
from app.models.athlete import Athlete
from app.repositories import (
    athlete_known_club_repository,
    athlete_repository,
    club_alias_repository,
    ignored_athlete_pair_repository,
)
from app.services import audit

REASONS = {
    "same_course_bibs": "Deux dossards sur une même épreuve",
    "multi_club": "Plusieurs clubs sur une même fiche",
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


def _significant_clubs(labels: dict[str, int], aliases: dict[str, str]) -> dict[str, dict]:
    """Les clubs significatifs d'une fiche, regroupés par clé canonique (#1209).

    Le libellé le plus fréquent nomme le club (à égalité, l'ordre alphabétique) :
    la requête ne trie pas, le nom doit rester stable d'une lecture à l'autre."""
    by_key: dict[str, dict] = {}
    for label, results in sorted(labels.items(), key=lambda item: (-item[1], item[0])):
        if not is_significant_club(label):
            continue  # ville, libellé vide ou portée TCN : pas un autre club
        key = canonical_club_key(label, aliases)
        entry = by_key.setdefault(key, {"club": label, "club_key": key, "results": 0})
        entry["results"] += results
    return by_key


def _unconfirmed_clubs(db: Session) -> dict[int, list[dict]]:
    """Fiches de membre et leurs clubs significatifs non confirmés (#1209).

    Une fiche de membre compte le TCN comme un club, même sans résultat étiqueté
    TCN (licence rattachée) : un seul autre club non confirmé suffit à la retenir.
    Un membre en double licence sort de la liste dès que son second club est confirmé."""
    members = athlete_repository.member_record_ids(db)
    labels = athlete_repository.club_labels_by_athlete(db, members)
    known = athlete_known_club_repository.keys_by_athlete(db, members)
    aliases = club_alias_repository.canonical_map(db)
    tcn_key = canonical_club_key(TCN_CANONICAL_NAME, aliases)
    cases: dict[int, list[dict]] = {}
    for athlete_id in sorted(members):
        to_check = [
            club
            for key, club in _significant_clubs(labels.get(athlete_id, {}), aliases).items()
            if key != tcn_key and key not in known.get(athlete_id, set())
        ]
        if to_check:
            cases[athlete_id] = sorted(to_check, key=lambda club: (-club["results"], club["club"]))
    return cases


def _cases(db: Session) -> list[tuple[str, list[int], list[int], list[dict]]]:
    """`(motif, fiches, épreuves en conflit, clubs à vérifier)`, dans l'ordre stable de la liste."""
    ignored = ignored_athlete_pair_repository.all_pairs(db)
    seen_pairs: set[tuple[int, int]] = set()
    cases: list[tuple[int, int, str, list[int], list[int], list[dict]]] = []

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
        cases.append((0, athlete_id, "same_course_bibs", [athlete_id], sorted(courses), []))

    for athlete_id, clubs in _unconfirmed_clubs(db).items():
        cases.append((1, athlete_id, "multi_club", [athlete_id], [], clubs))

    for group, touching in athlete_repository.homonym_groups(db):
        for first, second in combinations(group, 2):
            if (first in touching or second in touching) and keep_pair(first, second):
                cases.append((2, min(first, second), "club_homonym", [first, second], [], []))

    pairs = {
        "swapped": athlete_repository.swapped_pairs(db),
        "concatenated": athlete_repository.concatenated_pairs(db),
        "alias_collision": athlete_repository.alias_collisions(db),
    }
    all_pairs = [pair for found in pairs.values() for pair in found]
    facts = athlete_repository.pair_facts(db, all_pairs)
    athletes = athlete_repository.get_many(db, [i for pair in all_pairs for i in pair])
    for order, reason in enumerate(pairs, start=3):
        for first, second in pairs[reason]:
            fact = facts[(first, second)]
            if reason != "alias_collision" and recovery_would_merge(
                athletes[first], athletes[second], shared_course=bool(fact.shared_courses), blocked=fact.blocked
            ):
                continue
            if keep_pair(first, second):
                cases.append((order, min(first, second), reason, [first, second], fact.shared_courses, []))

    return [
        (reason, ids, courses, clubs)
        for _, _, reason, ids, courses, clubs in sorted(cases, key=lambda case: case[:2])
    ]


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
    athletes, results = athlete_repository.review_details(db, [i for _, ids, _, _ in cases for i in ids])
    by_athlete: dict[int, list] = defaultdict(list)
    for row in results:
        by_athlete[row.athlete_id].append(row)

    candidates = []
    for reason, ids, courses, clubs in cases:
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
            "clubs": clubs,
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


def confirm_club(db: Session, *, athlete_id: int, club_key: str, user_id: int) -> dict:
    """Confirme qu'un club est bien celui de la personne de la fiche (#1209) : la
    revue ne le signale plus, et l'import y rattache ses résultats. `flush` sans commit."""
    key = club_key.strip()
    if not key:
        raise DomainError("Le club à confirmer est vide.")
    if athlete_repository.get(db, athlete_id) is None:
        raise NotFoundError("Athlète introuvable.")
    labels = athlete_repository.club_labels_by_athlete(db, [athlete_id]).get(athlete_id, {})
    if key not in _significant_clubs(labels, club_alias_repository.canonical_map(db)):
        raise DomainError("Ce club ne figure pas parmi les clubs des résultats de cette fiche.")
    if athlete_known_club_repository.exists(db, athlete_id=athlete_id, club_key=key):
        raise DuplicateError("Ce club est déjà confirmé pour cette fiche.")
    known = athlete_known_club_repository.add(db, athlete_id=athlete_id, club_key=key, user_id=user_id)
    audit.record(
        db, user_id, action="athlete_identity.confirm_club", entity_type="athlete", entity_id=athlete_id,
        payload={"club_key": key},
    )
    return {"athlete_id": athlete_id, "club_key": key, "confirmed_at": known.created_at}


def _named(athlete: Athlete) -> dict:
    return {"id": athlete.id, "nom": athlete.nom, "prenom": athlete.prenom}


def list_ignored(db: Session) -> list[dict]:
    """Les paires écartées, pour les revoir (#1243)."""
    return [
        {
            "id": pair.id, "ignored_at": pair.ignored_at, "automatic": pair.ignored_by_user_id is None,
            "athletes": [_named(low), _named(high)],
        }
        for pair, low, high in ignored_athlete_pair_repository.list_with_athletes(db)
    ]


def unignore_pair(db: Session, *, pair_id: int, user_id: int) -> None:
    """Annule une mise à l'écart. La paire ne revient dans la revue que si un motif la
    retient sans que la reprise la fusionne : deux fiches de même clé, ou que
    `recovery_would_merge` accepte, seront fusionnées par la prochaine reprise."""
    pair = ignored_athlete_pair_repository.get(db, pair_id)
    if pair is None:
        raise NotFoundError("Cette paire n'est pas écartée.")
    low, high = pair.athlete_id_low, pair.athlete_id_high
    ignored_athlete_pair_repository.delete(db, pair)
    audit.record(
        db, user_id, action="athlete_identity.unignore", entity_type="athlete", entity_id=low,
        payload={"athlete_id_a": low, "athlete_id_b": high},
    )


def list_confirmed_clubs(db: Session) -> list[dict]:
    """Les clubs confirmés pour une fiche, pour les revoir (#1243)."""
    return [
        {
            "id": known.id, "athlete_id": athlete.id, "nom": athlete.nom, "prenom": athlete.prenom,
            "club_key": known.club_key, "confirmed_at": known.created_at,
        }
        for known, athlete in athlete_known_club_repository.list_with_athletes(db)
    ]


def unconfirm_club(db: Session, *, known_id: int, user_id: int) -> None:
    """Annule une confirmation de club : la fiche est de nouveau signalée pour lui.
    Les résultats que l'import a déjà rattachés sous ce club restent sur la fiche."""
    known = athlete_known_club_repository.get(db, known_id)
    if known is None:
        raise NotFoundError("Ce club n'est pas confirmé.")
    athlete_id, key = known.athlete_id, known.club_key
    athlete_known_club_repository.delete(db, known)
    audit.record(
        db, user_id, action="athlete_identity.unconfirm_club", entity_type="athlete", entity_id=athlete_id,
        payload={"club_key": key},
    )
