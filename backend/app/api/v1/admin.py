"""Router Admin : signalement des providers non supportés.

**Trois routes, deux gardes, et c'est délibéré** (#115). Le signalement est
public — il vient du formulaire du site, chez un visiteur anonyme — alors que le
consulter et l'instruire exigent chacun leur pouvoir. C'est ce contraste qui
interdit toute garde par préfixe (FR-018, FR-022) : posée sur `/admin`, elle
supprimerait la fonctionnalité de signalement sans que rien ne la nomme.
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.api.deps import (
    current_user,
    has_volunteer_cookie,
    public_write_rate_limit,
    require_permission,
)
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.permissions import P
from app.models.user import User
from app.repositories import course_repository, pending_provider_repository
from app.schemas.admin import (
    CourseReliabilityRead,
    CourseReliabilityUpdate,
    PendingProviderOut,
    PendingProviderReported,
    ProviderQualityOut,
)
from app.schemas.count import BadgeCounts
from app.schemas.ids import DbId
from app.services import admin_badge_counts, course_review, pending_providers
from app.services.auth import authorization

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
    response_model=PendingProviderReported,
    status_code=201,
    dependencies=[Depends(public_write_rate_limit)],
)
def report_pending_provider(body: PendingProviderCreate, db: Session = Depends(get_db)):
    # `HttpUrl` garantit un host : plus rien à rattraper ici.
    entry = pending_provider_repository.report(
        db, url=str(body.url), provider_hint=body.url.host or ""
    )
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "url": entry.url, "provider_hint": entry.provider_hint}


@router.get("/admin/badge-counts", response_model=BadgeCounts, response_model_exclude_none=True)
def badge_counts(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> BadgeCounts:
    """Les pastilles du rail en un appel (#1385) : chacune sous le pouvoir de
    son écran, absente sinon. Aucun pouvoir exigé, comme `GET /auth/me` : la
    réponse ne porte que ce que la session peut déjà voir."""
    codes = authorization.effective_permissions(db, user)
    validation = P.VOLUNTEER_ACCESS_MANAGE.code in codes or has_volunteer_cookie(request, db)
    return BadgeCounts(**admin_badge_counts.counts(db, codes, validation=validation))


@router.get("/admin/pending-providers", response_model=list[PendingProviderOut])
def list_pending_providers(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.PENDING_PROVIDERS_READ)),
):
    return pending_provider_repository.list_unhandled(db)


@router.delete("/admin/pending-providers/{entry_id}", status_code=204)
def mark_handled(
    entry_id: DbId,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.PENDING_PROVIDERS_HANDLE)),
):
    pending_providers.mark_handled(db, actor, entry_id)
    db.commit()


@router.get("/admin/quality/providers", response_model=list[ProviderQualityOut])
def provider_quality(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.QUALITY_OVERRIDE)),
):
    """Épreuves, épreuves non fiables et anomalies par fournisseur (#1366).

    Sous la garde de la revalidation qualité : c'est le même public, qui doit
    trancher ce que coûterait le retrait d'un fournisseur (#1342).
    """
    return course_repository.quality_by_provider(db)


@router.patch(
    "/admin/courses/{course_id}/reliability", response_model=CourseReliabilityRead
)
def set_course_reliability(
    course_id: DbId,
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
