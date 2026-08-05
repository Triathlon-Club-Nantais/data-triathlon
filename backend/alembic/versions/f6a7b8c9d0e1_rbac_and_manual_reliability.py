"""rbac: organisations, roles, role_permissions, user_roles + fiabilité manuelle

RBAC composable (#115). Quatre tables nouvelles, deux colonnes sur `courses`,
**aucune table de #114 modifiée**.

Relue à la main sur quatre points qui ne se rattrapent pas :

- `roles` porte **deux** contraintes d'unicité. `UNIQUE(organisation_id, slug)`
  laisse passer deux rôles globaux de même slug, les deux moteurs tenant deux
  `NULL` pour distincts ; l'index partiel `WHERE organisation_id IS NULL` ferme
  le cas, et **les deux dialectes** y sont renseignés — n'en donner qu'un
  produirait un index *complet* sur l'autre moteur.
- Aucun `ondelete` : `core/database.py` n'émet aucun `PRAGMA foreign_keys=ON`,
  la contrainte serait inerte en SQLite et active en PostgreSQL. Les cascades
  sont portées par l'ORM.
- `is_reliable` est **renommée**, pas recréée : les données restent en place.
- **Ce semis ne se rejoue jamais** (FR-041). Aucune migration ultérieure ne
  recompose `admin`, `validator` ou `moderator` : dès lors qu'un rôle est
  éditable à chaud, sa composition est une donnée d'exploitation, et une
  migration qui la réécrirait effacerait une décision humaine sans trace.
  Ajouter un rôle **nouveau** reste possible — il n'écrase rien.

Revision ID: f6a7b8c9d0e1
Revises: d5e6f7a8b9c0
Create Date: 2026-08-05 15:20:00.000000
"""
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = 'f6a7b8c9d0e1'
down_revision: str | None = 'd5e6f7a8b9c0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

#: Le club existant. `user_roles.organisation_id` est non nul : il faut une
#: organisation avant la première attribution.
ORGANISATION = ("tcn", "Triathlon Club Nantais")

#: `(slug, name, description, is_superuser, [codes])`.
#:
#: `admin` ne porte **aucun** code : `is_superuser` franchit tout pouvoir,
#: présent et à venir. Lui coller les neuf codes du jour le figerait au jour
#: d'aujourd'hui, ce qui est exactement ce que ce booléen évite.
#:
#: `moderator` est semé parce que ses deux pouvoirs sont **couplés** — instruire
#: un signalement sans pouvoir lire la liste n'a pas de sens — et que l'oubli du
#: pouvoir de lecture est le bug attendu d'une composition à la main.
ROLES_SYSTEME = [
    (
        "admin",
        "Administrateur",
        "Franchit tout pouvoir, y compris ceux livrés après lui.",
        True,
        [],
    ),
    (
        "validator",
        "Validateur",
        "Tranche la fiabilité des épreuves douteuses.",
        False,
        ["quality:override"],
    ),
    (
        "moderator",
        "Modérateur",
        "Instruit les chronométreurs signalés par les visiteurs.",
        False,
        ["pending_providers:read", "pending_providers:handle"],
    ),
]


def upgrade() -> None:
    op.create_table(
        'organisations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', name='uq_organisation_slug'),
    )

    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organisation_id', sa.Integer(), nullable=True),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('is_system', sa.Boolean(), nullable=False),
        sa.Column('is_superuser', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organisation_id', 'slug', name='uq_role_org_slug'),
    )
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_roles_organisation_id'), ['organisation_id'], unique=False
        )
    # Hors du bloc `batch_alter_table` : les `*_where` sont des arguments de
    # dialecte que l'opération par lot ne relaie pas.
    op.create_index(
        'uq_role_global_slug',
        'roles',
        ['slug'],
        unique=True,
        sqlite_where=sa.text('organisation_id IS NULL'),
        postgresql_where=sa.text('organisation_id IS NULL'),
    )

    op.create_table(
        'role_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        # Chaîne **sans clé étrangère** : la liste de référence des codes vit
        # dans `core/permissions.py`, pas en base. Une table `permissions` serait
        # un second inventaire, et son sync effacerait des attributions en
        # production le jour où un module ne serait pas importé au démarrage.
        sa.Column('permission_code', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_id', 'permission_code', name='uq_role_permission'),
    )
    with op.batch_alter_table('role_permissions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_role_permissions_role_id'), ['role_id'], unique=False)
        batch_op.create_index(
            batch_op.f('ix_role_permissions_permission_code'), ['permission_code'], unique=False
        )

    op.create_table(
        'user_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('organisation_id', sa.Integer(), nullable=False),
        sa.Column('granted_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id'], ),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'role_id', 'organisation_id', name='uq_user_role_org'),
    )
    with op.batch_alter_table('user_roles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_roles_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_roles_role_id'), ['role_id'], unique=False)
        batch_op.create_index(
            batch_op.f('ix_user_roles_organisation_id'), ['organisation_id'], unique=False
        )

    _semer()

    # `alter_column(new_column_name=…)` et non `drop`/`add` : les verdicts déjà
    # calculés restent en place. `reliability_override` naît à NULL — personne
    # n'a encore tranché quoi que ce soit.
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.alter_column(
            'is_reliable',
            new_column_name='is_reliable_computed',
            existing_type=sa.Boolean(),
            existing_nullable=True,
        )
        batch_op.add_column(sa.Column('reliability_override', sa.Boolean(), nullable=True))


def _semer() -> None:
    """Une organisation et les trois rôles système. **Joué une seule fois.**"""
    maintenant = datetime.now(UTC).replace(tzinfo=None)

    op.bulk_insert(
        sa.table(
            'organisations',
            sa.column('slug', sa.String),
            sa.column('name', sa.String),
            sa.column('created_at', sa.DateTime),
        ),
        [{'slug': ORGANISATION[0], 'name': ORGANISATION[1], 'created_at': maintenant}],
    )

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
                'organisation_id': None,  # rôles partagés par toutes les organisations
                'slug': slug,
                'name': nom,
                'description': description,
                'is_system': True,
                'is_superuser': superutilisateur,
                'created_at': maintenant,
            }
            for slug, nom, description, superutilisateur, _ in ROLES_SYSTEME
        ],
    )

    bind = op.get_bind()
    identifiants = {
        ligne.slug: ligne.id
        for ligne in bind.execute(sa.text('SELECT id, slug FROM roles')).fetchall()
    }
    liens = [
        {'role_id': identifiants[slug], 'permission_code': code}
        for slug, _, _, _, codes in ROLES_SYSTEME
        for code in codes
    ]
    if liens:
        op.bulk_insert(
            sa.table(
                'role_permissions',
                sa.column('role_id', sa.Integer),
                sa.column('permission_code', sa.String),
            ),
            liens,
        )


def downgrade() -> None:
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_column('reliability_override')
        batch_op.alter_column(
            'is_reliable_computed',
            new_column_name='is_reliable',
            existing_type=sa.Boolean(),
            existing_nullable=True,
        )

    op.drop_table('user_roles')
    op.drop_table('role_permissions')
    op.drop_index('uq_role_global_slug', table_name='roles')
    op.drop_table('roles')
    op.drop_table('organisations')
