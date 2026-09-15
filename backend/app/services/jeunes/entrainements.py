"""Le calendrier des entraînements jeunes : consultation et gestion (#868,
epic #863).

Modèle et routes posés indépendamment du détail du profil jeune (#867, en
parallèle) — `research.md` §Dépendance sur le profil jeune de la feature.
"""
import logging

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.entrainement import Entrainement
from app.models.user import User
from app.repositories import entrainement_repository

logger = logging.getLogger(__name__)


def get_entrainement_or_404(db: Session, entrainement_id: int) -> Entrainement:
    entrainement = entrainement_repository.get(db, entrainement_id)
    if entrainement is None:
        raise NotFoundError("Cet entraînement n'existe pas.")
    return entrainement


def entrainement_view(db: Session, entrainement: Entrainement) -> dict:
    """La forme rendue par la liste — `contracts/api.md`."""
    return {
        "id": entrainement.id,
        "date": entrainement.date,
        "heure_debut": entrainement.heure_debut,
        "lieu": entrainement.lieu,
        "type_seance": entrainement.type_seance,
        "participant_count": entrainement_repository.participant_count(db, entrainement.id),
    }


def entrainement_detail_view(db: Session, entrainement: Entrainement) -> dict:
    """La forme rendue par le détail : l'entraînement **et** ses inscrits."""
    return entrainement_view(db, entrainement) | {
        "participants": [
            {"jeune_id": participant.jeune_id, "created_at": participant.created_at}
            for participant in entrainement_repository.list_participants(db, entrainement.id)
        ]
    }


def list_entrainements(db: Session) -> list[Entrainement]:
    return entrainement_repository.list_all(db)


def create_entrainement(
    db: Session,
    actor: User,
    *,
    date,
    heure_debut=None,
    lieu: str | None = None,
    type_seance: str | None = None,
) -> Entrainement:
    """Crée un entraînement. Il naît sans participant."""
    entrainement = entrainement_repository.create(
        db, date=date, heure_debut=heure_debut, lieu=lieu, type_seance=type_seance
    )
    logger.info(
        "Entrainement created: actor=%s entrainement=%s date=%s", actor.id, entrainement.id, date
    )
    return entrainement


def update_entrainement(
    db: Session,
    actor: User,
    entrainement: Entrainement,
    *,
    date=None,
    heure_debut=...,
    lieu=...,
    type_seance=...,
) -> Entrainement:
    """Corrige un entraînement. Seuls les champs fournis sont écrits."""
    entrainement_repository.update(
        db,
        entrainement,
        date=date,
        heure_debut=heure_debut,
        lieu=lieu,
        type_seance=type_seance,
    )
    logger.info("Entrainement updated: actor=%s entrainement=%s", actor.id, entrainement.id)
    return entrainement


def add_participant(
    db: Session, actor: User, entrainement: Entrainement, *, jeune_id: int
) -> None:
    """Inscrit un jeune. **Idempotent** — réinscrire est un succès."""
    _, created = entrainement_repository.add_participant(
        db, entrainement_id=entrainement.id, jeune_id=jeune_id
    )
    logger.info(
        "Participant added: actor=%s entrainement=%s jeune=%s new=%s",
        actor.id,
        entrainement.id,
        jeune_id,
        created,
    )


def remove_participant(
    db: Session, actor: User, entrainement: Entrainement, *, jeune_id: int
) -> None:
    """Désinscrit un jeune. Idempotent — sans effet s'il n'était pas inscrit."""
    entrainement_repository.remove_participant(
        db, entrainement_id=entrainement.id, jeune_id=jeune_id
    )
    logger.info(
        "Participant removed: actor=%s entrainement=%s jeune=%s",
        actor.id,
        entrainement.id,
        jeune_id,
    )
