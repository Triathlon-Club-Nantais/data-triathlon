"""course_sources : les N sources d'une épreuve, dont une seule active (#278)

Revision ID: a2b3c4d5e6f7
Revises: bf114c4206a4
Create Date: 2026-08-12 10:30:00.000000

Une table, et la reprise de l'existant. **Aucun changement de comportement
observable** : `courses.source_url` et `courses.provider` restent la source de
vérité du reste du code, c'est #279 qui les dérive de la source active. La table
est donc en avance sur ses lecteurs, délibérément.

Trois points qui ne se rattrapent pas :

- `UNIQUE(course_id, url)` et **pas** `UNIQUE(url)`. Une URL porte légitimement
  N épreuves — heats Klikego, multi-catégories Wiclax, multi-listes RaceResult,
  multi-épreuves Chronoplace, cf. `course_repository.list_by_source_url`. Un
  unique global sur `url` casserait ces quatre fournisseurs, et la reprise
  ci-dessous échouerait dès la première épreuve à heats.
- L'index partiel `UNIQUE(course_id) WHERE is_active` porte **les deux
  dialectes**. N'en donner qu'un produirait un index *complet* sur l'autre
  moteur, ce qui rendrait la deuxième source d'une épreuve irreprésentable —
  exactement le piège déjà rencontré sur `uq_role_global_slug` (#115).
- La reprise passe par du **Core**, pas par l'ORM. Charger `Course` ferait porter
  à cette révision les colonnes ajoutées par les révisions *suivantes*, absentes
  de la base à ce stade, et `alembic upgrade head` casserait sur base vierge le
  jour où le modèle gagne une colonne (le piège documenté sur
  `services/reclassify._COLUMNS_AT_REVISION`).

Les épreuves à `source_url` vide — saisies à la main, jamais importées —
n'obtiennent **aucune** source. C'est un état légitime, pas un trou à combler.
"""
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "bf114c4206a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

#: Tables décrites en Core, réduites aux colonnes que cette révision touche.
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
    sa.column("created_at", sa.DateTime),
)


def upgrade() -> None:
    op.create_table(
        "course_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        # Nullable : l'import — collage public, Sheet, re-scrape en batch — n'a
        # pas d'utilisateur à nommer. Sans `ondelete`, comme partout dans le
        # dépôt : `core/database.py` n'émet aucun `PRAGMA foreign_keys=ON`, la
        # contrainte serait inerte en SQLite et active en PostgreSQL.
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("last_scraped_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_id", "url", name="uq_course_source_url"),
    )
    with op.batch_alter_table("course_sources", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_course_sources_course_id"), ["course_id"], unique=False
        )
    # Hors du bloc `batch_alter_table` : les `*_where` sont des arguments de
    # dialecte que l'opération par lot ne relaie pas.
    op.create_index(
        "uq_course_source_active",
        "course_sources",
        ["course_id"],
        unique=True,
        sqlite_where=sa.text("is_active"),
        postgresql_where=sa.text("is_active"),
    )

    _reprendre_les_urls_des_epreuves()


def _reprendre_les_urls_des_epreuves() -> None:
    """Une source **active** par épreuve déjà importée, depuis `(source_url, provider)`.

    `INSERT … SELECT` : la reprise reste une seule requête quel que soit le
    volume, et rien ne remonte en Python. `sa.true()` plutôt que `1` — un entier
    n'est pas un booléen en PostgreSQL.
    """
    maintenant = datetime.now(UTC).replace(tzinfo=None)
    origine = sa.select(
        COURSES.c.id,
        COURSES.c.source_url,
        COURSES.c.provider,
        sa.true(),
        sa.literal(maintenant, sa.DateTime),
    ).where(COURSES.c.source_url != "")
    op.execute(
        COURSE_SOURCES.insert().from_select(
            ["course_id", "url", "provider", "is_active", "created_at"], origine
        )
    )


def downgrade() -> None:
    """Rend la table. Les index tombent avec elle — pas de `drop_index` séparé.

    Sans perte : `courses.source_url` et `courses.provider` n'ont pas bougé, la
    remontée reconstitue les mêmes lignes.
    """
    op.drop_table("course_sources")
