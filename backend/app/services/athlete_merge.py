"""Fusion de deux fiches d'une même personne : l'aperçu et l'acte (#908, epic #1146).

Comme la fusion d'épreuves (`course_merge`), l'aperçu et l'acte partagent le
même prédicat de refus (`_blocking_reason`) : l'écran ne peut pas annoncer une
fusion que l'acte refuserait.

La fiche absorbée disparaît ; tout ce qui la référence passe sur la fiche
conservée (résultats, liens d'équipier, actions bénévoles, validations de
saison, comptes membres), et sa graphie devient une variante de la conservée,
que l'import résout désormais comme elle (Q2 de la spec).
"""
import logging

import psycopg.errors
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.models.athlete import Athlete
from app.repositories import (
    athlete_alias_repository,
    athlete_repository,
    lock_repository,
    participation_repository,
    season_validation_repository,
    user_repository,
    volunteer_action_repository,
)
from app.services import audit
from app.services.admin_actions import AthleteBusyError
from app.services.course_locks import lock_courses_or_409

logger = logging.getLogger(__name__)

#: Les refus, et leur libellé affichable. Deux fiches qui les déclenchent sont,
#: ou peuvent être, deux personnes : la fusion les confondrait.
_REFUSALS = {
    "same_athlete": "Une fiche ne se fusionne pas avec elle-même.",
    "distinct_users": "Les deux fiches sont liées à deux comptes membres différents.",
    "same_course_bibs": "Les deux fiches ont chacune un résultat sur une même épreuve individuelle : ce sont deux personnes.",
    "same_participation": "Les deux fiches figurent sur un même résultat de relais.",
    "distinct_birth_dates": "Les deux fiches portent deux dates de naissance différentes.",
}


class AthleteMergeRefusedError(DomainError):
    status_code = 409

    def __init__(self, reason: str):
        super().__init__(_REFUSALS[reason])
        self.code = reason


def _athlete_or_404(db: Session, athlete_id: int) -> Athlete:
    athlete = athlete_repository.get(db, athlete_id)
    if athlete is None:
        raise NotFoundError("Athlète introuvable.")
    return athlete


def _blocking_reason(db: Session, kept: Athlete, absorbed: Athlete) -> str | None:
    if kept.id == absorbed.id:
        return "same_athlete"
    if user_repository.ids_linked_to_athlete(db, kept.id) and user_repository.ids_linked_to_athlete(db, absorbed.id):
        return "distinct_users"
    if participation_repository.share_an_individual_course(db, kept.id, absorbed.id):
        return "same_course_bibs"
    if participation_repository.share_a_participation(db, kept.id, absorbed.id):
        return "same_participation"
    if kept.birth_date and absorbed.birth_date and kept.birth_date != absorbed.birth_date:
        return "distinct_birth_dates"
    return None


def _brief(db: Session, athlete: Athlete) -> dict:
    return {
        "id": athlete.id, "nom": athlete.nom, "prenom": athlete.prenom, "club": athlete.club,
        "participations": participation_repository.count_carried(db, athlete.id),
    }


def _adds_alias(kept: Athlete, absorbed: Athlete) -> bool:
    key = (absorbed.last_name_key, absorbed.first_name_key)
    return key[0] is not None and key != (kept.last_name_key, kept.first_name_key)


def merge_impact(db: Session, *, kept_id: int, absorbed_id: int) -> dict:
    """Ce que la fusion ferait, sans rien écrire."""
    kept, absorbed = _athlete_or_404(db, kept_id), _athlete_or_404(db, absorbed_id)
    reason = _blocking_reason(db, kept, absorbed)
    return {
        "kept": _brief(db, kept),
        "absorbed": _brief(db, absorbed),
        "moves": {
            "participations": participation_repository.count_carried(db, absorbed.id),
            "teammates": participation_repository.count_teammate_links(db, absorbed.id),
            "volunteer_actions": volunteer_action_repository.count_for_athlete(db, absorbed.id),
            "season_validations": season_validation_repository.count_for_athlete(db, absorbed.id),
            "users": len(user_repository.ids_linked_to_athlete(db, absorbed.id)),
        },
        "alias_added": _adds_alias(kept, absorbed),
        "blocking_reason": reason,
        "blocking_label": _REFUSALS.get(reason) if reason else None,
    }


def _lock(db: Session, kept_id: int, absorbed_id: int) -> tuple[Athlete, Athlete]:
    """Les deux fiches en `FOR UPDATE`, puis leurs épreuves.

    L'ordre compte : un import qui a résolu l'une des fiches (`FOR KEY SHARE`)
    termine d'abord, et ses résultats suivent la fusion. L'attente est bornée,
    au-delà la fiche est déclarée en cours d'import (409). Les épreuves se
    verrouillent ensuite sans attendre (`lock_courses_or_409`), comme pour tout
    geste admin sur une épreuve.
    """
    lock_repository.bound_lock_waits(db, "5s")
    try:
        locked = athlete_repository.lock_for_merge(db, [kept_id, absorbed_id])
    except OperationalError as exc:
        if isinstance(exc.orig, psycopg.errors.LockNotAvailable):
            raise AthleteBusyError() from exc
        raise
    if kept_id not in locked or absorbed_id not in locked:
        raise NotFoundError("Athlète introuvable.")
    courses = participation_repository.course_ids_carried_by(
        db, kept_id
    ) | participation_repository.course_ids_carried_by(db, absorbed_id)
    lock_courses_or_409(db, *sorted(courses))
    return locked[kept_id], locked[absorbed_id]


def _complete(kept: Athlete, absorbed: Athlete) -> None:
    """La fiche conservée prend ce qu'elle n'a pas ; un club corrigé à la main prime."""
    if absorbed.club_locked and not kept.club_locked:
        kept.club, kept.club_locked = absorbed.club, True
    elif not kept.club and absorbed.club:
        kept.club = absorbed.club
    if not kept.gender and absorbed.gender:
        kept.gender = absorbed.gender
    if kept.birth_date is None and absorbed.birth_date is not None:
        kept.birth_date = absorbed.birth_date


def merge_athletes(db: Session, *, kept_id: int, absorbed_id: int, user_id: int) -> Athlete:
    """Absorbe `absorbed_id` dans `kept_id`. Tout ou rien : `flush` sans `commit`,
    la route clôt la transaction ; un refus n'écrit ni donnée ni journal."""
    if kept_id == absorbed_id:
        raise AthleteMergeRefusedError("same_athlete")
    kept, absorbed = _lock(db, kept_id, absorbed_id)
    reason = _blocking_reason(db, kept, absorbed)
    if reason:
        raise AthleteMergeRefusedError(reason)

    summary = {"absorbed": {"id": absorbed.id, "nom": absorbed.nom, "prenom": absorbed.prenom, "club": absorbed.club}}
    alias_key = (absorbed.last_name_key, absorbed.first_name_key)
    alias_added = _adds_alias(kept, absorbed)
    takes_principal_rank = kept.homonym_rank > 0 and absorbed.homonym_rank == 0 and not alias_added

    db.flush()
    carried, teammates = participation_repository.repoint_athlete(
        db, from_athlete_id=absorbed.id, to_athlete_id=kept.id
    )
    summary["moved"] = {
        "participations": carried,
        "teammates": teammates,
        "volunteer_actions": volunteer_action_repository.repoint(db, from_athlete_id=absorbed.id, to_athlete_id=kept.id),
        "season_validations": season_validation_repository.repoint_deduplicated(
            db, from_athlete_id=absorbed.id, to_athlete_id=kept.id
        ),
        "users": user_repository.repoint_athlete(db, from_athlete_id=absorbed.id, to_athlete_id=kept.id),
    }
    athlete_alias_repository.repoint(db, from_athlete_id=absorbed.id, to_athlete_id=kept.id)
    _complete(kept, absorbed)
    db.expunge(absorbed)
    athlete_repository.delete_by_id(db, absorbed.id)
    if alias_added:
        alias_added = athlete_alias_repository.add(db, alias_key, kept.id)
    if takes_principal_rank:
        kept.homonym_rank = 0
    db.flush()
    db.expire(kept, ["participations"])
    summary["alias_added"] = alias_added

    audit.record(db, user_id, action="athlete.merge", entity_type="athlete", entity_id=kept.id, payload=summary)
    logger.info("Admin %s merged athlete %s into %s", user_id, absorbed_id, kept_id)
    return kept
