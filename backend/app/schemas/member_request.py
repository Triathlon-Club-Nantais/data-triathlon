"""DTO de la demande d'adhésion d'un compte non adhérent (#1785)."""

import re
from datetime import date
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator

from app.schemas.athlete_claim import ClaimantRead
from app.schemas.utc_datetime import UtcDatetime

_PHONE = re.compile(r"^[0-9+ .()-]{6,32}$")
_EARLIEST_BIRTH_DATE = date(1900, 1, 1)

_Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class MemberRequestCreate(BaseModel):
    first_name: _Name
    last_name: _Name
    birth_date: date | None = None
    phone: str | None = None

    @field_validator("birth_date")
    @classmethod
    def _plausible_birth_date(cls, value: date | None) -> date | None:
        if value is not None and not _EARLIEST_BIRTH_DATE <= value <= date.today():
            raise ValueError("Date de naissance invalide.")
        return value

    @field_validator("phone")
    @classmethod
    def _valid_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not _PHONE.fullmatch(value):
            raise ValueError("Numéro de téléphone invalide.")
        return value

    @model_validator(mode="after")
    def _birth_date_or_phone(self) -> Self:
        if self.birth_date is None and self.phone is None:
            raise ValueError("Indiquez votre date de naissance ou votre téléphone.")
        return self


class MemberRequestRead(BaseModel):
    """La demande du compte, telle que son auteur la voit."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: Literal["pending", "rejected"]
    first_name: str
    last_name: str
    birth_date: date | None
    phone: str | None
    created_at: UtcDatetime
    decided_at: UtcDatetime | None


class MemberRequestReviewRead(BaseModel):
    """Une demande de la file du club."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: UtcDatetime
    first_name: str
    last_name: str
    birth_date: date | None
    phone: str | None
    user: ClaimantRead
