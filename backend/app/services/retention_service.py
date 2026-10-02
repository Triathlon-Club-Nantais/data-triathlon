"""Purge de rétention : tenir les durées qu'annonce la politique de confidentialité (#1158).

Les durées viennent de la décision `docs/superpowers/specs/2026-10-01-base-legale-decision.md`
(#332) et sont publiées dans `frontend/components/legal/content/confidentialite.tsx` :
changer l'une sans l'autre rend la politique fausse.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.season import season_bounds, season_of
from app.repositories import (
    admin_action_log_repository,
    feedback_repository,
    profile_repository,
    training_session_repository,
)

FEEDBACK_RETENTION = timedelta(days=365)
ADMIN_LOG_RETENTION = timedelta(days=365)


@dataclass(frozen=True)
class RetentionOutcome:
    feedback: int
    admin_log: int
    profiles: int
    dry_run: bool


def youth_profile_cutoff(today: date) -> date:
    """Une adhésion close pendant la saison S est gardée jusqu'à la fin de S+1 :
    est purgé ce qui a pris fin avant le début de la saison précédant celle en cours."""
    return season_bounds(season_of(today) - 1)[0]


def purge_expired(db: Session, *, now: datetime, dry_run: bool = False) -> RetentionOutcome:
    """Supprime et commite, ou compte seulement avec `dry_run`, ce qui a dépassé sa durée."""
    feedback_cutoff = now - FEEDBACK_RETENTION
    admin_log_cutoff = now - ADMIN_LOG_RETENTION
    profiles = profile_repository.list_membership_ended_before(db, youth_profile_cutoff(now.date()))

    if dry_run:
        return RetentionOutcome(
            feedback=feedback_repository.count_created_before(db, feedback_cutoff),
            admin_log=admin_action_log_repository.count_created_before(db, admin_log_cutoff),
            profiles=len(profiles),
            dry_run=True,
        )

    for profile in profiles:
        training_session_repository.delete_participations_of_profile(db, profile.id)
        profile_repository.delete(db, profile)
    outcome = RetentionOutcome(
        feedback=feedback_repository.delete_created_before(db, feedback_cutoff),
        admin_log=admin_action_log_repository.delete_created_before(db, admin_log_cutoff),
        profiles=len(profiles),
        dry_run=False,
    )
    db.commit()
    return outcome
