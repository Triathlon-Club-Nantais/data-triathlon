"""`GET /auth/me/export` (#1674) : les données du compte connecté, droit d'accès et de portabilité.

Jamais un secret (`subject`, `secret_hash`, jeton) ni la donnée d'une autre personne :
ni l'auteur ou l'athlète d'une déclaration de bénévolat, ni les équipiers d'un relais.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict

from app.schemas.athlete_claim import AthleteClaimRead
from app.schemas.auth import AccountIdentityRead
from app.schemas.course import CourseBrief
from app.schemas.member_request import MemberRequestRead
from app.schemas.utc_datetime import UtcDatetime


class ExportedAccount(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    display_name: str
    created_at: UtcDatetime
    last_seen_at: UtcDatetime


class ExportedAthlete(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nom: str
    prenom: str
    gender: str
    birth_date: date | None
    club: str | None


class ExportedSeasonGoal(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    season: int
    kind: str
    event_type: str | None
    target: int
    created_at: UtcDatetime


class ExportedResultClaim(BaseModel):
    """Une réclamation de résultat : l'épreuve, sa date et le temps réclamé, sans le club ni la catégorie
    de la ligne, qui peuvent être ceux d'une autre personne."""

    participation_id: int
    status: str
    created_at: UtcDatetime
    course_name: str
    event_date: date | None
    total_time: str | None


class ExportedFeedback(BaseModel):
    """Un signalement du compte, sans `ip_address`, `user_agent` ni `github_url`."""

    model_config = ConfigDict(from_attributes=True)

    type: str
    title: str
    body: str
    page_url: str | None
    status: str
    created_at: UtcDatetime


class ExportedVolunteerAction(BaseModel):
    season: int
    title: str | None
    description: str | None
    status: str
    created_at: UtcDatetime
    #: Vrai si la déclaration crédite la fiche rattachée ; fausse, le compte l'a faite pour un autre athlète.
    for_my_athlete: bool


class ExportedResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course: CourseBrief
    club: str | None
    category: str | None
    bib_number: str | None
    rank_overall: int | None
    rank_category: int | None
    rank_gender: int | None
    total_time: str | None
    status: str
    is_relay: bool
    team_name: str | None
    splits: dict[str, str] | None
    evidence_url: str | None
    is_pending_validation: bool
    is_rejected: bool
    created_at: UtcDatetime | None


class AccountExport(BaseModel):
    account: ExportedAccount
    identities: list[AccountIdentityRead]
    athlete: ExportedAthlete | None
    athlete_claim: AthleteClaimRead | None
    member_request: MemberRequestRead | None
    result_claims: list[ExportedResultClaim]
    season_goals: list[ExportedSeasonGoal]
    volunteer_actions: list[ExportedVolunteerAction]
    feedback: list[ExportedFeedback]
    results: list[ExportedResult]
