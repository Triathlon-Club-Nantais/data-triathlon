"""Reprise des doublons d'athlètes existants : simulée, puis appliquée (#906, #907, #908, #900).

`plan` calcule **toutes** les opérations sur l'état de départ, sans rien écrire ;
`apply` exécute exactement le plan qu'on lui donne, une transaction par
opération. Chaque fusion se juge sur la fiche telle que les fusions précédentes
du plan l'auront faite (union des épreuves, comptes, dates), de sorte que la
simulation annonce ce que l'application fait (SC-009). Une opération devenue
impossible entre-temps est consignée en erreur, les autres continuent ; relancer
la reprise ne refait rien de ce qui est fait (FR-029).

Trois familles, dans cet ordre :

1. `comma_names` : « NOM, Prénom » mal découpé avant #906 (prénom vide et nom
   virgulé, nom finissant par une virgule, prénom virgulé et inversé). La fiche
   prend son découpage, coupé sur la première virgule comme `split_athlete_name`,
   ou rejoint la fiche qui porte déjà cette identité ;
2. `same_key` : les homonymes distingués d'une clé, rangés par la migration de
   #907 (doublons d'accents, de ponctuation, d'espaces, et fiches datées par un
   admin, #900), fusionnés dans la fiche principale ;
3. `swapped`, `concatenated` : nom et prénom inversés, ou nom complet face à une
   fiche découpée, fusionnés quand les signaux concordent
   (`athlete_identity_review.recovery_would_merge`, Q3).

Toute fusion que `athlete_merge` refuserait part en revue, jamais en force, comme
toute paire qu'un admin a déclarée distincte. Les fiches factices (bouche-trous
de dossard, anonymes, équipes) sont laissées.
"""
from collections.abc import Callable

import psycopg
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.athlete_identity import athlete_identity_keys
from app.core.exceptions import DomainError
from app.models.athlete import Athlete
from app.repositories import (
    athlete_repository,
    ignored_athlete_pair_repository,
    lock_repository,
    participation_repository,
)
from app.services import athlete_identity_review, athlete_merge, audit
from app.services.admin_actions import AthleteBusyError

FAMILIES = ("comma_names", "same_key", "swapped", "concatenated")

Progress = Callable[[str], None]


def _source_key(nom: str | None, prenom: str | None) -> str | None:
    last, first = athlete_identity_keys(nom, prenom)
    return None if last is None else f"{last}|{first}"


def _is_team(athlete: Athlete) -> bool:
    return "&" in (athlete.nom or "") or "&" in (athlete.prenom or "")


def _split(athlete: Athlete) -> tuple[str, str] | None:
    """Le découpage d'une fiche virgulée, ou `None` s'il n'en donne pas une personne."""
    nom, prenom = athlete.nom or "", athlete.prenom or ""
    if not prenom.strip() and "," in nom:
        left, right = nom.split(",", 1)
        target = (left.strip(), right.strip())
    elif nom.rstrip().endswith(",") and prenom.strip():
        target = (nom.rstrip().rstrip(",").strip(), prenom.strip())
    elif prenom.rstrip().endswith(",") and nom.strip():
        target = (prenom.rstrip().rstrip(",").strip(), nom.strip())
    else:
        return None
    keys = athlete_identity_keys(*target)
    if not target[0] or not target[1] or keys[0] is None or any(c.isdigit() for k in keys for c in k):
        return None
    return target


class _Planner:
    def __init__(self, db: Session):
        self.db = db
        self.operations: list[dict] = []
        self.review: list[dict] = []
        self.absorbed: dict[int, int] = {}
        self.members: dict[int, set[int]] = {}
        self.renamed: set[int] = set()
        self.facts: dict[int, athlete_repository.IdentityFacts] = {}
        self.ignored = ignored_athlete_pair_repository.all_pairs(db)
        self.counts = {family: {"merged": 0, "review": 0} for family in FAMILIES}
        self.counts["comma_names"]["renamed"] = 0
        self.counts["same_key"]["dated"] = 0

    def root(self, athlete_id: int) -> int:
        while athlete_id in self.absorbed:
            athlete_id = self.absorbed[athlete_id]
        return athlete_id

    def is_ignored(self, first_root: int, second_root: int) -> bool:
        """Une paire écartée par un admin vaut pour tout ce que chaque fiche aura absorbé :
        la fusion reporte ce jugement sur la fiche conservée."""
        return any(
            (min(one, other), max(one, other)) in self.ignored
            for one in self.members.get(first_root, {first_root})
            for other in self.members.get(second_root, {second_root})
        )

    def refusal(self, kept_id: int, absorbed_id: int) -> str | None:
        """Le refus de `athlete_merge.blocking_reason` sur les deux fiches telles que
        le plan les aura faites."""
        return athlete_repository.merge_refusal(self.facts[kept_id], self.facts[absorbed_id])

    def merge(self, family: str, kept_id: int, absorbed_id: int, extra: dict | None = None) -> None:
        self.operations.append({"family": family, "action": "merge", "kept_id": kept_id, "absorbed_id": absorbed_id,
                                **(extra or {})})
        self.absorbed[absorbed_id] = kept_id
        self.members[kept_id] = self.members.get(kept_id, {kept_id}) | self.members.pop(absorbed_id, {absorbed_id})
        self.facts[kept_id] = self.facts[kept_id] | self.facts.pop(absorbed_id)
        self.counts[family]["merged"] += 1

    def merge_or_review(self, family: str, kept_id: int, absorbed_id: int, extra: dict | None = None) -> bool:
        kept_root, absorbed_root = self.root(kept_id), self.root(absorbed_id)
        if kept_root == absorbed_root:
            return False
        if self.is_ignored(kept_root, absorbed_root):
            self.to_review(family, [kept_id, absorbed_id], "ignored")
            return False
        reason = self.refusal(kept_root, absorbed_root)
        if reason:
            self.to_review(family, [kept_id, absorbed_id], reason)
            return False
        self.merge(family, kept_root, absorbed_root, extra)
        return True

    def to_review(self, family: str, athlete_ids: list[int], reason: str) -> None:
        self.review.append({"family": family, "athlete_ids": sorted(set(athlete_ids)), "reason": reason})

    def settled_review(self) -> list[dict]:
        """La revue sans doublon, ni paire qu'une fusion du plan a déjà réunie."""
        kept, seen = [], set()
        for entry in self.review:
            ids = tuple(entry["athlete_ids"])
            if ids in seen or (len(ids) > 1 and len({self.root(i) for i in ids}) == 1):
                continue
            seen.add(ids)
            kept.append(entry)
            self.counts[entry["family"]]["review"] += 1
        return kept


def _plan_comma_names(planner: _Planner, athletes: list[Athlete], twins: dict) -> None:
    teams = athlete_repository.relay_only(planner.db, [athlete.id for athlete in athletes])
    renamed_into: dict[tuple, int] = {}
    for athlete in athletes:
        if _is_team(athlete) or athlete.id in teams:
            continue
        target = _split(athlete)
        if target is None:
            planner.to_review("comma_names", [athlete.id], "unparsed")
            continue
        key = athlete_identity_keys(*target)
        source_keys = {"old_source_key": _source_key(athlete.nom, athlete.prenom),
                       "new_source_key": f"{key[0]}|{key[1]}"}
        twin = twins.get(key)
        if twin is not None and twin.id != athlete.id:
            planner.merge_or_review("comma_names", twin.id, athlete.id, source_keys)
        elif key in renamed_into:
            planner.merge_or_review("comma_names", renamed_into[key], athlete.id, source_keys)
        else:
            planner.operations.append({"family": "comma_names", "action": "rename", "athlete_id": athlete.id,
                                       "nom": target[0], "prenom": target[1], **source_keys})
            renamed_into[key] = athlete.id
            planner.renamed.add(athlete.id)
            planner.counts["comma_names"]["renamed"] += 1


def _plan_same_key(planner: _Planner, groups: list[tuple[int, int]], orphans: list[int]) -> None:
    """Un renommage par la virgule fait quitter sa clé à la fiche : elle n'est plus
    de ce groupe, et son groupe perd sa fiche principale s'il s'agissait d'elle."""
    athletes = athlete_repository.get_many(planner.db, [i for pair in groups for i in pair])
    for principal_id, homonym_id in groups:
        if homonym_id in planner.renamed:
            continue
        if principal_id in planner.renamed:
            planner.to_review("same_key", [homonym_id], "no_principal")
            continue
        dated = (athletes[principal_id].birth_date is None) != (athletes[homonym_id].birth_date is None)
        if planner.merge_or_review("same_key", principal_id, homonym_id) and dated:
            planner.counts["same_key"]["dated"] += 1
    for orphan_id in orphans:
        if orphan_id not in planner.renamed:
            planner.to_review("same_key", [orphan_id], "no_principal")


def _plan_pairs(planner: _Planner, pairs: dict[str, list[tuple[int, int]]]) -> None:
    athletes = athlete_repository.get_many(planner.db, [i for found in pairs.values() for pair in found for i in pair])
    for family, found in pairs.items():
        for first, second in found:
            first_root, second_root = planner.root(first), planner.root(second)
            if first_root == second_root:
                continue
            if planner.is_ignored(first_root, second_root):
                planner.to_review(family, [first, second], "ignored")
            elif planner.facts[first_root].courses & planner.facts[second_root].courses:
                planner.to_review(family, [first, second], "shared_course")
            elif planner.refusal(first_root, second_root):
                planner.to_review(family, [first, second], "merge_refused")
            elif not athlete_identity_review.recovery_would_merge(
                athletes[first], athletes[second], shared_course=False, blocked=False
            ):
                planner.to_review(family, [first, second], "no_signal")
            else:
                carried = {root: planner.facts[root].carried for root in (first_root, second_root)}
                kept = max((first_root, second_root), key=lambda root: (carried[root], -root))
                planner.merge(family, kept, second_root if kept == first_root else first_root)


def plan(db: Session, *, progress: Progress | None = None) -> dict:
    """Ce que la reprise ferait, sans rien écrire. Les faits qui décident des
    fusions se lisent en lot, une fois, pour toutes les fiches candidates."""
    say = progress or (lambda message: None)
    planner = _Planner(db)
    say("Lecture des candidats")
    comma = athlete_repository.comma_named(db)
    twins = athlete_repository.get_by_identity_keys_batch(
        db, [athlete_identity_keys(*t) for t in map(_split, comma) if t is not None]
    )
    groups = athlete_repository.homonyms_with_their_principal(db)
    orphans = athlete_repository.homonyms_without_principal(db)
    pairs = {"swapped": athlete_repository.swapped_pairs(db), "concatenated": athlete_repository.concatenated_pairs(db)}
    candidates = {a.id for a in comma} | {t.id for t in twins.values()} | {i for pair in groups for i in pair}
    candidates |= {i for found in pairs.values() for pair in found for i in pair}
    say(f"Lecture des faits de {len(candidates)} fiches")
    planner.facts = athlete_repository.identity_facts(db, sorted(candidates))
    say("Noms virgulés")
    _plan_comma_names(planner, comma, twins)
    say("Mêmes clés")
    _plan_same_key(planner, groups, orphans)
    say("Paires inversées et concaténées")
    _plan_pairs(planner, pairs)
    review = planner.settled_review()
    # La simulation ne garde aucune transaction ouverte pendant la relecture.
    db.rollback()
    return {
        "applied": False,
        "families": planner.counts,
        "operations": planner.operations,
        "review": review,
        "errors": [],
    }


def _rename(db: Session, operation: dict, user_id: int) -> None:
    athlete = athlete_repository.get(db, operation["athlete_id"])
    if athlete is None:
        raise DomainError("Athlète introuvable.")
    before = {"nom": athlete.nom, "prenom": athlete.prenom}
    # Comme le renommage de l'écran : un import qui tient la fiche (`FOR KEY SHARE`)
    # se laisse attendre 5 s, au-delà la fiche est déclarée occupée.
    lock_repository.bound_lock_waits(db, "5s")
    try:
        athlete_repository.update_identity(db, athlete, nom=operation["nom"], prenom=operation["prenom"], homonym_rank=0)
        db.flush()
    except OperationalError as exc:
        if isinstance(exc.orig, psycopg.errors.LockNotAvailable):
            raise AthleteBusyError() from exc
        raise
    lock_repository.bound_lock_waits(db, "0")
    participation_repository.retarget_source_key(
        db, athlete_id=athlete.id, old_key=operation["old_source_key"], new_key=operation["new_source_key"]
    )
    audit.record(db, user_id, action="athlete.update", entity_type="athlete", entity_id=athlete.id,
                 payload={"before": before, "after": {"nom": athlete.nom, "prenom": athlete.prenom}})


def _merge(db: Session, operation: dict, user_id: int) -> None:
    athlete_merge.merge_athletes(
        db, kept_id=operation["kept_id"], absorbed_id=operation["absorbed_id"], user_id=user_id
    )
    if "new_source_key" in operation:
        # Après la fusion : ses résultats portent désormais `kept_id`, sous l'ancienne clé.
        participation_repository.retarget_source_key(
            db, athlete_id=operation["kept_id"], old_key=operation["old_source_key"],
            new_key=operation["new_source_key"],
        )


def apply(db: Session, planned: dict, *, user_id: int, report: dict | None = None,
          progress: Progress | None = None) -> dict:
    """Exécute le plan, une transaction par opération, journalisée au nom de `user_id`.

    `report` est rempli au fil de l'eau : interrompue (Ctrl-C), la reprise rend
    encore ce qui a été fait, et ce qui est fait reste commité.
    """
    report = report if report is not None else {}
    report.update({**planned, "applied": True, "errors": [], "done": 0})
    total = len(planned["operations"])
    for index, operation in enumerate(planned["operations"], 1):
        try:
            if operation["action"] == "rename":
                _rename(db, operation, user_id)
            else:
                _merge(db, operation, user_id)
            db.commit()
            report["done"] += 1
        except (DomainError, SQLAlchemyError) as exc:
            db.rollback()
            report["errors"].append({"operation": operation, "error": str(exc)})
        if progress and (index % 100 == 0 or index == total):
            progress(f"{index}/{total} opérations ({len(report['errors'])} en erreur)")
    return report
