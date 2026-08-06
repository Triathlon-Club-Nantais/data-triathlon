"""groups and memberships

Les deux tables de #197. **Aucune donnée n'est écrite** : pas de groupe semé, et
aucun rôle existant n'est recomposé — FR-041 de #115 l'interdit, la composition
d'un rôle étant une donnée d'exploitation. Les trois pouvoirs neufs
(`groups:read`, `groups:write`, `groups:assign`) vivent dans l'application, pas
en base : ils atteignent l'administrateur par `is_superuser`, sans migration.

`groups.organisation_id` est **non nul**, contrairement à `roles.organisation_id` :
un groupe est la composition d'un club précis. C'est ce qui dispense cette table
de l'index partiel `WHERE organisation_id IS NULL` que porte `roles`, et
`user_groups` de toute colonne d'organisation.

Revision ID: 7f53922f6c73
Revises: f6a7b8c9d0e1
Create Date: 2026-08-06 15:47:47.737354
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7f53922f6c73'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table('groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('organisation_id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organisation_id', 'slug', name='uq_group_org_slug')
    )
    with op.batch_alter_table('groups', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_groups_organisation_id'), ['organisation_id'], unique=False)

    op.create_table('user_groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('joined_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'group_id', name='uq_user_group')
    )
    with op.batch_alter_table('user_groups', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_groups_group_id'), ['group_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_groups_user_id'), ['user_id'], unique=False)




def downgrade() -> None:
    with op.batch_alter_table('user_groups', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_groups_user_id'))
        batch_op.drop_index(batch_op.f('ix_user_groups_group_id'))

    op.drop_table('user_groups')
    with op.batch_alter_table('groups', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_groups_organisation_id'))

    op.drop_table('groups')

