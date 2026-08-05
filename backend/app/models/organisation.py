"""Modèle Organisation — le club dont on est administrateur (#115)."""
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow


class Organisation(Base):
    """Un club. Une seule ligne existera longtemps : `('tcn', …)`, semée.

    **Pourquoi la créer maintenant.** Pas pour épargner un `batch_alter_table`
    plus tard — mesuré et réfuté, `alembic/env.py` porte `render_as_batch=True`.
    C'est une décision produit (« modèle maintenant, usage plus tard ») doublée
    d'un gain précis : elle permet `user_roles.organisation_id` **non nul**, ce
    qui supprime le piège des deux index d'unicité qu'imposerait une colonne
    nullable.

    **Ce qu'elle ne portera jamais** : de la donnée sportive. `Course` est unique
    par `(name, event_date, event_type, is_relay)` — deux clubs important la même
    épreuve obtiennent la **même** ligne. Y ajouter une organisation casserait la
    déduplication ou dupliquerait des milliers de participations par club.
    """

    __tablename__ = "organisations"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
