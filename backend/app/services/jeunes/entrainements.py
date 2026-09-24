"""Le calendrier des entraînements jeunes : consultation et gestion (#868,
epic #863).

Le modèle a d'abord été posé indépendamment du profil jeune (#867, en
parallèle) — `research.md` §Dépendance sur le profil jeune de la feature.
Depuis le merge de #867 dans `epic/863-jeunes`, `jeune_id` référence
`personal_profiles.id` (contrainte de clé étrangère **et** vérification
Python ci-dessous — cf. `_jeune_existant`).
"""
import logging

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.entrainement import Entrainement
from app.models.user import User
from app.repositories import entrainement_repository, profile_repository

logger = logging.getLogger(__name__)


def get_entrainement_or_404(db: Session, entrainement_id: int) -> Entrainement:
    entrainement = entrainement_repository.get(db, entrainement_id)
    if entrainement is None:
        raise NotFoundError("Cet entraînement n'existe pas.")
    return entrainement


def _jeune_existant(db: Session, jeune_id: int) -> None:
    """Vérifie l'existence du profil **en Python**, avant l'écriture.

    `core/database.py` n'active `PRAGMA foreign_keys=ON` sur aucun moteur : la
    contrainte SQL sur `jeune_id` serait muette en SQLite (dev, tests) et
    lèverait une `IntegrityError` non attrapée en PostgreSQL — un chemin
    d'écriture qui diverge entre les deux moteurs, le défaut que
    `services/auth/groups._existing_organisation` évite déjà pour la même
    raison.
    """
    if profile_repository.get(db, jeune_id) is None:
        raise NotFoundError("Ce jeune n'existe pas.")


def entrainement_view(entrainement: Entrainement, participant_count: int) -> dict:
    """La forme rendue par la liste, `contracts/api.md`."""
    return {
        "id": entrainement.id,
        "date": entrainement.date,
        "heure_debut": entrainement.heure_debut,
        "lieu": entrainement.lieu,
        "type_seance": entrainement.type_seance,
        "note": entrainement.note,
        "participant_count": participant_count,
    }


def entrainement_detail_view(db: Session, entrainement: Entrainement) -> dict:
    """La forme rendue par le détail : l'entraînement **et** ses inscrits."""
    participants = entrainement_repository.list_participants(db, entrainement.id)
    return entrainement_view(entrainement, len(participants)) | {
        "participants": [
            {
                "jeune_id": participant.jeune_id,
                "present": participant.present,
                "created_at": participant.created_at,
            }
            for participant in participants
        ]
    }


def list_entrainement_views(db: Session) -> list[dict]:
    """Toute la liste du calendrier en deux requêtes, quel que soit le nombre
    de séances : les séances, puis leurs comptes d'inscrits agrégés."""
    entrainements = entrainement_repository.list_all(db)
    comptes = entrainement_repository.count_participants_by_entrainement(
        db, [entrainement.id for entrainement in entrainements]
    )
    return [
        entrainement_view(entrainement, comptes.get(entrainement.id, 0))
        for entrainement in entrainements
    ]


def create_entrainement(
    db: Session,
    actor: User,
    *,
    date,
    heure_debut=None,
    lieu: str | None = None,
    type_seance: str | None = None,
) -> Entrainement:
    """Crée un entraînement. Il naît sans participant, note vide (`""`) — la
    note de séance (#869) s'ajoute après coup via `update_entrainement`,
    jamais à la création."""
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
    note=...,
) -> Entrainement:
    """Corrige un entraînement. Seuls les champs fournis sont écrits."""
    entrainement_repository.update(
        db,
        entrainement,
        date=date,
        heure_debut=heure_debut,
        lieu=lieu,
        type_seance=type_seance,
        note=note,
    )
    logger.info("Entrainement updated: actor=%s entrainement=%s", actor.id, entrainement.id)
    return entrainement


def add_participant(
    db: Session,
    actor: User,
    entrainement: Entrainement,
    *,
    jeune_id: int,
    present: bool | None = None,
) -> None:
    """Inscrit un jeune. **Idempotent** — réinscrire est un succès.

    404 si le jeune n'existe pas (`_jeune_existant`) — jamais laissé à la
    seule contrainte SQL. `present` (#869) pointe le jeune au même geste que
    son inscription — cf. `entrainement_repository.add_participant`.
    """
    _jeune_existant(db, jeune_id)
    _, created = entrainement_repository.add_participant(
        db, entrainement_id=entrainement.id, jeune_id=jeune_id, present=present
    )
    logger.info(
        "Participant added: actor=%s entrainement=%s jeune=%s new=%s present=%s",
        actor.id,
        entrainement.id,
        jeune_id,
        created,
        present,
    )


def set_presence(
    db: Session, actor: User, entrainement: Entrainement, *, jeune_id: int, present: bool
) -> None:
    """Pointe un jeune déjà inscrit présent ou absent (#869, appel de début).

    404 si le jeune n'est pas inscrit à cette séance — cohérent avec le 404
    d'`add_participant` sur un profil inexistant : cette route ne crée jamais
    d'inscription.
    """
    resultat = entrainement_repository.set_presence(
        db, entrainement_id=entrainement.id, jeune_id=jeune_id, present=present
    )
    if resultat is None:
        raise NotFoundError("Ce jeune n'est pas inscrit à cet entraînement.")
    logger.info(
        "Presence set: actor=%s entrainement=%s jeune=%s present=%s",
        actor.id,
        entrainement.id,
        jeune_id,
        present,
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
