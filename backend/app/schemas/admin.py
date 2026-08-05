"""DTO des ressources d'administration (#115) — formes de `contracts/admin-api.md`."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class PermissionRead(BaseModel):
    """Un pouvoir de l'inventaire, prêt à cocher.

    `code` est un identifiant technique anglais et **stable** — il traverse la
    base ; `label` et `description` sont du français d'affichage.
    """

    code: str
    label: str
    description: str


class PermissionGroupRead(BaseModel):
    """Les pouvoirs d'une fonctionnalité. Composer un rôle en cochant dans une
    liste plate de codes techniques est le geste qu'on veut éviter."""

    feature: str
    permissions: list[PermissionRead]


class RoleBrief(BaseModel):
    """Un rôle tel qu'il se présente à son porteur — sans sa composition."""

    id: int
    slug: str
    name: str
    organisation_id: int | None


class RoleRead(BaseModel):
    """Un rôle, sa composition et son nombre de porteurs.

    `stale_permissions` liste les codes présents en base mais absents de
    l'inventaire — inertes, purgeables, jamais bloquants (FR-042). Les séparer
    de `permissions` est ce qui rend l'écran honnête : « ce rôle porte un code
    que l'application ne connaît plus » se lit, « ce rôle porte 4 pouvoirs dont
    un fantôme » ne se lit pas.
    """

    id: int
    organisation_id: int | None
    slug: str
    name: str
    description: str
    is_system: bool
    is_superuser: bool
    permissions: list[str]
    stale_permissions: list[str]
    holders: int


class RoleCreate(BaseModel):
    """Création d'un rôle. Le `slug` est fixé ici **une fois pour toutes**."""

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    name: str = Field(min_length=1)
    description: str = ""
    organisation_id: int | None = None
    permissions: list[str] = Field(default_factory=list)
    is_superuser: bool = False


class RoleUpdate(BaseModel):
    """Modification d'un rôle. Champs tous facultatifs, `permissions` **remplace**.

    `extra="forbid"` n'est pas de la rigueur gratuite : c'est ce qui fait qu'un
    `slug` soumis rend **422** au lieu d'être ignoré en silence. Le slug est le
    seul nom qui traverse une frontière (`grant-role --role`, le semis) ; le
    renommer casserait les deux sans bruit.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    permissions: list[str] | None = None
    is_superuser: bool | None = None


class RoleAssign(BaseModel):
    """Attribution d'un rôle. `organisation_id` vaut par défaut le seul club."""

    model_config = ConfigDict(extra="forbid")

    role_id: int
    organisation_id: int | None = None


class AdminUserRead(BaseModel):
    """Un utilisateur vu depuis l'administration.

    Sans pagination : le peuplement d'`users` est borné par
    `AUTH_ALLOWED_EMAILS` — une personne y naît d'une connexion réussie **et
    autorisée**.
    """

    id: int
    email: str
    display_name: str
    is_active: bool
    roles: list[RoleBrief]
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_utc(self, value: datetime) -> str:
        """Suffixe `Z`, comme `SessionUserRead` : les colonnes sont des datetimes
        **naïfs en UTC**, et un naïf sérialisé tel quel serait lu comme une heure
        locale par le client."""
        return f"{value.isoformat()}Z"


class CourseReliabilityUpdate(BaseModel):
    """L'avis humain sur la fiabilité d'une épreuve. `null` **lève** l'avis."""

    model_config = ConfigDict(extra="forbid")

    reliability_override: bool | None = None


class CourseReliabilityRead(BaseModel):
    """Les **trois** valeurs, rendues délibérément.

    « La machine a relevé trois trous de classement et doute ; un humain a
    tranché que l'épreuve est fiable » : c'est ce qu'une interface de revue doit
    montrer, et ce qu'une valeur unique rendrait indicible. Ces deux champs
    supplémentaires n'apparaissent **que** sur cette route (FR-038).
    """

    id: int
    is_reliable: bool | None
    is_reliable_computed: bool | None
    reliability_override: bool | None
    quality_issues: dict | None
