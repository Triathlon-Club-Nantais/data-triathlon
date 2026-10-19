"""club roles: bureau, bénévoles data, validation, encadrement (#1654)

Rôles globaux, **non système** : le club les renomme, les recompose ou les
supprime depuis l'écran. Un slug déjà présent n'est ni recréé ni recomposé, sa
composition étant une donnée d'exploitation (#115). Aucun ne porte un geste
irréversible sur toute la base ni le pouvoir de distribuer des rôles : ceux-là
restent au superutilisateur.

Revision ID: 2901789fc3c8
Revises: cd0a7061e41f
Create Date: 2026-10-19 12:05:43.793470
"""
from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2901789fc3c8'
down_revision: Union[str, None] = 'cd0a7061e41f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

#: `(slug, name, description, [codes])`, figé à la date de la migration.
CLUB_ROLES = [
    (
        "bureau",
        "Bureau",
        "Accès au site et au back-office, adhérents, licenciés, rattachements, groupes, oppositions, retours.",
        [
            "users:read", "roles:read", "admin_log:read", "allowed_emails:manage", "site_access:manage",
            "benevole_access:manage", "groups:read", "groups:write", "groups:assign", "member_emails:manage",
            "club_members:manage", "athlete_claims:review", "oppositions:manage", "feedback:read",
            "feedback:manage", "pages:preview",
        ],
    ),
    (
        "data",
        "Bénévole data",
        "Entretient les données : épreuves, fiches, homonymes, chronométreurs signalés, variantes de club.",
        [
            "quality:override", "pending_providers:read", "pending_providers:handle", "courses:write",
            "courses:sources", "athletes:read", "athletes:write", "participations:reassign",
            "club_aliases:manage", "counter_scope:manage", "batch:read", "feedback:read",
            "athlete_claims:review", "pages:preview",
        ],
    ),
    (
        "validation",
        "Validation",
        "Valide les saisons des athlètes et les déclarations de bénévolat.",
        ["athletes:season_validate", "athletes:volunteer_validate", "benevole_access:manage"],
    ),
    (
        "encadrant",
        "Encadrant jeunes",
        "Consulte et encadre les jeunes : groupes, séances, appels.",
        ["jeunes:read", "jeunes:write"],
    ),
]

_SLUGS = tuple(slug for slug, *_ in CLUB_ROLES)


def upgrade() -> None:
    bind = op.get_bind()
    existing = {row.slug for row in bind.execute(sa.text("SELECT slug FROM roles WHERE organisation_id IS NULL"))}
    missing = [role for role in CLUB_ROLES if role[0] not in existing]
    if not missing:
        return
    now = datetime.now(UTC).replace(tzinfo=None)
    op.bulk_insert(
        sa.table(
            'roles',
            sa.column('organisation_id', sa.Integer),
            sa.column('slug', sa.String),
            sa.column('name', sa.String),
            sa.column('description', sa.String),
            sa.column('is_system', sa.Boolean),
            sa.column('is_superuser', sa.Boolean),
            sa.column('created_at', sa.DateTime),
        ),
        [
            {
                'organisation_id': None, 'slug': slug, 'name': name, 'description': description,
                'is_system': False, 'is_superuser': False, 'created_at': now,
            }
            for slug, name, description, _ in missing
        ],
    )
    ids = {
        row.slug: row.id
        for row in bind.execute(sa.text("SELECT id, slug FROM roles WHERE organisation_id IS NULL"))
    }
    op.bulk_insert(
        sa.table('role_permissions', sa.column('role_id', sa.Integer), sa.column('permission_code', sa.String)),
        [{'role_id': ids[slug], 'permission_code': code} for slug, _, _, codes in missing for code in codes],
    )


def downgrade() -> None:
    # Un rôle attribué reste en place : la descente ne retire de droit à personne.
    removable = sa.text(
        "SELECT id FROM roles WHERE organisation_id IS NULL AND NOT is_system AND slug IN :slugs"
        " AND id NOT IN (SELECT role_id FROM user_roles)"
    ).bindparams(sa.bindparam('slugs', expanding=True))
    ids = [row.id for row in op.get_bind().execute(removable, {'slugs': list(_SLUGS)})]
    if not ids:
        return
    for table, column in (('role_permissions', 'role_id'), ('roles', 'id')):
        op.get_bind().execute(
            sa.text(f"DELETE FROM {table} WHERE {column} IN :ids").bindparams(sa.bindparam('ids', expanding=True)),
            {'ids': ids},
        )
