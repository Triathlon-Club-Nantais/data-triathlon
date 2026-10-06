"""club members per season (#1202)

Licenciés du club par saison (#1202). Un numéro de licence apparaît une fois par
saison ; sans numéro (fichier importé), le nom seul identifie, d'où l'index
unique partiel sur `(season, last_name_key, first_name_key)`.

Revision ID: d2b6e8a1c5f3
Revises: c4f1a7d2e9b3
Create Date: 2026-10-06 19:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd2b6e8a1c5f3'
down_revision: Union[str, None] = 'c4f1a7d2e9b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table(
        'club_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('licence_id', sa.String(length=20), nullable=True),
        sa.Column('nom', sa.String(), nullable=False),
        sa.Column('prenom', sa.String(), nullable=False),
        sa.Column('gender', sa.String(length=1), nullable=False),
        sa.Column('last_name_key', sa.String(), nullable=True),
        sa.Column('first_name_key', sa.String(), nullable=True),
        sa.Column('athlete_id', sa.Integer(), nullable=True),
        sa.Column('link_status', sa.String(length=16), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('season', 'licence_id', name='uq_club_member_licence'),
    )
    op.create_index('ix_club_members_season', 'club_members', ['season'], unique=False)
    op.create_index('ix_club_members_athlete_id', 'club_members', ['athlete_id'], unique=False)
    op.create_index(
        'uq_club_member_identity_without_licence',
        'club_members',
        ['season', 'last_name_key', 'first_name_key'],
        unique=True,
        postgresql_where=sa.text('licence_id IS NULL'),
        sqlite_where=sa.text('licence_id IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_club_member_identity_without_licence', table_name='club_members')
    op.drop_index('ix_club_members_athlete_id', table_name='club_members')
    op.drop_index('ix_club_members_season', table_name='club_members')
    op.drop_table('club_members')
