"""ClubAlias — variantes de libellé de club regroupées sous un nom canonique (#635).

Généralise à tout club le mécanisme de fusion livré pour le seul TCN (#215) :
`core.counter_scope.club_labels`/`is_tcn` reste intact et continue de servir
exclusivement le comptage (`scope=club`) — ce module est indépendant, pour la
canonicalisation d'affichage/filtre de tous les autres clubs. Design complet :
`docs/superpowers/specs/2026-08-30-fusion-variantes-club-design.md`.

Table dénormalisée, sur le patron de `CounterScopeEntry` : un « club
canonique » n'est pas une entité séparée, seulement le regroupement des
lignes qui partagent le même `canonical_name`.

Pas de registre en mémoire, contrairement à `counter_scope` : ce mécanisme
n'est jamais lu ligne à ligne pendant l'import en tâche de fond — seulement à
la demande (synthèse d'épreuve, filtre) — une lecture base classique suffit.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class ClubAlias(Base):
    """Un libellé brut rattaché à un nom canonique affiché."""

    __tablename__ = "club_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Nom affiché, texte libre choisi par l'administrateur (ex. « Racing Club
    #: Nantais »). Jamais normalisé : c'est la forme d'affichage voulue.
    canonical_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    #: Forme comparable (`core.club.normalize_club`) — UNIQUE : un même
    #: libellé ne peut pas être rattaché à deux noms canoniques différents.
    alias_normalized: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    created_by: Mapped["User | None"] = relationship()  # noqa: F821
