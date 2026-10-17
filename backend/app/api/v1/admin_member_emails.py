"""Adresses d'adhérents par saison (#1334).

Routeur fin : validation et délégation au service ; le routeur commite. Chaque
route porte sa garde.
"""
from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.api.uploads import read_bounded_upload
from app.core.database import get_db
from app.core.permissions import P
from app.core.season import SEASON_MAX, SEASON_MIN, current_season
from app.core.time import utcnow
from app.models.user import User
from app.schemas.ids import DbId
from app.schemas.member_email import (
    MemberEmailCreate,
    MemberEmailOut,
    MemberEmailsImportReportOut,
    MemberEmailsSeasonOut,
)
from app.services import member_emails_service

router = APIRouter(tags=["admin"])


@router.get("/admin/member-emails", response_model=MemberEmailsSeasonOut)
def list_member_emails(
    season: int | None = Query(None, ge=SEASON_MIN, le=SEASON_MAX),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.MEMBER_EMAILS_MANAGE)),
):
    listed = member_emails_service.list_season(db, season or current_season(), utcnow().date())
    return MemberEmailsSeasonOut.model_validate(listed)


@router.post("/admin/member-emails/import", response_model=MemberEmailsImportReportOut)
async def import_member_emails(
    season: int = Form(..., ge=SEASON_MIN, le=SEASON_MAX),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.MEMBER_EMAILS_MANAGE)),
):
    content = await read_bounded_upload(file)
    report = member_emails_service.import_file(
        db, season=season, content=content, filename=file.filename or "", user_id=actor.id
    )
    db.commit()
    return report


@router.post("/admin/member-emails", response_model=MemberEmailOut, status_code=201)
def add_member_email(
    body: MemberEmailCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.MEMBER_EMAILS_MANAGE)),
):
    entry = member_emails_service.add(db, email=body.email, season=body.season, user_id=actor.id)
    db.commit()
    return MemberEmailOut.model_validate(entry)


@router.delete("/admin/member-emails/{entry_id}", status_code=204)
def remove_member_email(
    entry_id: DbId,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.MEMBER_EMAILS_MANAGE)),
):
    member_emails_service.remove(db, entry_id=entry_id, user_id=actor.id)
    db.commit()
    return Response(status_code=204)
