"""Classements Challenge (#1008), lecture seule."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.schemas.challenge import ChallengeDetail
from app.services import challenge_service

router = APIRouter(tags=["challenges"])


@router.get("/challenges/{challenge_id}", response_model=ChallengeDetail)
def get_challenge(challenge_id: int, db: Session = Depends(get_db)):
    found = challenge_service.detail(db, challenge_id)
    if found is None:
        raise NotFoundError("Challenge introuvable")
    return found
