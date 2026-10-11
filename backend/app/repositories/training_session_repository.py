"""Accès données pour TrainingSession et TrainingParticipant — seule couche
qui touche la Session (#868, epic #863).

La transaction reste portée par le service appelant
(`services/training_session_service.py`) : on `flush()` pour peupler l'id, on ne
`commit()` jamais ici — même patron que `group_repository.py`.
"""
from datetime import date as date_

from sqlalchemy import delete, func, select
from sqlalchemy import update as sql_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.training_group import TrainingGroup, TrainingGroupMember
from app.models.training_participant import TrainingParticipant
from app.models.training_recurrence import training_session_groups
from app.models.training_session import TrainingSession


def get(db: Session, training_session_id: int) -> TrainingSession | None:
    return db.get(TrainingSession, training_session_id)


def list_all(db: Session) -> list[TrainingSession]:
    """Les entraînements, triés par date puis heure de début.

    Une séance sans heure renseignée sort en **fin** de sa date : l'ordre
    `TrainingSession.start_time.is_(None)` place d'abord les séances à heure
    connue (`False` < `True`), sur le même patron que l'ordre de finisseurs de
    `participation_repository._ordre_affichage`.
    """
    return list(
        db.scalars(
            select(TrainingSession)
            .options(selectinload(TrainingSession.groups))
            .order_by(
                TrainingSession.date,
                TrainingSession.start_time.is_(None),
                TrainingSession.start_time,
            )
        )
    )


def count_participants_by_training_session(
    db: Session, training_session_ids: list[int]
) -> dict[int, int]:
    """Le nombre d'inscrits par séance, en une seule requête agrégée, pour la
    liste du calendrier (patron `role_repository.count_holders_by_role`). Une
    séance absente du résultat n'a aucun inscrit."""
    if not training_session_ids:
        return {}
    lignes = db.execute(
        select(TrainingParticipant.training_session_id, func.count())
        .where(TrainingParticipant.training_session_id.in_(training_session_ids))
        .group_by(TrainingParticipant.training_session_id)
    ).all()
    return dict(lignes)


def list_participants(db: Session, training_session_id: int) -> list[TrainingParticipant]:
    """Les participants inscrits, dans l'ordre d'inscription."""
    return list(
        db.scalars(
            select(TrainingParticipant)
            .options(selectinload(TrainingParticipant.profile))
            .where(TrainingParticipant.training_session_id == training_session_id)
            .order_by(TrainingParticipant.created_at)
        )
    )


def create(
    db: Session,
    *,
    date,
    start_time=None,
    location: str | None = None,
    session_type: str | None = None,
    recurrence_id: int | None = None,
) -> TrainingSession:
    training_session = TrainingSession(
        date=date,
        start_time=start_time,
        location=location,
        session_type=session_type,
        recurrence_id=recurrence_id,
    )
    db.add(training_session)
    db.flush()
    return training_session


def update(
    db: Session,
    training_session: TrainingSession,
    *,
    date=None,
    start_time=...,
    location=...,
    session_type=...,
    note=...,
) -> TrainingSession:
    """Écrit uniquement les champs fournis.

    `start_time`/`location`/`session_type`/`note` acceptent explicitement `None`
    comme valeur voulue (effacer le champ) — le défaut `...` (sentinelle)
    distingue « champ absent du `PATCH` » de « champ remis à vide », que
    `None` seul ne pourrait pas distinguer.
    """
    if date is not None:
        training_session.date = date
    if start_time is not ...:
        training_session.start_time = start_time
    if location is not ...:
        training_session.location = location
    if session_type is not ...:
        training_session.session_type = session_type
    if note is not ...:
        training_session.note = note
    db.flush()
    return training_session


def delete_training_session(db: Session, training_session: TrainingSession) -> None:
    """Supprime la séance ; ses inscriptions partent avec elle par la cascade
    ORM `delete-orphan` de `TrainingSession.participants`."""
    db.delete(training_session)
    db.flush()


def find_participant(
    db: Session, *, training_session_id: int, profile_id: int
) -> TrainingParticipant | None:
    return db.scalar(
        select(TrainingParticipant).where(
            TrainingParticipant.training_session_id == training_session_id,
            TrainingParticipant.profile_id == profile_id,
        )
    )


def add_participant(
    db: Session,
    *,
    training_session_id: int,
    profile_id: int,
    present: bool | None = None,
    added_manually: bool = True,
) -> tuple[TrainingParticipant, bool]:
    """Inscrit le jeune. Rend `(inscription, créée)` — **idempotent**.

    L'insertion est tentée d'abord, sous point de reprise : une lecture
    préalable serait franchie par deux exploitants simultanés, là où
    `UNIQUE(training_session_id, profile_id)` ne l'est jamais — reprise exacte de
    `group_repository.add_member`.

    `present` (#869) permet d'inscrire un jeune et de le pointer présent en
    un seul geste, pendant l'appel — généralisation du paramètre, jamais un
    second chemin d'écriture (research.md D4). Fourni sur une inscription déjà
    existante, il met aussi à jour son statut : re-pointer quelqu'un déjà
    inscrit reste le même geste, idempotent des deux côtés.

    `added_manually` (#1291) : un ajout manuel d'un jeune déjà inscrit d'office
    rend l'inscription manuelle ; l'inverse ne la rétrograde jamais.
    """
    inscription = TrainingParticipant(
        training_session_id=training_session_id,
        profile_id=profile_id,
        present=present,
        added_manually=added_manually,
    )
    try:
        with db.begin_nested():
            db.add(inscription)
            db.flush()
    except IntegrityError:
        existante = find_participant(db, training_session_id=training_session_id, profile_id=profile_id)
        if existante is None:  # pragma: no cover — une autre contrainte a cédé
            raise
        if present is not None:
            existante.present = present
        if added_manually:
            existante.added_manually = True
        db.flush()
        return existante, False
    return inscription, True


def set_presence(
    db: Session, *, training_session_id: int, profile_id: int, present: bool
) -> TrainingParticipant | None:
    """Bascule le statut de présence d'une inscription déjà existante (#869).

    Rend `None` si le jeune n'est pas inscrit à cette séance — cette fonction
    ne crée jamais d'inscription (`add_participant` s'en charge), elle ne
    modifie qu'une ligne déjà existante. Seul le dernier statut écrit fait
    foi (FR-005) : aucun historique des changements.
    """
    inscription = find_participant(db, training_session_id=training_session_id, profile_id=profile_id)
    if inscription is None:
        return None
    inscription.present = present
    db.flush()
    return inscription


def remove_participant(db: Session, *, training_session_id: int, profile_id: int) -> bool:
    """Désinscrit le jeune. Rend `False` s'il ne l'était pas — jamais d'erreur."""
    inscription = find_participant(db, training_session_id=training_session_id, profile_id=profile_id)
    if inscription is None:
        return False
    db.delete(inscription)
    db.flush()
    return True


def delete_participations_of_profile(db: Session, profile_id: int) -> int:
    """Retire toutes les présences d'un profil purgé (#1158)."""
    return db.execute(delete(TrainingParticipant).where(TrainingParticipant.profile_id == profile_id)).rowcount


def set_groups(db: Session, training_session: TrainingSession, groups: list[TrainingGroup]) -> None:
    training_session.groups = groups
    db.flush()


def roll_call_started(db: Session, training_session_id: int) -> bool:
    """« Appel commencé » : au moins un statut de présence saisi (#1291)."""
    return db.scalar(
        select(
            select(TrainingParticipant.id)
            .where(
                TrainingParticipant.training_session_id == training_session_id,
                TrainingParticipant.present.is_not(None),
            )
            .exists()
        )
    )


def roll_call_started_among(db: Session, training_session_ids: list[int]) -> set[int]:
    """Parmi ces séances, celles dont l'appel a commencé, en une requête."""
    if not training_session_ids:
        return set()
    return set(
        db.scalars(
            select(TrainingParticipant.training_session_id)
            .where(
                TrainingParticipant.training_session_id.in_(training_session_ids),
                TrainingParticipant.present.is_not(None),
            )
            .distinct()
        )
    )


def list_upcoming_targeting_group(db: Session, training_group_id: int, *, today: date_) -> list[TrainingSession]:
    return list(
        db.scalars(
            select(TrainingSession)
            .join(training_session_groups, training_session_groups.c.training_session_id == TrainingSession.id)
            .where(training_session_groups.c.training_group_id == training_group_id, TrainingSession.date >= today)
        )
    )


def make_group_enrolments_manual(db: Session, training_group_id: int) -> None:
    """Avant la suppression d'un groupe : ses inscriptions d'office deviennent
    manuelles, pour qu'aucune resynchronisation ultérieure ne les retire."""
    db.execute(
        sql_update(TrainingParticipant)
        .where(
            TrainingParticipant.added_manually.is_(False),
            TrainingParticipant.training_session_id.in_(
                select(training_session_groups.c.training_session_id).where(
                    training_session_groups.c.training_group_id == training_group_id
                )
            ),
            TrainingParticipant.profile_id.in_(
                select(TrainingGroupMember.profile_id).where(
                    TrainingGroupMember.training_group_id == training_group_id
                )
            ),
        )
        .values(added_manually=True)
        .execution_options(synchronize_session="fetch")
    )


def mark_detached(db: Session, training_session: TrainingSession) -> None:
    training_session.detached = True
    db.flush()


def unlink_from_recurrence(db: Session, training_session: TrainingSession) -> None:
    training_session.recurrence_id = None
    db.flush()
