"""Router Admin : signalement des providers non supportés.

**Trois routes, deux gardes, et c'est délibéré** (#115). Le signalement est
public — il vient du formulaire du site, chez un visiteur anonyme — alors que le
consulter et l'instruire exigent chacun leur pouvoir. C'est ce contraste qui
interdit toute garde par préfixe (FR-018, FR-022) : posée sur `/admin`, elle
supprimerait la fonctionnalité de signalement sans que rien ne la nomme.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.api.deps import public_write_rate_limit, require_permission
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.permissions import P
from app.models.user import User
from app.repositories import course_repository, pending_provider_repository
from app.schemas.admin import CourseReliabilityRead, CourseReliabilityUpdate
from app.services import course_review

router = APIRouter(tags=["admin"])


class PendingProviderCreate(BaseModel):
    #: `HttpUrl` et non `str` (A04-3, #398) : la route est publique et écrit en
    #: base sans session — sans forme imposée, un anonyme y range des lignes de
    #: taille arbitraire dans une colonne `TEXT`. Le patron est celui de
    #: `ScrapeRequest.url` (#49), et il est ici **sans coût pour l'appelant** :
    #: le signalement suit toujours un import échoué, donc une URL que
    #: `ScrapeRequest` a déjà validée comme `HttpUrl`. Ce qu'`HttpUrl` normalise
    #: au passage n'a pas d'importance pour un champ de diagnostic.
    url: HttpUrl


@router.post(
    "/admin/pending-providers",
    status_code=201,
    dependencies=[Depends(public_write_rate_limit)],
)
def report_pending_provider(body: PendingProviderCreate, db: Session = Depends(get_db)):
    # `HttpUrl` garantit un host : plus rien à rattraper ici.
    entry = pending_provider_repository.create(
        db, url=str(body.url), provider_hint=body.url.host or ""
    )
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "url": entry.url, "provider_hint": entry.provider_hint}


@router.get("/admin/pending-providers")
def list_pending_providers(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.PENDING_PROVIDERS_READ)),
):
    rows = pending_provider_repository.list_unhandled(db)
    return [
        {
            "id": r.id,
            "url": r.url,
            "provider_hint": r.provider_hint,
            "reported_at": r.reported_at.isoformat() if r.reported_at else None,
        }
        for r in rows
    ]


@router.delete("/admin/pending-providers/{entry_id}", status_code=204)
def mark_handled(
    entry_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.PENDING_PROVIDERS_HANDLE)),
):
    pending_provider_repository.mark_handled(db, entry_id)
    db.commit()


@router.patch(
    "/admin/courses/{course_id}/reliability", response_model=CourseReliabilityRead
)
def set_course_reliability(
    course_id: int,
    body: CourseReliabilityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.QUALITY_OVERRIDE)),
):
    """Tranche à la main la fiabilité d'une épreuve, contre l'avis calculé.

    `null` **lève** l'avis humain : l'épreuve reprend son verdict calculé, à jour
    — le *dernier*, pas celui qui valait au moment de la décision (FR-039).

    Rend les **trois** valeurs, et c'est délibéré : elles ne se déduisent pas
    l'une de l'autre, et c'est ce qu'une interface de revue doit montrer.
    """
    course = course_repository.get(db, course_id)
    if course is None:
        raise NotFoundError("Épreuve introuvable")
    course_review.set_override(
        db,
        course,
        verdict=body.reliability_override,
        user_id=user.id,
        notes=body.notes,
    )
    db.commit()
    db.refresh(course)
    return course
