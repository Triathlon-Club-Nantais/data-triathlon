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
from app.schemas.entrainement import (
    EntrainementCreate,
    EntrainementDetailRead,
    EntrainementRead,
    EntrainementUpdate,
    ParticipantAdd,
    PresenceUpdate,
)
from app.services.jeunes import entrainements as entrainement_service

router = APIRouter(tags=["admin"])


@router.get("/admin/jeunes/entrainements", response_model=list[EntrainementRead])
def list_entrainements(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.JEUNES_READ)),
):
    """Les entraînements, triés par date puis heure de début."""
    return [
        entrainement_service.entrainement_view(db, entrainement)
        for entrainement in entrainement_service.list_entrainements(db)
    ]


@router.get(
    "/admin/jeunes/entrainements/{entrainement_id}", response_model=EntrainementDetailRead
)
def get_entrainement(
    entrainement_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.JEUNES_READ)),
):
    """Un entraînement **et sa liste de participants inscrits**."""
    entrainement = entrainement_service.get_entrainement_or_404(db, entrainement_id)
    return entrainement_service.entrainement_detail_view(db, entrainement)


@router.post(
    "/admin/jeunes/entrainements", response_model=EntrainementDetailRead, status_code=201
)
def create_entrainement(
    body: EntrainementCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    """Crée un entraînement. Il naît sans participant."""
    entrainement = entrainement_service.create_entrainement(
        db,
        actor,
        date=body.date,
        heure_debut=body.heure_debut,
        lieu=body.lieu,
        type_seance=body.type_seance,
    )
    view = entrainement_service.entrainement_detail_view(db, entrainement)
    db.commit()
    return view


@router.patch(
    "/admin/jeunes/entrainements/{entrainement_id}", response_model=EntrainementDetailRead
)
def update_entrainement(
    entrainement_id: int,
    body: EntrainementUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    """Corrige la date, l'heure, le lieu, le type ou la note. Seuls les
    champs fournis sont écrits."""
    entrainement = entrainement_service.get_entrainement_or_404(db, entrainement_id)
    champs_fournis = body.model_dump(exclude_unset=True)
    # `note` n'est pas nullable côté modèle : un `null` explicite (sans
    # objet réel — « pas de note » se dit `""`) est traité comme « champ
    # absent », jamais comme une tentative d'écrire `NULL` en base.
    note_fournie = champs_fournis.get("note", ...)
    if note_fournie is None:
        note_fournie = ...
    entrainement_service.update_entrainement(
        db,
        actor,
        entrainement,
        date=champs_fournis.get("date"),
        heure_debut=champs_fournis.get("heure_debut", ...),
        lieu=champs_fournis.get("lieu", ...),
        type_seance=champs_fournis.get("type_seance", ...),
        note=note_fournie,
    )
    view = entrainement_service.entrainement_detail_view(db, entrainement)
    db.commit()
    return view


@router.post(
    "/admin/jeunes/entrainements/{entrainement_id}/participants",
    response_model=EntrainementDetailRead,
    status_code=201,
)
def add_participant(
    entrainement_id: int,
    body: ParticipantAdd,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    """Inscrit un jeune. **Idempotent** — réinscrire est un succès.

    `present` (#869) le pointe au même geste, pendant l'appel de début."""
    entrainement = entrainement_service.get_entrainement_or_404(db, entrainement_id)
    entrainement_service.add_participant(
        db, actor, entrainement, jeune_id=body.jeune_id, present=body.present
    )
    view = entrainement_service.entrainement_detail_view(db, entrainement)
    db.commit()
    return view


@router.delete(
    "/admin/jeunes/entrainements/{entrainement_id}/participants/{jeune_id}",
    status_code=204,
)
def remove_participant(
    entrainement_id: int,
    jeune_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    """Désinscrit un jeune. Idempotent — sans effet s'il n'était pas inscrit."""
    entrainement = entrainement_service.get_entrainement_or_404(db, entrainement_id)
    entrainement_service.remove_participant(db, actor, entrainement, jeune_id=jeune_id)
    db.commit()


@router.patch(
    "/admin/jeunes/entrainements/{entrainement_id}/participants/{jeune_id}/presence",
    response_model=EntrainementDetailRead,
)
def set_presence(
    entrainement_id: int,
    jeune_id: int,
    body: PresenceUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    """Pointe un jeune déjà inscrit présent ou absent (#869, appel de début).

    404 si le jeune n'est pas inscrit à cette séance — cette route ne crée
    jamais d'inscription (`POST .../participants` s'en charge)."""
    entrainement = entrainement_service.get_entrainement_or_404(db, entrainement_id)
    entrainement_service.set_presence(
        db, actor, entrainement, jeune_id=jeune_id, present=body.present
    )
    view = entrainement_service.entrainement_detail_view(db, entrainement)
    db.commit()
    return view
