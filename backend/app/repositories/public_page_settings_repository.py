"""Accès données des réglages de fiche publique (#1692) : une ligne par compte."""
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.public_page_settings import PublicPageSettings


def get(db: Session, user_id: int) -> PublicPageSettings | None:
    return db.get(PublicPageSettings, user_id)


def list_for_users(db: Session, user_ids: Iterable[int]) -> list[PublicPageSettings]:
    return list(db.scalars(
        select(PublicPageSettings).where(PublicPageSettings.user_id.in_(list(user_ids))).order_by(PublicPageSettings.user_id)
    ))


def upsert(db: Session, user_id: int, **fields) -> PublicPageSettings:
    row = get(db, user_id)
    if row is None:
        row = PublicPageSettings(user_id=user_id)
        db.add(row)
    for name, value in fields.items():
        setattr(row, name, value)
    db.flush()
    return row
