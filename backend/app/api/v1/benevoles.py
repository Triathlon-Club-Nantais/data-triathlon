"""Page de vérification des résultats par les bénévoles (#271).

Couche mince : garde dédiée (`require_benevole_access`, cf. `api/deps.py`),
**distincte** de `require_permission` (SSO/RBAC) — mot de passe partagé, pas
de rôle. Trois des quatre routes gardées délèguent à des fonctions déjà
livrées de `services/admin_actions.py` (réutilisées, pas dupliquées) sous le
`user_id` du compte système « Bénévoles (accès partagé) » ; seule la
validation (`validate_participation`) est une logique nouvelle.
"""
import hmac

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import NotAuthenticatedError, require_benevole_access
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.repositories import participation_repository
from app.schemas.admin import ParticipationReassign
from app.schemas.benevole import BenevoleCourseRename, BenevoleLogin
from app.schemas.course import CourseBrief
from app.schemas.participation import ParticipationOut
from app.services import admin_actions, benevole_access

router = APIRouter(tags=["benevoles"])


@router.post("/benevoles/session", status_code=204)
def open_session(
    body: BenevoleLogin,
    response: Response,
    settings: Settings = Depends(get_settings),
):
    """Connexion par mot de passe partagé. **Non gardée** — c'est elle qui pose
    la garde des autres routes de ce routeur."""
    if not settings.benevole_shared_password or not hmac.compare_digest(
        body.password, settings.benevole_shared_password
    ):
        raise NotAuthenticatedError("Mot de passe incorrect.")

    response.set_cookie(
        key=benevole_access.BENEVOLE_SESSION_COOKIE,
        value=benevole_access.sign_session(settings.benevole_shared_password),
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
        # Pas de `max_age` : cookie de session, effacé à la fermeture du
        # navigateur (spec § Assumptions — aucune durée exigée par l'issue).
    )


@router.delete("/benevoles/session", status_code=204)
def close_session(response: Response, settings: Settings = Depends(get_settings)):
    """Déconnexion explicite. Sans garde : sortir d'un cookie invalide doit
    toujours être possible, et le geste n'a aucun effet de bord sensible."""
    response.delete_cookie(
        key=benevole_access.BENEVOLE_SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )


@router.get(
    "/benevoles/queue",
    response_model=list[ParticipationOut],
    dependencies=[Depends(require_benevole_access)],
)
def queue(db: Session = Depends(get_db)):
    """Résultats en attente de validation, tous clubs confondus (research.md §D5)."""
    return participation_repository.list_pending(db)


@router.patch(
    "/benevoles/courses/{course_id}",
    response_model=CourseBrief,
    dependencies=[Depends(require_benevole_access)],
)
def rename_course(course_id: int, body: BenevoleCourseRename, db: Session = Depends(get_db)):
    """Uniformise le nom d'une épreuve associée à un résultat en attente (US2).

    **Scopée aux épreuves qui portent un résultat en attente** (revue de
    code) : le mot de passe partagé ne doit pas ouvrir n'importe quelle
    épreuve à la réécriture, seulement celles que cette page a vocation à
    corriger.
    """
    if not participation_repository.has_pending_for_course(db, course_id):
        raise NotFoundError("Aucun résultat en attente n'est associé à cette épreuve.")
    course = admin_actions.update_course(
        db, course_id=course_id, champs={"name": body.name}, user_id=benevole_access.system_user_id(db)
    )
    db.commit()
    return course


@router.post(
    "/benevoles/participations/{participation_id}/reassign",
    response_model=ParticipationOut,
    dependencies=[Depends(require_benevole_access)],
)
def reassign(participation_id: int, body: ParticipationReassign, db: Session = Depends(get_db)):
    """Réattribue un résultat en attente à un autre athlète existant (US3).

    **Scopée aux résultats encore en attente** (revue de code) : une fois
    validé, un résultat sort du périmètre que le mot de passe partagé est
    censé ouvrir.
    """
    cible = participation_repository.get(db, participation_id)
    if cible is None or not cible.is_pending_validation:
        raise NotFoundError("Ce résultat n'est pas ou plus en attente de validation.")
    participation = admin_actions.reassign_participation(
        db,
        participation_id=participation_id,
        athlete_id=body.athlete_id,
        user_id=benevole_access.system_user_id(db),
    )
    db.commit()
    return participation


@router.post(
    "/benevoles/participations/{participation_id}/validate",
    response_model=ParticipationOut,
    dependencies=[Depends(require_benevole_access)],
)
def validate(participation_id: int, db: Session = Depends(get_db)):
    """Valide un résultat en attente (US1) — le fait passer visible partout."""
    participation = admin_actions.validate_participation(
        db, participation_id=participation_id, user_id=benevole_access.system_user_id(db)
    )
    db.commit()
    return participation
