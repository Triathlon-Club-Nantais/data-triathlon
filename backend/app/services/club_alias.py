"""Édition du registre d'alias de club (#635).

Généralise pour tous les clubs le mécanisme de fusion des variantes livré
pour le TCN (#215) — indépendant de `counter_scope.club_labels`/`is_tcn`, qui
reste réservé au comptage `scope=club`. Design :
`docs/superpowers/specs/2026-08-30-fusion-variantes-club-design.md`.
"""
from sqlalchemy.orm import Session

from app.core.club import normalize_club
from app.core.exceptions import DomainError, DuplicateError, NotFoundError
from app.models.club_alias import ClubAlias
from app.repositories import club_alias_repository


def add_entry(
    db: Session, *, canonical_name: str, alias: str, admin_user_id: int | None
) -> ClubAlias:
    """Rattache un alias à un nom canonique. Crée le groupe s'il n'existe pas
    encore : un « club canonique » n'est que le regroupement des lignes qui
    partagent le même `canonical_name` (cf. modèle)."""
    nom = canonical_name.strip()
    if not nom:
        raise DomainError("Le nom canonique ne peut pas être vide.")

    alias_normalise = normalize_club(alias)
    if not alias_normalise:
        raise DomainError("L'alias ne peut pas être vide.")

    if club_alias_repository.find_by_alias(db, alias_normalized=alias_normalise) is not None:
        raise DuplicateError(f"« {alias_normalise} » est déjà rattaché à un club.")

    entry = club_alias_repository.create_entry(
        db, canonical_name=nom, alias_normalized=alias_normalise, created_by_user_id=admin_user_id
    )
    db.flush()
    return entry


def remove_entry(db: Session, *, entry_id: int) -> ClubAlias:
    """Retire un alias. Aucune protection « dernier alias » : contrairement au
    dernier libellé TCN, retirer le seul alias d'un groupe ne fait tomber
    aucun compteur à zéro — ce club revient simplement à son libellé brut."""
    entry = club_alias_repository.get_entry(db, entry_id=entry_id)
    if entry is None:
        raise NotFoundError("Cet alias n'existe pas.")

    club_alias_repository.delete_entry(db, entry)
    db.flush()
    return entry
