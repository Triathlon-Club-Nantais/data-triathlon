"""DTO du socle d'authentification (#114)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer


class AuthMethodRead(BaseModel):
    """Un moyen de connexion proposé sur l'écran de connexion."""

    slug: str
    label: str


class SessionRoleRead(BaseModel):
    """Un rôle tel que son porteur se le voit attribuer (#115)."""

    id: int
    slug: str
    name: str
    organisation_id: int | None


class SessionUserRead(BaseModel):
    """Identité rendue par `GET /auth/me`.

    N'expose ni l'identifiant opaque chez le fournisseur, ni l'identifiant de
    session, ni aucun jeton. `athlete_id` (#117) s'ajoutera ici sans rompre le
    contrat — ajouter un champ n'est pas un changement cassant au sens du
    Principe IV, qui vise le champ retiré, la sémantique inversée et le code de
    retour modifié. C'est ce qu'a fait #115 avec les deux champs ci-dessous.

    **Les deux sont nécessaires et ne se déduisent pas l'un de l'autre** :
    `permissions` répond à « ai-je le droit d'afficher ce bouton », `roles` à
    « comment me présenter à moi-même ». Sans le second, écrire « connecté en
    tant qu'administrateur » exigerait un appel de plus, que `GET /admin/roles`
    refuserait justement à qui n'a pas `roles:read`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str = ""
    created_at: datetime
    permissions: list[str] = []
    roles: list[SessionRoleRead] = []

    @field_serializer("created_at")
    def _serialize_utc(self, value: datetime) -> str:
        """Suffixe `Z` : les colonnes sont des datetimes **naïfs en UTC**, et un
        naïf sérialisé tel quel serait lu comme une heure locale par le client."""
        return f"{value.isoformat()}Z"
