"""Licenciés du club par saison (#1202).

Routeur fin : validation et délégation au service, qui recalcule les
compteurs ; le routeur commite. Chaque route porte sa garde.
"""
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.api.uploads import read_bounded_upload
from app.core.database import get_db
from app.core.permissions import P
from app.core.season import SEASON_MAX, SEASON_MIN
from app.models.user import User
from app.schemas.club_member import (
    ClubMemberLinkIn,
    ClubMemberOut,
    ClubMembersSeasonOut,
    MembersSyncReportOut,
)
from app.services import club_members_service

router = APIRouter(tags=["admin"])


@router.get("/admin/club-members", response_model=ClubMembersSeasonOut)
def list_club_members(
    season: int = Query(..., ge=SEASON_MIN, le=SEASON_MAX),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.CLUB_MEMBERS_MANAGE)),
):
    members = club_members_service.list_season(db, season)
    report = club_members_service.report_of(season, members)
    return ClubMembersSeasonOut(
        **MembersSyncReportOut.model_validate(report).model_dump(),
        seasons=club_members_service.seasons(db),
        members=[ClubMemberOut.model_validate(m) for m in members],
    )


@router.post("/admin/club-members/sync", response_model=MembersSyncReportOut)
def sync_club_members(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.CLUB_MEMBERS_MANAGE)),
):
    report = club_members_service.sync_from_fftri(db, user_id=actor.id)
    db.commit()
    return report


@router.post("/admin/club-members/import", response_model=MembersSyncReportOut)
async def import_club_members(
    season: int = Form(..., ge=SEASON_MIN, le=SEASON_MAX),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.CLUB_MEMBERS_MANAGE)),
):
    content = await read_bounded_upload(file)
    report = club_members_service.import_file(
        db, season=season, content=content, filename=file.filename or "", user_id=actor.id
    )
    db.commit()
    return report


@router.post("/admin/club-members/{member_id}/link", response_model=ClubMemberOut)
def link_club_member(
    member_id: int,
    body: ClubMemberLinkIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.CLUB_MEMBERS_MANAGE)),
):
    member = club_members_service.link_member(
        db, member_id=member_id, athlete_id=body.athlete_id, user_id=actor.id
    )
    db.commit()
    return ClubMemberOut.model_validate(member)


@router.delete("/admin/club-members/{member_id}/link", response_model=ClubMemberOut)
def unlink_club_member(
    member_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.CLUB_MEMBERS_MANAGE)),
):
    member = club_members_service.unlink_member(db, member_id=member_id, user_id=actor.id)
    db.commit()
    return ClubMemberOut.model_validate(member)
