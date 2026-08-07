"""Router des accès au back-office (#170) — trois ressources, trois gardes.

**Chacune porte sa garde individuellement**, et nomme un pouvoir, jamais un rôle
(FR-017/FR-018 de #115). Aucune n'est protégée par son préfixe : `admin.py`
monte, sous le même `/admin/`, le signalement anonyme du site public.

Couche mince : validation, délégation à `services/auth/allowed_emails.py`,
traduction en HTTP. **Aucune écriture directe** dans `allowed_emails` ni dans
`users` — la désactivation en cascade est un invariant du service, pas du
router, et c'est ce qui la rend impossible à oublier au prochain appelant.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.allowed_email import AllowedEmail
from app.models.user import User
from app.repositories import allowed_email_repository
from app.schemas.admin import AllowedEmailCreate, AllowedEmailRead
from app.services.auth import allowed_emails

router = APIRouter(tags=["admin"])


def _vue(entree: AllowedEmail) -> AllowedEmailRead:
    return AllowedEmailRead(
        id=entree.id,
        email=entree.email,
        created_at=entree.created_at,
        created_by_name=entree.created_by.display_name if entree.created_by else None,
    )


@router.get("/admin/allowed-emails", response_model=list[AllowedEmailRead])
def list_allowed_emails(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ALLOWED_EMAILS_MANAGE)),
):
    """Les adresses autorisées, par ordre alphabétique.

    Une liste vide est une réponse **valide** — elle dit « personne n'est
    autorisé », et l'interface l'affiche comme telle. Elle ne se confond pas avec
    un refus : c'est la distinction que `PendingProvidersTable` a dû apprendre.
    """
    return [_vue(entree) for entree in allowed_emails.list_all(db)]


@router.post("/admin/allowed-emails", response_model=AllowedEmailRead, status_code=201)
def add_allowed_email(
    body: AllowedEmailCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.ALLOWED_EMAILS_MANAGE)),
):
    """Inscrit une adresse. **Idempotent** — réinscrire est un succès (FR-005).

    Effet de bord contractuel : les comptes portant cette adresse repassent à
    `is_active = True`. Sans quoi une réinscription n'ouvrirait rien.
    """
    entree, _, _ = allowed_emails.add(db, actor, email=body.email)
    vue = _vue(entree)
    db.commit()
    return vue


@router.delete("/admin/allowed-emails/{entry_id}", status_code=204)
def remove_allowed_email(
    entry_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.ALLOWED_EMAILS_MANAGE)),
):
    """Retire une adresse et **ferme** les comptes qui la portent (FR-016).

    Idempotent : un identifiant inconnu est un succès sans effet — même parti
    pris que la révocation d'un rôle, et pour la même raison, un 404 n'apprendrait
    rien à qui vient de supprimer la ligne dans un autre onglet.

    **409** si l'organisation y perdrait son dernier administrateur actif :
    l'appelant est bien administrateur et sa requête est bien formée, c'est le
    résultat qui est interdit.
    """
    entree = allowed_email_repository.get(db, entry_id)
    if entree is None:
        return
    allowed_emails.remove(db, actor, entree)
    db.commit()
