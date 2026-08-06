"""Router d'administration des données (#117) — six ressources, six gardes.

**Chacune porte sa garde individuellement, et nomme un pouvoir, jamais un rôle**
(#115, FR-017/FR-018). Aucune garde de préfixe, et ce n'est pas une préférence
de style : `admin.py` monte sous le même `/admin/` le signalement **anonyme** du
site public, qu'une garde posée sur le préfixe supprimerait sans que rien ne la
nomme.

Couche mince : validation, délégation à `services/admin_actions.py`, traduction
en HTTP. La transaction se clôt ici — le service `flush`, la route `commit` —,
ce qui rend l'action et sa trace indissociables (FR-015) : un refus lève avant
le commit, et rien n'est écrit, ni la donnée ni le journal.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.repositories import athlete_repository
from app.schemas.admin import (
    AdminAthleteRead,
    AdminAthleteUpdate,
    AdminCourseUpdate,
    CourseDeletionImpact,
    ParticipationReassign,
)
from app.schemas.course import CourseBrief
from app.schemas.participation import ParticipationOut
from app.services import admin_actions

router = APIRouter(tags=["admin"])


def _fiche(athlete, participations: int | None = None) -> AdminAthleteRead:
    """Une fiche coureur prête à servir. Trois routes la construisent."""
    return AdminAthleteRead(
        id=athlete.id,
        nom=athlete.nom,
        prenom=athlete.prenom,
        birth_date=athlete.birth_date,
        gender=athlete.gender,
        club=athlete.club,
        participations=len(athlete.participations) if participations is None else participations,
    )


@router.get("/admin/athletes", response_model=list[AdminAthleteRead])
def search_athletes(
    search: str | None = Query(None, description="Filtre sur le nom et le prénom."),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ATHLETES_READ)),
):
    """Recherche de coureurs **avec leur identité complète** (FR-024).

    C'est la seule ressource du site qui rend une date de naissance, et c'est ce
    pouvoir qui la garde (FR-025). La lecture publique `GET /athletes` ne
    l'expose pas — l'y ajouter viderait cette garde de son objet.
    """
    return [
        _fiche(athlete, nombre)
        for athlete, nombre in athlete_repository.search_admin(
            db, search=search, page=page, page_size=page_size
        )
    ]


@router.get("/admin/athletes/{athlete_id}", response_model=AdminAthleteRead)
def get_athlete(
    athlete_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ATHLETES_READ)),
):
    """Une fiche coureur **complète**, par son identifiant.

    Sans elle, l'écran d'édition atteint depuis un résultat n'aurait que
    l'`AthleteBrief` de la participation — **sans `birth_date`** — et
    l'enregistrement effacerait une date de naissance qu'il n'a jamais lue.
    """
    return _fiche(admin_actions.get_athlete(db, athlete_id=athlete_id))


@router.post(
    "/admin/participations/{participation_id}/reassign", response_model=ParticipationOut
)
def reassign_participation(
    participation_id: int,
    body: ParticipationReassign,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.PARTICIPATIONS_REASSIGN)),
):
    """Rattache un résultat au bon coureur.

    `POST` et non `PATCH` : ce n'est pas l'édition d'un champ, c'est un geste
    nommé qui déplace un rattachement et peut détruire une fiche coureur au
    passage.
    """
    participation = admin_actions.reassign_participation(
        db, participation_id=participation_id, athlete_id=body.athlete_id, user_id=user.id
    )
    db.commit()
    return participation


@router.get("/admin/courses/{course_id}/deletion-impact", response_model=CourseDeletionImpact)
def course_deletion_impact(
    course_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.COURSES_DELETE)),
):
    """Chiffre l'ampleur d'une suppression **avant** de la commettre (FR-026).

    Gardée par `courses:delete` et non par un pouvoir de lecture : qui peut
    détruire peut mesurer, et l'inverse n'aurait pas d'usage.
    """
    return admin_actions.course_deletion_impact(db, course_id=course_id)


@router.delete("/admin/courses/{course_id}", status_code=204)
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.COURSES_DELETE)),
):
    """Supprime une épreuve, ses résultats et les fiches coureur qu'elle laisse vides.

    Irréversible et sans corps de réponse : ce qui reste du geste est son entrée
    au journal (FR-018).
    """
    admin_actions.delete_course(db, course_id=course_id, user_id=user.id)
    db.commit()


@router.patch("/admin/athletes/{athlete_id}", response_model=AdminAthleteRead)
def update_athlete(
    athlete_id: int,
    body: AdminAthleteUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.ATHLETES_WRITE)),
):
    """Corrige l'identité d'un coureur.

    `exclude_unset` et non `exclude_none` : `birth_date: null` est une mise à
    `NULL` légitime, et seule la présence du champ la distingue d'une absence.
    """
    athlete = admin_actions.update_athlete(
        db,
        athlete_id=athlete_id,
        champs=body.model_dump(exclude_unset=True),
        user_id=user.id,
    )
    db.commit()
    return _fiche(athlete)


@router.patch("/admin/courses/{course_id}", response_model=CourseBrief)
def update_course(
    course_id: int,
    body: AdminCourseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.COURSES_WRITE)),
):
    """Corrige le libellé d'une épreuve — les quatre champs de son identité."""
    course = admin_actions.update_course(
        db,
        course_id=course_id,
        champs=body.model_dump(exclude_unset=True),
        user_id=user.id,
    )
    db.commit()
    return course
