"""Router du calendrier des entraînements jeunes (#868, epic #863) et de
l'appel de présence (#869).

Six ressources, deux pouvoirs : `jeunes:read` pour les deux lectures,
`jeunes:write` pour le cycle de vie d'un entraînement, sa liste de
participants et leur statut de présence — même patron que `admin_groups.py`.
Aucune route n'est protégée par son préfixe : chaque route porte sa garde
individuellement.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.schemas.training_session import (
    ParticipantAdd,
    PresenceUpdate,
    TrainingSessionCreate,
    TrainingSessionDetailRead,
    TrainingSessionRead,
    TrainingSessionUpdate,
)
from app.services import training_session_service

router = APIRouter(tags=["admin"])


@router.get("/admin/training-sessions", response_model=list[TrainingSessionRead])
def list_training_sessions(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.JEUNES_READ)),
):
    """Les entraînements, triés par date puis heure de début."""
    return training_session_service.list_training_session_views(db)


@router.get(
    "/admin/training-sessions/{training_session_id}", response_model=TrainingSessionDetailRead
)
def get_training_session(
    training_session_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.JEUNES_READ)),
):
    """Un entraînement **et sa liste de participants inscrits**."""
    training_session = training_session_service.get_training_session_or_404(db, training_session_id)
    return training_session_service.training_session_detail_view(db, training_session)


@router.post(
    "/admin/training-sessions", response_model=TrainingSessionDetailRead, status_code=201
)
def create_training_session(
    body: TrainingSessionCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    """Crée un entraînement. Il naît sans participant."""
    training_session = training_session_service.create_training_session(
        db,
        actor,
        date=body.date,
        start_time=body.start_time,
        location=body.location,
        session_type=body.session_type,
    )
    view = training_session_service.training_session_detail_view(db, training_session)
    db.commit()
    return view


@router.patch(
    "/admin/training-sessions/{training_session_id}", response_model=TrainingSessionDetailRead
)
def update_training_session(
    training_session_id: int,
    body: TrainingSessionUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    """Corrige la date, l'heure, le lieu, le type ou la note. Seuls les
    champs fournis sont écrits."""
    training_session = training_session_service.get_training_session_or_404(db, training_session_id)
    champs_fournis = body.model_dump(exclude_unset=True)
    # `note` n'est pas nullable côté modèle : un `null` explicite (sans
    # objet réel — « pas de note » se dit `""`) est traité comme « champ
    # absent », jamais comme une tentative d'écrire `NULL` en base.
    note_fournie = champs_fournis.get("note", ...)
    if note_fournie is None:
        note_fournie = ...
    training_session_service.update_training_session(
        db,
        actor,
        training_session,
        date=champs_fournis.get("date"),
        start_time=champs_fournis.get("start_time", ...),
        location=champs_fournis.get("location", ...),
        session_type=champs_fournis.get("session_type", ...),
        note=note_fournie,
    )
    view = training_session_service.training_session_detail_view(db, training_session)
    db.commit()
    return view


@router.post(
    "/admin/training-sessions/{training_session_id}/participants",
    response_model=TrainingSessionDetailRead,
    status_code=201,
)
def add_participant(
    training_session_id: int,
    body: ParticipantAdd,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    """Inscrit un jeune. **Idempotent** — réinscrire est un succès.

    `present` (#869) le pointe au même geste, pendant l'appel de début."""
    training_session = training_session_service.get_training_session_or_404(db, training_session_id)
    training_session_service.add_participant(
        db, actor, training_session, profile_id=body.profile_id, present=body.present
    )
    view = training_session_service.training_session_detail_view(db, training_session)
    db.commit()
    return view


@router.delete(
    "/admin/training-sessions/{training_session_id}/participants/{profile_id}",
    status_code=204,
)
def remove_participant(
    training_session_id: int,
    profile_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    """Désinscrit un jeune. Idempotent — sans effet s'il n'était pas inscrit."""
    training_session = training_session_service.get_training_session_or_404(db, training_session_id)
    training_session_service.remove_participant(db, actor, training_session, profile_id=profile_id)
    db.commit()


@router.patch(
    "/admin/training-sessions/{training_session_id}/participants/{profile_id}/presence",
    response_model=TrainingSessionDetailRead,
)
def set_presence(
    training_session_id: int,
    profile_id: int,
    body: PresenceUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    """Pointe un jeune déjà inscrit présent ou absent (#869, appel de début).

    404 si le jeune n'est pas inscrit à cette séance — cette route ne crée
    jamais d'inscription (`POST .../participants` s'en charge)."""
    training_session = training_session_service.get_training_session_or_404(db, training_session_id)
    training_session_service.set_presence(
        db, actor, training_session, profile_id=profile_id, present=body.present
    )
    view = training_session_service.training_session_detail_view(db, training_session)
    db.commit()
    return view
