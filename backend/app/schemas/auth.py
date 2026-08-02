"""DTO du socle d'authentification (#114)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer


class AuthMethodRead(BaseModel):
    """Un moyen de connexion proposé sur l'écran de connexion."""

    slug: str
    label: str


class SessionUserRead(BaseModel):
    """Identité rendue par `GET /auth/me`.

    N'expose ni l'identifiant opaque chez le fournisseur, ni l'identifiant de
    session, ni aucun jeton. `athlete_id` (#117) et le ou les rôles (#115)
    s'ajouteront ici sans rompre le contrat — ajouter un champ n'est pas un
    changement cassant au sens du Principe IV, qui vise le champ retiré, la
    sémantique inversée et le code de retour modifié.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str = ""
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_utc(self, value: datetime) -> str:
        """Suffixe `Z` : les colonnes sont des datetimes **naïfs en UTC**, et un
        naïf sérialisé tel quel serait lu comme une heure locale par le client."""
        return f"{value.isoformat()}Z"
