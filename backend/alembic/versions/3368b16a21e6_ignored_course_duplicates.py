"""ignored course duplicates

Revision ID: 3368b16a21e6
Revises: f93f6bf40e66
Create Date: 2026-08-30 17:18:45.471717
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3368b16a21e6'
down_revision: Union[str, None] = 'f93f6bf40e66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table('ignored_course_duplicates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('course_id_low', sa.Integer(), nullable=False),
    sa.Column('course_id_high', sa.Integer(), nullable=False),
    sa.Column('ignored_by_user_id', sa.Integer(), nullable=False),
    sa.Column('ignored_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['course_id_high'], ['courses.id'], ),
    sa.ForeignKeyConstraint(['course_id_low'], ['courses.id'], ),
    sa.ForeignKeyConstraint(['ignored_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('course_id_low', 'course_id_high', name='uq_ignored_course_duplicate_pair')
    )
    with op.batch_alter_table('ignored_course_duplicates', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ignored_course_duplicates_course_id_high'), ['course_id_high'], unique=False)
        batch_op.create_index(batch_op.f('ix_ignored_course_duplicates_course_id_low'), ['course_id_low'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('ignored_course_duplicates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ignored_course_duplicates_course_id_low'))
        batch_op.drop_index(batch_op.f('ix_ignored_course_duplicates_course_id_high'))

    op.drop_table('ignored_course_duplicates')
