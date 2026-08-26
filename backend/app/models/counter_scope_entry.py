"""CounterScopeEntry — les deux ensembles qui bornent les compteurs (#95).

Une entrée est une chaîne appartenant à l'un des deux ensembles : les
disciplines exclues des compteurs, ou les libellés reconnus comme libellés du
club. Ces deux listes vivaient en dur dans `core/discipline.py` et
`core/club.py` ; les porter en base retire le développeur, le commit et le
déploiement du chemin d'une décision d'exploitation.

**Une table pour deux natures**, discriminées par `kind`. Les deux entrées ont
exactement la même forme — une chaîne, son auteur, sa date — et rien ne les
distingue structurellement : deux tables auraient produit deux modèles, deux
repositories et deux routeurs pour la même forme.

`value` porte la forme **comparable**, jamais la saisie brute : c'est elle que
`is_tcn` et `tcn_clause` comparent des deux côtés. Normaliser à la lecture
donnerait deux occasions de plus de diverger.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow

#: Les deux natures d'entrée. Ces chaînes traversent la base : les renommer
#: laisserait derrière elles des lignes que plus rien ne lit.
NON_FEDERAL_DISCIPLINE = "non_federal_discipline"
CLUB_LABEL = "tcn_club_label"

KINDS: frozenset[str] = frozenset({NON_FEDERAL_DISCIPLINE, CLUB_LABEL})


class CounterScopeEntry(Base):
    """Une chaîne dans l'un des deux ensembles, avec sa provenance."""

    __tablename__ = "counter_scope_entries"
    __table_args__ = (UniqueConstraint("kind", "value", name="uq_counter_scope_kind_value"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    #: `NULL` pour les lignes posées par la migration d'amorçage — affichées
    #: « Configuration initiale ». Aucune `relationship` inverse sur `User` :
    #: rien ne remonte d'un utilisateur vers ses entrées.
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    created_by: Mapped["User | None"] = relationship()  # noqa: F821
