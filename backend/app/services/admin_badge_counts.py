"""Les pastilles du rail admin, en une réponse (#1385).

Huit appels en rafale se disputaient le seul process du backend avec les
données de la page. Une pastille que la session ne voit pas n'est ni calculée
ni rendue : chaque compte reste sous le pouvoir de son écran.
"""

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.permissions import P
from app.core.season import current_season
from app.repositories import (
    athlete_claim_repository,
    club_member_repository,
    course_repository,
    feedback_repository,
    participation_repository,
    pending_provider_repository,
    result_claim_repository,
    volunteer_action_repository,
)
from app.services import athlete_identity_review, course_duplicates, member_requests

#: Clé de pastille (`nav.config.ts`), pouvoir de son écran, compte.
_BADGES: dict[str, tuple[str, Callable[[Session], int]]] = {
    "quality": (P.QUALITY_OVERRIDE.code, course_repository.count_awaiting_review),
    "duplicates": (P.COURSES_SOURCES.code, course_duplicates.count),
    "providers": (P.PENDING_PROVIDERS_READ.code, pending_provider_repository.count_unhandled),
    # La file d'attente, pas l'historique : le statut `nouveau` seul.
    "feedback": (
        P.FEEDBACK_READ.code,
        lambda db: feedback_repository.count_by_status(db).get("nouveau", 0),
    ),
    "identities": (P.ATHLETES_WRITE.code, athlete_identity_review.count),
    # La saison en cours, celle que l'écran ouvre par défaut.
    "members": (
        P.CLUB_MEMBERS_MANAGE.code,
        lambda db: club_member_repository.count_to_settle(db, current_season()),
    ),
    "volunteer": (P.ATHLETES_VOLUNTEER_VALIDATE.code, volunteer_action_repository.count_pending),
    # File commune (#1637) : demandes de fiche et réclamations de résultat.
    "claims": (
        P.ATHLETE_CLAIMS_REVIEW.code,
        lambda db: (
            athlete_claim_repository.count_pending(db) + result_claim_repository.count_pending(db)
        ),
    ),
    "member_requests": (P.MEMBER_REQUESTS_REVIEW.code, member_requests.count_pending),
}


def counts(db: Session, codes: frozenset[str], *, validation: bool) -> dict[str, int]:
    """Les comptes ouverts par `codes` ; `validation` dit si la file bénévoles est
    accessible (pouvoir `benevole_access:manage` ou cookie bénévoles)."""
    out = {key: count(db) for key, (code, count) in _BADGES.items() if code in codes}
    if validation:
        out["validation"] = participation_repository.count_pending(db)
    return out
