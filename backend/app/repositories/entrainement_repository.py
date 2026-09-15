"""Accès données pour Entrainement et EntrainementParticipant — seule couche
qui touche la Session (#868, epic #863).

La transaction reste portée par le service appelant
(`services/jeunes/entrainements.py`) : on `flush()` pour peupler l'id, on ne
`commit()` jamais ici — même patron que `group_repository.py`.
"""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entrainement import Entrainement
from app.models.entrainement_participant import EntrainementParticipant


def get(db: Session, entrainement_id: int) -> Entrainement | None:
    return db.get(Entrainement, entrainement_id)


def list_all(db: Session) -> list[Entrainement]:
    """Les entraînements, triés par date puis heure de début.

    Une séance sans heure renseignée sort en **fin** de sa date : l'ordre
    `Entrainement.heure_debut.is_(None)` place d'abord les séances à heure
    connue (`False` < `True`), sur le même patron que l'ordre de finisseurs de
    `participation_repository._ordre_affichage`.
    """
    return list(
        db.scalars(
            select(Entrainement).order_by(
                Entrainement.date,
                Entrainement.heure_debut.is_(None),
                Entrainement.heure_debut,
            )
        )
    )


def participant_count(db: Session, entrainement_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(EntrainementParticipant)
        .where(EntrainementParticipant.entrainement_id == entrainement_id)
    )


def list_participants(db: Session, entrainement_id: int) -> list[EntrainementParticipant]:
    """Les participants inscrits, dans l'ordre d'inscription."""
    return list(
        db.scalars(
            select(EntrainementParticipant)
            .where(EntrainementParticipant.entrainement_id == entrainement_id)
            .order_by(EntrainementParticipant.created_at)
        )
    )


def create(
    db: Session,
    *,
    date,
    heure_debut=None,
    lieu: str | None = None,
    type_seance: str | None = None,
) -> Entrainement:
    entrainement = Entrainement(
        date=date, heure_debut=heure_debut, lieu=lieu, type_seance=type_seance
    )
    db.add(entrainement)
    db.flush()
    return entrainement


def update(
    db: Session,
    entrainement: Entrainement,
    *,
    date=None,
    heure_debut=...,
    lieu=...,
    type_seance=...,
    note=...,
) -> Entrainement:
    """Écrit uniquement les champs fournis.

    `heure_debut`/`lieu`/`type_seance`/`note` acceptent explicitement `None`
    comme valeur voulue (effacer le champ) — le défaut `...` (sentinelle)
    distingue « champ absent du `PATCH` » de « champ remis à vide », que
    `None` seul ne pourrait pas distinguer.
    """
    if date is not None:
        entrainement.date = date
    if heure_debut is not ...:
        entrainement.heure_debut = heure_debut
    if lieu is not ...:
        entrainement.lieu = lieu
    if type_seance is not ...:
        entrainement.type_seance = type_seance
    if note is not ...:
        entrainement.note = note
    db.flush()
    return entrainement


def find_participant(
    db: Session, *, entrainement_id: int, jeune_id: int
) -> EntrainementParticipant | None:
    return db.scalar(
        select(EntrainementParticipant).where(
            EntrainementParticipant.entrainement_id == entrainement_id,
            EntrainementParticipant.jeune_id == jeune_id,
        )
    )


def add_participant(
    db: Session, *, entrainement_id: int, jeune_id: int, present: bool | None = None
) -> tuple[EntrainementParticipant, bool]:
    """Inscrit le jeune. Rend `(inscription, créée)` — **idempotent**.

    L'insertion est tentée d'abord, sous point de reprise : une lecture
    préalable serait franchie par deux exploitants simultanés, là où
    `UNIQUE(entrainement_id, jeune_id)` ne l'est jamais — reprise exacte de
    `group_repository.add_member`.

    `present` (#869) permet d'inscrire un jeune et de le pointer présent en
    un seul geste, pendant l'appel — généralisation du paramètre, jamais un
    second chemin d'écriture (research.md D4). Fourni sur une inscription déjà
    existante, il met aussi à jour son statut : re-pointer quelqu'un déjà
    inscrit reste le même geste, idempotent des deux côtés.
    """
    inscription = EntrainementParticipant(
        entrainement_id=entrainement_id, jeune_id=jeune_id, present=present
    )
    try:
        with db.begin_nested():
            db.add(inscription)
            db.flush()
    except IntegrityError:
        existante = find_participant(db, entrainement_id=entrainement_id, jeune_id=jeune_id)
        if existante is None:  # pragma: no cover — une autre contrainte a cédé
            raise
        if present is not None:
            existante.present = present
            db.flush()
        return existante, False
    return inscription, True


def set_presence(
    db: Session, *, entrainement_id: int, jeune_id: int, present: bool
) -> EntrainementParticipant | None:
    """Bascule le statut de présence d'une inscription déjà existante (#869).

    Rend `None` si le jeune n'est pas inscrit à cette séance — cette fonction
    ne crée jamais d'inscription (`add_participant` s'en charge), elle ne
    modifie qu'une ligne déjà existante. Seul le dernier statut écrit fait
    foi (FR-005) : aucun historique des changements.
    """
    inscription = find_participant(db, entrainement_id=entrainement_id, jeune_id=jeune_id)
    if inscription is None:
        return None
    inscription.present = present
    db.flush()
    return inscription


def remove_participant(db: Session, *, entrainement_id: int, jeune_id: int) -> bool:
    """Désinscrit le jeune. Rend `False` s'il ne l'était pas — jamais d'erreur."""
    inscription = find_participant(db, entrainement_id=entrainement_id, jeune_id=jeune_id)
    if inscription is None:
        return False
    db.delete(inscription)
    db.flush()
    return True
