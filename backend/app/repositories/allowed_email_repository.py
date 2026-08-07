"""Accès données pour AllowedEmail — seule couche qui touche la Session (#170).

La transaction reste portée par le service appelant (`services/auth/`), comme
partout ailleurs : on `flush()` pour peupler l'id, on ne `commit()` jamais ici.

**La normalisation vit ici**, et pas chez les appelants : le repository est le
point de passage unique de cette table, et c'est elle qui rend le `UNIQUE`
suffisant. La disperser chez les trois appelants — l'écran, la CLI, la
connexion — la ferait diverger au premier oubli.
"""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.allowed_email import AllowedEmail


def normalize(email: str) -> str:
    """Forme rangée d'une adresse : minuscules, espaces de bordure retirés."""
    return email.strip().lower()


def exists(db: Session, email: str) -> bool:
    """Cette adresse est-elle autorisée ? Lue à chaque tentative, **sans cache**.

    C'est la propriété qui *est* la feature (#170) : la liste vivait dans un
    `Settings` en `lru_cache`, et c'est ce cache qui imposait un redéploiement
    pour ajouter un contributeur. Un cache TTL, même court, le recréerait sous
    une forme plus difficile à diagnostiquer.
    """
    return (
        db.scalar(select(AllowedEmail.id).where(AllowedEmail.email == normalize(email)))
        is not None
    )


def list_all(db: Session) -> list[AllowedEmail]:
    """Toutes les adresses, par ordre alphabétique. **Sans pagination**, et c'est borné.

    Le peuplement est celui d'un club : quelques dizaines d'entrées, saisies à la
    main. L'auteur est chargé dans la même requête — l'écran l'affiche sur chaque
    ligne, et une requête par ligne serait un N+1 pour rien.
    """
    return list(
        db.scalars(
            select(AllowedEmail)
            .options(joinedload(AllowedEmail.created_by))
            .order_by(AllowedEmail.email)
        )
    )


def get(db: Session, entry_id: int) -> AllowedEmail | None:
    return db.get(AllowedEmail, entry_id)


def add(
    db: Session, *, email: str, created_by_user_id: int | None = None
) -> tuple[AllowedEmail, bool]:
    """Inscrit l'adresse. Rend `(entrée, créée)` — **idempotent** (FR-005).

    L'insertion est tentée d'abord, sous point de reprise, et c'est délibéré :
    une lecture préalable serait franchie par deux exploitants simultanés, là où
    `UNIQUE(email)` ne l'est jamais. Le `SAVEPOINT` est ce qui permet de
    rattraper la violation sans perdre la transaction en cours. Patron exact de
    `user_role_repository.grant`.

    Réinscrire ne réécrit **pas** l'auteur : c'est la première inscription qui a
    accordé l'accès, et l'écraser effacerait la seule trace de qui l'a fait.
    """
    entree = AllowedEmail(email=normalize(email), created_by_user_id=created_by_user_id)
    try:
        with db.begin_nested():
            db.add(entree)
            db.flush()
    except IntegrityError:
        existante = db.scalar(
            select(AllowedEmail).where(AllowedEmail.email == normalize(email))
        )
        if existante is None:  # pragma: no cover — une autre contrainte a cédé
            raise
        return existante, False
    return entree, True


def delete(db: Session, entry: AllowedEmail) -> None:
    db.delete(entry)
    db.flush()
