"""Séparer une fiche qui porte plusieurs personnes du même nom (#1209).

Les résultats choisis partent sur une nouvelle fiche d'homonyme, chacun par le
rattachement admin (`admin_actions.reassign_participation` : verrou d'épreuve,
refus d'un doublon sur une épreuve, résultat verrouillé contre les imports, et
recalcul de `counts_for_tcn` pour les deux fiches).
La paire est enregistrée comme distincte : sans elle, la reprise
`reconcile-athletes` (famille `same_key`) refusionnerait les deux fiches.
"""
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.models.athlete import Athlete
from app.repositories import (
    athlete_repository,
    ignored_athlete_pair_repository,
    participation_repository,
)
from app.services import admin_actions, audit


def detach_participations(
    db: Session, *, athlete_id: int, participation_ids: list[int], user_id: int
) -> Athlete:
    """Déplace `participation_ids` de la fiche `athlete_id` vers une nouvelle fiche
    d'homonyme et rend celle-ci. `flush` sans `commit` : la route clôt."""
    ids = list(dict.fromkeys(participation_ids))
    if not ids:
        raise DomainError("Choisissez au moins un résultat à séparer.")
    source = athlete_repository.get(db, athlete_id)
    if source is None:
        raise NotFoundError("Athlète introuvable.")
    participations = []
    for participation_id in ids:
        participation = participation_repository.get(db, participation_id)
        if participation is None:
            raise NotFoundError("Résultat introuvable.")
        if participation.athlete_id != source.id:
            raise DomainError("Ce résultat n'appartient pas à cette fiche.")
        participations.append(participation)
    if participation_repository.count_for_athlete(db, source.id) <= len(participations):
        raise DomainError("La fiche doit garder au moins un résultat : ce serait une fusion inverse.")

    latest = max(participations, key=lambda p: (p.course.event_date is not None, p.course.event_date, p.id))
    created = athlete_repository.create_homonym(db, {
        "nom": source.nom, "prenom": source.prenom, "gender": source.gender, "club": latest.club,
    })
    for participation in participations:
        admin_actions.reassign_participation(
            db, participation_id=participation.id, athlete_id=created.id, user_id=user_id
        )
    ignored_athlete_pair_repository.create(db, athlete_id_a=source.id, athlete_id_b=created.id, user_id=user_id)
    audit.record(
        db, user_id, action="athlete.detach", entity_type="athlete", entity_id=source.id,
        payload={"from_athlete_id": source.id, "to_athlete_id": created.id, "participation_ids": ids},
    )
    return created
