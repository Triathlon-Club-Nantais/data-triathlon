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
from app.schemas.admin import SessionRevocation, SessionRevocationRequest
from app.services.auth import session as session_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


@router.post("/admin/sessions/revoke", response_model=SessionRevocation)
def revoke_sessions(
    body: SessionRevocationRequest | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.SESSIONS_REVOKE)),
):
    """Ferme des sessions. Corps absent → **toutes** ; une adresse → ses comptes.

    **Une adresse ferme tous les comptes qui la portent.** `users.email` n'est
    pas unique (FR-003), et l'écran qui appelle cette route liste des *adresses*,
    pas des comptes : en épargner un sous incident serait l'erreur coûteuse.
    Même cible que la CLI, à l'inverse de `grant-role` qui refuse de trancher.

    Sans corps, elle ferme **la session de l'appelant** avec les autres. Ce n'est
    pas un effet de bord à corriger : sous fuite, le jeton de celui qui clique est
    suspect comme les autres. L'écran l'annonce avant le geste, et la requête
    suivante rendra 401.

    Idempotente, et un « 0 session fermée » est un succès : révoquer deux fois de
    suite n'est pas une erreur, et distinguer les deux appartient au compte rendu,
    pas au code de statut. Une adresse inconnue en est un aussi — l'écran ne
    propose que des adresses de sa propre liste, il n'y a pas de faute de frappe
    possible, là où la CLI la refuse. **Aucun compte n'est désactivé** : on coupe
    des jetons, on ne met personne dehors.
    """
    email = body.email if body else None
    sessions, comptes = (
        session_service.revoke_all(db)
        if email is None
        else session_service.revoke_for_email(db, email)
    )
    # « Qui a coupé tout le monde, et quand » est la première question posée en
    # incident, et c'est le seul geste dont l'auteur s'effacerait lui-même : sa
    # session est détruite avec les autres. Tous les gestes d'administration du
    # dépôt journalisent leur acteur ; celui-ci ne peut pas faire exception.
    logger.info(
        "Sessions revoked: actor=%s scope=%s sessions=%s accounts=%s",
        actor.id,
        email or "all",
        sessions,
        comptes,
    )
    db.commit()
    return SessionRevocation(sessions=sessions, accounts=comptes)
