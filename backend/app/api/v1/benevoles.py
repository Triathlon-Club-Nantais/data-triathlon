"""Page de vérification des résultats par les bénévoles (#271).

Couche mince : garde dédiée (`require_volunteer_access`, cf. `api/deps.py`),
**distincte** de `require_permission` (SSO/RBAC) — mot de passe partagé, pas
de rôle. Deux des huit routes gardées délèguent à des fonctions déjà livrées
de `services/admin_actions.py` (réutilisées, pas dupliquées) sous le
`user_id` du compte système « Bénévoles (accès partagé) », ou de
l'administrateur admis par le pouvoir `benevole_access:manage` (#1272) ; quatre sont une
logique nouvelle — validation (`validate_participation`), signalement non
conforme et son annulation (`reject_participation`/`unreject_participation`,
#437), et correction de champs (`update_participation_fields`, #437). Les
deux dernières (`queue`, `rejected`) lisent directement le repository.
"""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import (
    NotAuthenticatedError,
    require_volunteer_access,
    volunteer_login_rate_limit,
)
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.time import utcnow
from app.core.validation import is_actionable_pending
from app.models.user import User
from app.repositories import (
    athlete_repository,
    benevole_config_repository,
    course_repository,
    participation_repository,
)
from app.schemas.admin import ParticipationReassign
from app.schemas.athlete import AthleteBrief
from app.schemas.benevole import ParticipationFieldsUpdate, VolunteerCourseRename, VolunteerLogin
from app.schemas.course import CourseBrief
from app.schemas.ids import DbId
from app.schemas.participation import ParticipationOut
from app.schemas.validation_queue import ValidationQueueHistory
from app.services import (
    admin_actions,
    benevole_access,
    scrape_service,
    shared_password,
    validation_queue_service,
)

router = APIRouter(tags=["benevoles"])


@router.post(
    "/benevoles/session", status_code=204, dependencies=[Depends(volunteer_login_rate_limit)]
)
def open_session(
    body: VolunteerLogin,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Connexion par mot de passe partagé. **Non gardée** — c'est elle qui pose
    la garde des autres routes de ce routeur."""
    config = benevole_config_repository.get_config(db)
    if config is None or not shared_password.verify_password(
        body.password, password_hash=config.password_hash, password_salt=config.password_salt
    ):
        raise NotAuthenticatedError("Mot de passe incorrect.")

    response.set_cookie(
        key=benevole_access.VOLUNTEER_SESSION_COOKIE,
        value=shared_password.sign_cookie(config.session_secret),
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
        # Pas de `max_age` : cookie de session, effacé à la fermeture du
        # navigateur. La borne réelle est serveur (#1534, `has_volunteer_cookie`).
    )


@router.delete("/benevoles/session", status_code=204)
def close_session(response: Response, settings: Settings = Depends(get_settings)):
    """Déconnexion explicite. Sans garde : sortir d'un cookie invalide doit
    toujours être possible, et le geste n'a aucun effet de bord sensible."""
    response.delete_cookie(
        key=benevole_access.VOLUNTEER_SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )


@router.get(
    "/benevoles/queue",
    response_model=list[ParticipationOut],
    dependencies=[Depends(require_volunteer_access)],
)
def queue(db: Session = Depends(get_db)):
    """Résultats en attente de validation, tous clubs confondus (research.md §D5)."""
    return participation_repository.list_pending(db)


@router.get(
    "/benevoles/queue/history",
    response_model=ValidationQueueHistory,
    dependencies=[Depends(require_volunteer_access)],
)
def queue_history(db: Session = Depends(get_db)):
    """Arriéré de la file par jour et délai moyen de résolution (US13, #466)."""
    timestamps = participation_repository.validation_queue_timestamps(db)
    return validation_queue_service.build_history(timestamps, today=utcnow().date())


#: Taille de la liste rendue au sélecteur de réattribution. Fixée ici plutôt
#: qu'ouverte en paramètre : cette route n'a qu'un appelant, et une liste
#: déroulante de vingt lignes est déjà plus longue que ce qu'on parcourt.
_SEARCH_PAGE_SIZE = 20


@router.get(
    "/benevoles/athletes",
    response_model=list[AthleteBrief],
    dependencies=[Depends(require_volunteer_access)],
)
def search_athletes(
    name: str = Query(min_length=2, description="Nom ou prénom, mot à mot, sans casse ni accents."),
    db: Session = Depends(get_db),
):
    """Recherche d'athlètes du sélecteur de réattribution (US3).

    **Jumelle de `GET /athletes`, et volontairement pas elle** : depuis #509,
    `athletes` vit derrière le mot de passe du site, que cette population n'a
    pas — un bénévole non-adhérent y recevait un 401, avalé en « aucun athlète
    trouvé » par le panneau (relevé en revue de #513). Exempter `athletes` de
    la garde site aurait rouvert toute la recherche d'athlètes du site à
    l'anonyme pour servir ce seul sélecteur ; la ranger ici lui donne la garde
    qui vaut pour la page qui l'appelle, et une seule.

    Elle rend le même `AthleteBrief` que la route publique, donc **sans date de
    naissance** — celle-ci reste réservée à `search_admin` et à son pouvoir
    RBAC (`athletes:read`, cf. `athlete_repository.search_admin`).
    """
    return athlete_repository.search(db, name=name, page_size=_SEARCH_PAGE_SIZE)


@router.patch(
    "/benevoles/courses/{course_id}",
    response_model=CourseBrief,
)
def rename_course(
    course_id: DbId,
    body: VolunteerCourseRename,
    db: Session = Depends(get_db),
    admin: User | None = Depends(require_volunteer_access),
):
    """Uniformise le nom d'une épreuve associée à un résultat en attente (US2).

    **Scopée aux épreuves qui portent un résultat en attente** (revue de
    code) : le mot de passe partagé ne doit pas ouvrir n'importe quelle
    épreuve à la réécriture, seulement celles que cette page a vocation à
    corriger.
    """
    if not participation_repository.has_pending_for_course(db, course_id):
        raise NotFoundError("Aucun résultat en attente n'est associé à cette épreuve.")
    scrape_service.ensure_rename_keeps_rows_adult(
        db, course_repository.get(db, course_id), body.name
    )
    course = admin_actions.update_course(
        db,
        course_id=course_id,
        fields={"name": body.name},
        user_id=benevole_access.actor_user_id(db, admin),
    )
    db.commit()
    return course


@router.post(
    "/benevoles/participations/{participation_id}/reassign",
    response_model=ParticipationOut,
)
def reassign(
    participation_id: DbId,
    body: ParticipationReassign,
    db: Session = Depends(get_db),
    admin: User | None = Depends(require_volunteer_access),
):
    """Réattribue un résultat en attente à un autre athlète existant (US3).

    **Scopée aux résultats encore en attente** (revue de code) : une fois
    validé, un résultat sort du périmètre que le mot de passe partagé est
    censé ouvrir.
    """
    target = participation_repository.get(db, participation_id)
    if target is None or not is_actionable_pending(target):
        raise NotFoundError("Ce résultat n'est pas ou plus en attente de validation.")
    participation = admin_actions.reassign_participation(
        db,
        participation_id=participation_id,
        athlete_id=body.athlete_id,
        user_id=benevole_access.actor_user_id(db, admin),
    )
    db.commit()
    return participation


@router.post(
    "/benevoles/participations/{participation_id}/validate",
    response_model=ParticipationOut,
)
def validate(
    participation_id: DbId,
    db: Session = Depends(get_db),
    admin: User | None = Depends(require_volunteer_access),
):
    """Valide un résultat en attente (US1) — le fait passer visible partout."""
    target = participation_repository.get(db, participation_id)
    if target is None or not is_actionable_pending(target):
        raise NotFoundError("Ce résultat n'est pas ou plus en attente de validation.")
    participation = admin_actions.validate_participation(
        db, participation_id=participation_id, user_id=benevole_access.actor_user_id(db, admin)
    )
    db.commit()
    return participation


@router.get(
    "/benevoles/rejected",
    response_model=list[ParticipationOut],
    dependencies=[Depends(require_volunteer_access)],
)
def rejected(db: Session = Depends(get_db)):
    """Résultats signalés non conformes, tous clubs confondus (#437)."""
    return participation_repository.list_rejected(db)


@router.post(
    "/benevoles/participations/{participation_id}/reject",
    response_model=ParticipationOut,
)
def reject(
    participation_id: DbId,
    db: Session = Depends(get_db),
    admin: User | None = Depends(require_volunteer_access),
):
    """Signale un résultat en attente comme non conforme (#437)."""
    target = participation_repository.get(db, participation_id)
    if target is None or not is_actionable_pending(target):
        raise NotFoundError("Ce résultat n'est pas ou plus en attente de validation.")
    participation = admin_actions.reject_participation(
        db, participation_id=participation_id, user_id=benevole_access.actor_user_id(db, admin)
    )
    db.commit()
    return participation


@router.post(
    "/benevoles/participations/{participation_id}/unreject",
    response_model=ParticipationOut,
)
def unreject(
    participation_id: DbId,
    db: Session = Depends(get_db),
    admin: User | None = Depends(require_volunteer_access),
):
    """Annule le signalement d'un résultat non conforme (#437)."""
    target = participation_repository.get(db, participation_id)
    if target is None or not target.is_pending_validation or not target.is_rejected:
        raise NotFoundError("Ce résultat n'est pas ou plus signalé non conforme.")
    participation = admin_actions.unreject_participation(
        db, participation_id=participation_id, user_id=benevole_access.actor_user_id(db, admin)
    )
    db.commit()
    return participation


@router.patch(
    "/benevoles/participations/{participation_id}",
    response_model=ParticipationOut,
)
def update_fields(
    participation_id: DbId,
    body: ParticipationFieldsUpdate,
    db: Session = Depends(get_db),
    admin: User | None = Depends(require_volunteer_access),
):
    """Corrige dossard, place au général, club et catégorie (#437)."""
    target = participation_repository.get(db, participation_id)
    if target is None or not is_actionable_pending(target):
        raise NotFoundError("Ce résultat n'est pas ou plus en attente de validation.")
    participation = admin_actions.update_participation_fields(
        db,
        participation_id=participation_id,
        fields=body.model_dump(exclude_unset=True),
        user_id=benevole_access.actor_user_id(db, admin),
    )
    db.commit()
    return participation
