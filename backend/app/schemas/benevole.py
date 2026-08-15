"""DTO de la page de vérification des résultats par les bénévoles (#271)."""
from pydantic import BaseModel, ConfigDict, Field


class BenevoleLogin(BaseModel):
    """Corps de `POST /benevoles/session`."""

    password: str


class BenevoleCourseRename(BaseModel):
    """Corps de `PATCH /benevoles/courses/{course_id}`.

    **Restreint au seul nom** (contracts/api.md) : contrairement à
    `AdminCourseUpdate`, les trois autres champs de l'identité d'une épreuve
    (`event_date`, `event_type`, `is_relay`) ne sont pas éditables depuis cette
    page.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
