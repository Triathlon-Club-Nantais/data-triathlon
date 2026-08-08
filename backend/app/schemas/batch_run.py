"""DTO du lancement et du suivi des batches (#47).

Le corps de lancement est un jeu d'**options typées**, jamais une commande : il
n'existe aucun chemin par lequel une chaîne fournie par l'utilisateur devienne
un argument de ligne de commande (FR-003).
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.scrapers import registry


class RescrapeLaunch(BaseModel):
    """Une reprise filtrée de la base.

    `extra="forbid"` n'est pas du zèle : c'est ce qui fait refuser un `target`
    glissé dans le corps plutôt que l'ignorer en silence. La base visée vient du
    réglage de l'instance, et le dire par un 422 vaut mieux que de laisser
    croire qu'on l'a honoré.
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["rescrape"]
    provider: str | None = None
    older_than: int | None = Field(default=None, ge=1, le=3650)
    limit: int | None = Field(default=None, ge=1, le=500)
    dry_run: bool = False

    @field_validator("provider")
    @classmethod
    def _provider_connu(cls, v: str | None) -> str | None:
        """Validé contre le registre — la seule source de vérité des noms.

        Une faute de frappe passerait sinon jusqu'au runner, où elle ne
        sélectionnerait aucune épreuve : un batch vert, vide, et personne pour
        dire pourquoi.
        """
        if v is not None and v not in registry.provider_names():
            connus = ", ".join(registry.provider_names())
            raise ValueError(f"Fournisseur inconnu : « {v} ». Connus : {connus}.")
        return v


class BatchLaunched(BaseModel):
    """La réponse à un lancement — **sans** identifiant d'exécution.

    La plateforme n'en rend aucun au dispatch. L'interface retrouve son
    lancement dans `GET /admin/batches`, par le `correlation_id` porté par le
    libellé.
    """

    correlation_id: str
    state: Literal["pending"] = "pending"


class BatchRunRead(BaseModel):
    """Un lancement, vu de l'interface.

    Énumérations **en anglais** : une valeur sérialisée dans un contrat d'API
    est de la couche technique invisible (Principe I). « En cours » et « Échec »
    sont produits par les composants du front.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    state: Literal["pending", "running", "completed"]
    outcome: Literal["success", "failure", "cancelled"] | None
    started_at: datetime
    duration_s: int | None
    triggered_by: Literal["ui", "schedule", "manual"]
    report_available: bool
    external_url: str
