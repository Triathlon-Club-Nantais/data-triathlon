"""Reprise des doublons d'athlètes existants : simulée, puis appliquée (#906, #907, #908, #900).

`plan` calcule **toutes** les opérations sur l'état de départ, sans rien écrire ;
`apply` exécute exactement ce plan, une transaction par opération. La simulation
annonce donc ce que l'application fait (SC-009). Une opération devenue impossible
entre-temps est consignée en erreur, les autres continuent ; relancer la reprise
ne refait rien de ce qui est fait (FR-029).

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

Toute fusion que `athlete_merge` refuserait part en revue, jamais en force. Les
fiches factices (bouche-trous de dossard, anonymes, équipes) sont laissées.
"""
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.athlete_identity import athlete_identity_keys
from app.core.exceptions import DomainError
from app.models.athlete import Athlete
from app.repositories import athlete_repository, participation_repository
from app.services import athlete_identity_review, athlete_merge, audit

FAMILIES = ("comma_names", "same_key", "swapped", "concatenated")


def _source_key(nom: str | None, prenom: str | None) -> str | None:
    last, first = athlete_identity_keys(nom, prenom)
    return None if last is None else f"{last}|{first}"


def _split(athlete: Athlete) -> tuple[str, str] | None:
    """Le découpage d'une fiche virgulée, ou `None` si elle n'est pas une personne."""
    nom, prenom = athlete.nom or "", athlete.prenom or ""
    if "&" in nom or "&" in prenom:
        return None
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
        self.counts = {family: {"merged": 0, "review": 0} for family in FAMILIES}
        self.counts["comma_names"]["renamed"] = 0

    def root(self, athlete_id: int) -> int:
        while athlete_id in self.absorbed:
            athlete_id = self.absorbed[athlete_id]
        return athlete_id

    def merge_or_review(self, family: str, kept_id: int, absorbed_id: int, extra: dict | None = None) -> None:
        kept_id, absorbed_id = self.root(kept_id), self.root(absorbed_id)
        if kept_id == absorbed_id:
            return
        kept, absorbed = self.db.get(Athlete, kept_id), self.db.get(Athlete, absorbed_id)
        reason = athlete_merge.blocking_reason(self.db, kept, absorbed)
        if reason:
            self.to_review(family, [kept_id, absorbed_id], reason)
            return
        self.operations.append({"family": family, "action": "merge", "kept_id": kept_id, "absorbed_id": absorbed_id,
                                **(extra or {})})
        self.absorbed[absorbed_id] = kept_id
        self.counts[family]["merged"] += 1

    def to_review(self, family: str, athlete_ids: list[int], reason: str) -> None:
        self.review.append({"family": family, "athlete_ids": sorted(athlete_ids), "reason": reason})
        self.counts[family]["review"] += 1


def _plan_comma_names(planner: _Planner) -> None:
    athletes = athlete_repository.comma_named(planner.db)
    targets = {athlete.id: _split(athlete) for athlete in athletes}
    keys = {a_id: athlete_identity_keys(*t) for a_id, t in targets.items() if t is not None}
    existing = athlete_repository.get_by_identity_keys_batch(planner.db, list(keys.values()))
    renamed_into: dict[tuple, int] = {}
    for athlete in athletes:
        target = targets[athlete.id]
        if target is None:
            continue
        key = keys[athlete.id]
        source_keys = {"old_source_key": _source_key(athlete.nom, athlete.prenom),
                       "new_source_key": f"{key[0]}|{key[1]}"}
        twin = existing.get(key)
        if twin is not None and twin.id != athlete.id:
            planner.merge_or_review("comma_names", twin.id, athlete.id, source_keys)
        elif key in renamed_into:
            planner.merge_or_review("comma_names", renamed_into[key], athlete.id, source_keys)
        else:
            planner.operations.append({"family": "comma_names", "action": "rename", "athlete_id": athlete.id,
                                       "nom": target[0], "prenom": target[1], **source_keys})
            renamed_into[key] = athlete.id
            planner.counts["comma_names"]["renamed"] += 1


def _plan_same_key(planner: _Planner) -> None:
    for principal_id, homonym_id in athlete_repository.homonyms_with_their_principal(planner.db):
        planner.merge_or_review("same_key", principal_id, homonym_id)


def _plan_pairs(planner: _Planner) -> None:
    pairs = {
        "swapped": athlete_repository.swapped_pairs(planner.db),
        "concatenated": athlete_repository.concatenated_pairs(planner.db),
    }
    every = [pair for found in pairs.values() for pair in found]
    facts = athlete_repository.pair_facts(planner.db, every)
    athletes = athlete_repository.get_many(planner.db, [i for pair in every for i in pair])
    for family, found in pairs.items():
        for first, second in found:
            if planner.root(first) == planner.root(second) or first in planner.absorbed or second in planner.absorbed:
                continue
            fact = facts[(first, second)]
            if fact.shared_courses:
                planner.to_review(family, [first, second], "shared_course")
            elif fact.blocked:
                planner.to_review(family, [first, second], "merge_refused")
            elif not athlete_identity_review.recovery_would_merge(
                athletes[first], athletes[second], shared_course=False, blocked=False
            ):
                planner.to_review(family, [first, second], "no_signal")
            else:
                counts = {i: participation_repository.count_carried(planner.db, i) for i in (first, second)}
                kept = first if (counts[first], -first) >= (counts[second], -second) else second
                planner.merge_or_review(family, kept, second if kept == first else first)


def plan(db: Session) -> dict:
    """Ce que la reprise ferait, sans rien écrire."""
    planner = _Planner(db)
    _plan_comma_names(planner)
    _plan_same_key(planner)
    _plan_pairs(planner)
    return {
        "applied": False,
        "families": planner.counts,
        "operations": planner.operations,
        "review": planner.review,
        "errors": [],
    }


def _rename(db: Session, operation: dict, user_id: int) -> None:
    athlete = athlete_repository.get(db, operation["athlete_id"])
    if athlete is None:
        raise DomainError("Athlète introuvable.")
    before = {"nom": athlete.nom, "prenom": athlete.prenom}
    athlete_repository.update_identity(db, athlete, nom=operation["nom"], prenom=operation["prenom"], homonym_rank=0)
    participation_repository.retarget_source_key(
        db, athlete_id=athlete.id, old_key=operation["old_source_key"], new_key=operation["new_source_key"]
    )
    audit.record(db, user_id, action="athlete.update", entity_type="athlete", entity_id=athlete.id,
                 payload={"before": before, "after": {"nom": athlete.nom, "prenom": athlete.prenom}})


def _merge(db: Session, operation: dict, user_id: int) -> None:
    if "new_source_key" in operation:
        participation_repository.retarget_source_key(
            db, athlete_id=operation["absorbed_id"], old_key=operation["old_source_key"],
            new_key=operation["new_source_key"],
        )
    athlete_merge.merge_athletes(
        db, kept_id=operation["kept_id"], absorbed_id=operation["absorbed_id"], user_id=user_id
    )


def apply(db: Session, planned: dict, *, user_id: int, report: dict | None = None) -> dict:
    """Exécute le plan, une transaction par opération, journalisée au nom de `user_id`.

    `report` est rempli au fil de l'eau : interrompue (Ctrl-C), la reprise rend
    encore ce qui a été fait, et ce qui est fait reste commité.
    """
    report = report if report is not None else {}
    report.update({**planned, "applied": True, "errors": [], "done": 0})
    for operation in planned["operations"]:
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
    return report
