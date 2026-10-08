"""ignored identity cases

Cas de revue d'identité à une seule fiche écartés par un admin (#1252).

Revision ID: b0a5ce5d2183
Revises: f3a8c1d7b6e4
Create Date: 2026-10-08 12:18:30.237845
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b0a5ce5d2183'
down_revision: str | None = 'f3a8c1d7b6e4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table('ignored_identity_cases',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('athlete_id', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(length=32), nullable=False),
    sa.Column('fingerprint', sa.String(length=1024), nullable=False),
    sa.Column('ignored_by_user_id', sa.Integer(), nullable=False),
    sa.Column('ignored_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['ignored_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('athlete_id', 'reason', name='uq_ignored_identity_case')
    )
    with op.batch_alter_table('ignored_identity_cases', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ignored_identity_cases_athlete_id'), ['athlete_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('ignored_identity_cases', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ignored_identity_cases_athlete_id'))

    op.drop_table('ignored_identity_cases')
