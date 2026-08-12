"""courses.source_url et courses.provider tombent : dérivés de la source active (#279)

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-12 11:40:00.000000

`course_sources` cesse d'être en avance sur ses lecteurs : elle devient la
**seule** vérité. `Course.source_url` et `Course.provider` sont désormais des
`hybrid_property` lisant la source active, les deux colonnes n'ont plus de
lecteur, et elles **partent** — on ne les garde pas « au cas où » (principe : ne
pas préserver la compatibilité ascendante).

La reprise a déjà eu lieu, en `a2b3c4d5e6f7` : une source active par épreuve
importée. Rien à copier ici, seulement à supprimer. Les épreuves à `source_url`
vide n'avaient obtenu aucune source, et c'était voulu — elles rendront la chaîne
vide, ce que faisait déjà la colonne.

`batch_alter_table` **n'est pas optionnel** : SQLite ne sait pas supprimer une
colonne portée par une table qu'il reconstruit, et le dépôt tourne sur SQLite en
dev comme en test. Il n'y a en revanche **aucun `*_where` de dialecte en jeu**
ici, contrairement à `a2b3c4d5e6f7` — c'est ce qui rend l'opération par lot
utilisable sans réserve.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

#: Tables décrites en Core, réduites aux colonnes que la **remontée** touche.
#: Pas d'entité ORM : `Course` ne porte plus ces deux attributs comme colonnes,
#: et charger le modèle ferait porter à cette révision les colonnes ajoutées par
#: les suivantes (le piège documenté sur `services/reclassify`).
COURSES = sa.table(
    "courses",
    sa.column("id", sa.Integer),
    sa.column("source_url", sa.String),
    sa.column("provider", sa.String),
)
COURSE_SOURCES = sa.table(
    "course_sources",
    sa.column("course_id", sa.Integer),
    sa.column("url", sa.String),
    sa.column("provider", sa.String),
    sa.column("is_active", sa.Boolean),
)


def upgrade() -> None:
    with op.batch_alter_table("courses", schema=None) as batch_op:
        batch_op.drop_column("source_url")
        batch_op.drop_column("provider")


def downgrade() -> None:
    """Rend les colonnes **et leur contenu**, relu depuis la source active.

    Une remontée qui rendrait deux colonnes vides serait une perte de données
    déguisée en réversibilité : l'épreuve garderait son classement et perdrait le
    lien vers le chronométrage. Les passives, elles, ne sont pas
    représentables dans l'ancien schéma — c'est la limite assumée de la remontée,
    et la raison pour laquelle `course_sources` **n'est pas supprimée** ici.

    `server_default=""` puis retrait : les colonnes sont `NOT NULL` dans le schéma
    d'origine (`e4211f35a275`), et une table déjà peuplée refuserait l'ajout sans
    valeur de remplissage.
    """
    with op.batch_alter_table("courses", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("source_url", sa.String(), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("provider", sa.String(), nullable=False, server_default="")
        )

    active = sa.select(COURSE_SOURCES.c.url).where(
        COURSE_SOURCES.c.course_id == COURSES.c.id, COURSE_SOURCES.c.is_active
    )
    provider_actif = sa.select(COURSE_SOURCES.c.provider).where(
        COURSE_SOURCES.c.course_id == COURSES.c.id, COURSE_SOURCES.c.is_active
    )
    op.execute(
        COURSES.update().values(
            source_url=sa.func.coalesce(active.scalar_subquery(), ""),
            provider=sa.func.coalesce(provider_actif.scalar_subquery(), ""),
        )
    )

    with op.batch_alter_table("courses", schema=None) as batch_op:
        batch_op.alter_column("source_url", server_default=None)
        batch_op.alter_column("provider", server_default=None)
