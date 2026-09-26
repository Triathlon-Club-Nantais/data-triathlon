"""Le calendrier des entraînements jeunes : consultation et gestion (#868,
epic #863).

Le modèle a d'abord été posé indépendamment du profil jeune (#867, en
parallèle) — `research.md` §Dépendance sur le profil jeune de la feature.
Depuis le merge de #867 dans `epic/863-jeunes`, `profile_id` référence
`personal_profiles.id` (contrainte de clé étrangère **et** vérification
Python ci-dessous — cf. `_ensure_profile_exists`).
"""
import logging

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.training_session import TrainingSession
from app.models.user import User
from app.repositories import profile_repository, training_session_repository

logger = logging.getLogger(__name__)


def get_training_session_or_404(db: Session, training_session_id: int) -> TrainingSession:
    training_session = training_session_repository.get(db, training_session_id)
    if training_session is None:
        raise NotFoundError("Cet entraînement n'existe pas.")
    return training_session


def _ensure_profile_exists(db: Session, profile_id: int) -> None:
    """Vérifie l'existence du profil **en Python**, avant l'écriture.

    `core/database.py` n'active `PRAGMA foreign_keys=ON` sur aucun moteur : la
    contrainte SQL sur `profile_id` serait muette en SQLite (dev, tests) et
    lèverait une `IntegrityError` non attrapée en PostgreSQL — un chemin
    d'écriture qui diverge entre les deux moteurs, le défaut que
    `services/auth/authorization.existing_organisation` évite déjà pour la même
    raison.
    """
    if profile_repository.get(db, profile_id) is None:
        raise NotFoundError("Ce profil n'existe pas.")


def training_session_view(training_session: TrainingSession, participant_count: int) -> dict:
    """La forme rendue par la liste, `contracts/api.md`."""
    return {
        "id": training_session.id,
        "date": training_session.date,
        "start_time": training_session.start_time,
        "location": training_session.location,
        "session_type": training_session.session_type,
        "note": training_session.note,
        "participant_count": participant_count,
    }


def training_session_detail_view(db: Session, training_session: TrainingSession) -> dict:
    """La forme rendue par le détail : l'entraînement **et** ses inscrits."""
    participants = training_session_repository.list_participants(db, training_session.id)
    return training_session_view(training_session, len(participants)) | {
        "participants": [
            {
                "profile_id": participant.profile_id,
                "present": participant.present,
                "created_at": participant.created_at,
            }
            for participant in participants
        ]
    }


def list_training_session_views(db: Session) -> list[dict]:
    """Toute la liste du calendrier en deux requêtes, quel que soit le nombre
    de séances : les séances, puis leurs comptes d'inscrits agrégés."""
    training_sessions = training_session_repository.list_all(db)
    comptes = training_session_repository.count_participants_by_training_session(
        db, [training_session.id for training_session in training_sessions]
    )
    return [
        training_session_view(training_session, comptes.get(training_session.id, 0))
        for training_session in training_sessions
    ]


def create_training_session(
    db: Session,
    actor: User,
    *,
    date,
    start_time=None,
    location: str | None = None,
    session_type: str | None = None,
) -> TrainingSession:
    """Crée un entraînement. Il naît sans participant, note vide (`""`) — la
    note de séance (#869) s'ajoute après coup via `update_training_session`,
    jamais à la création."""
    training_session = training_session_repository.create(
        db, date=date, start_time=start_time, location=location, session_type=session_type
    )
    logger.info(
        "Training session created: actor=%s training_session=%s date=%s", actor.id, training_session.id, date
    )
    return training_session


def update_training_session(
    db: Session,
    actor: User,
    training_session: TrainingSession,
    *,
    date=None,
    start_time=...,
    location=...,
    session_type=...,
    note=...,
) -> TrainingSession:
    """Corrige un entraînement. Seuls les champs fournis sont écrits."""
    training_session_repository.update(
        db,
        training_session,
        date=date,
        start_time=start_time,
        location=location,
        session_type=session_type,
        note=note,
    )
    logger.info("Training session updated: actor=%s training_session=%s", actor.id, training_session.id)
    return training_session


def add_participant(
    db: Session,
    actor: User,
    training_session: TrainingSession,
    *,
    profile_id: int,
    present: bool | None = None,
) -> None:
    """Inscrit un jeune. **Idempotent** — réinscrire est un succès.

    404 si le jeune n'existe pas (`_ensure_profile_exists`) — jamais laissé à la
    seule contrainte SQL. `present` (#869) pointe le jeune au même geste que
    son inscription — cf. `training_session_repository.add_participant`.
    """
    _ensure_profile_exists(db, profile_id)
    _, created = training_session_repository.add_participant(
        db, training_session_id=training_session.id, profile_id=profile_id, present=present
    )
    logger.info(
        "Participant added: actor=%s training_session=%s profile=%s new=%s present=%s",
        actor.id,
        training_session.id,
        profile_id,
        created,
        present,
    )


def set_presence(
    db: Session, actor: User, training_session: TrainingSession, *, profile_id: int, present: bool
) -> None:
    """Pointe un jeune déjà inscrit présent ou absent (#869, appel de début).

    404 si le jeune n'est pas inscrit à cette séance — cohérent avec le 404
    d'`add_participant` sur un profil inexistant : cette route ne crée jamais
    d'inscription.
    """
    resultat = training_session_repository.set_presence(
        db, training_session_id=training_session.id, profile_id=profile_id, present=present
    )
    if resultat is None:
        raise NotFoundError("Ce profil n'est pas inscrit à cette séance.")
    logger.info(
        "Presence set: actor=%s training_session=%s profile=%s present=%s",
        actor.id,
        training_session.id,
        profile_id,
        present,
    )


def remove_participant(
    db: Session, actor: User, training_session: TrainingSession, *, profile_id: int
) -> None:
    """Désinscrit un jeune. Idempotent — sans effet s'il n'était pas inscrit."""
    training_session_repository.remove_participant(
        db, training_session_id=training_session.id, profile_id=profile_id
    )
    logger.info(
        "Participant removed: actor=%s training_session=%s profile=%s",
        actor.id,
        training_session.id,
        profile_id,
    )
