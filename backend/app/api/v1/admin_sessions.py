"""Révocation d'urgence des sessions (#169) — deux ressources, un seul pouvoir.

**Toutes, ou un compte.** Le trou de l'issue portait sur « tous les comptes à la
fois » et sur l'ergonomie du geste en incident — la procédure supposait d'ouvrir
`psql` sur Supabase à la main. Le geste par compte n'est pas un doublon du
retrait d'adresse (#170) : celui-ci ferme par la **jointure** sans effacer une
ligne, donc une réinscription dans la fenêtre de TTL ressuscite les jetons.

**L'écran n'est pas le seul chemin, et ne doit pas l'être** : `python -m app.cli
revoke-sessions` fait le même geste sans session, pour le jour où c'est
justement du back-office qu'on se méfie.

Couche mince : délégation à `services/auth/session.py`, aucune écriture directe.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.repositories import user_repository
from app.schemas.admin import SessionRevocation
from app.services.auth import session as session_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


@router.post("/admin/sessions/revoke", response_model=SessionRevocation)
def revoke_all_sessions(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.SESSIONS_REVOKE)),
):
    """Ferme toutes les sessions ouvertes, **celle de l'appelant comprise**.

    Ce n'est pas un effet de bord à corriger : sous fuite, le jeton de celui qui
    clique est suspect comme les autres. L'écran l'annonce avant le geste, et la
    requête suivante rendra 401.

    Idempotente, et un « 0 session fermée » est un succès : révoquer deux fois de
    suite n'est pas une erreur, et distinguer les deux appartient au compte rendu,
    pas au code de statut. **Aucun compte n'est désactivé** — on coupe des jetons,
    on ne met personne dehors.
    """
    sessions, comptes = session_service.revoke_all(db)
    # « Qui a coupé tout le monde, et quand » est la première question posée en
    # incident, et c'est le seul geste dont l'auteur s'effacerait lui-même : sa
    # session est détruite avec les autres. Tous les gestes d'administration du
    # dépôt journalisent leur acteur ; celui-ci ne peut pas faire exception.
    logger.info(
        "Sessions revoked: actor=%s sessions=%s accounts=%s",
        actor.id,
        sessions,
        comptes,
    )
    db.commit()
    return SessionRevocation(sessions=sessions, accounts=comptes)


@router.post("/admin/users/{user_id}/sessions/revoke", response_model=SessionRevocation)
def revoke_user_sessions(
    user_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.SESSIONS_REVOKE)),
):
    """Ferme les sessions d'**un** compte, durablement.

    **Elle cible un compte, jamais une adresse.** `users.email` n'est pas unique
    (FR-003), et l'écran qui appelle cette route liste des comptes : frapper par
    adresse y toucherait des homonymes que rien n'aurait nommés. La CLI prend
    l'adresse parce qu'elle n'a pas d'écran pour choisir.

    Ce qu'elle ajoute au retrait d'adresse (#170) : celui-ci ferme par la
    **jointure** sans effacer une ligne, donc une réinscription dans la fenêtre
    de TTL ressuscite les jetons exacts. Ici les lignes partent, et le compte
    **reste actif** — la personne se reconnecte.

    Un identifiant inconnu est un **succès sans effet**, même parti pris que le
    retrait d'une adresse et d'un rôle : un 404 n'apprendrait rien à qui vient
    de supprimer la ligne dans un autre onglet.

    Révoquer son propre compte est permis et sans garde : c'est le geste de
    « j'ai perdu mon téléphone ».
    """
    cible = user_repository.get(db, user_id)
    if cible is None:
        return SessionRevocation(sessions=0, accounts=0)

    sessions, comptes = session_service.revoke_for_user(db, cible)
    logger.info(
        "Sessions revoked: actor=%s target_user=%s sessions=%s",
        actor.id,
        cible.id,
        sessions,
    )
    db.commit()
    return SessionRevocation(sessions=sessions, accounts=comptes)
