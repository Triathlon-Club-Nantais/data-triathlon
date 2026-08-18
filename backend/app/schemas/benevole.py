"""DTO de la page de vérification des résultats par les bénévoles (#271)."""
from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class ParticipationFieldsUpdate(BaseModel):
    """Corps de `PATCH /benevoles/participations/{id}` (#437).

    Les quatre champs sont facultatifs et tous nullables en base — un
    bénévole peut aussi bien renseigner un dossard que l'effacer.
    """

    model_config = ConfigDict(extra="forbid")

    bib_number: str | None = None
    rank_overall: int | None = None
    club: str | None = None
    category: str | None = None

    @model_validator(mode="after")
    def _au_moins_un_champ(self):
        if not self.model_fields_set:
            raise ValueError("Aucune modification demandée.")
        return self
