"""seed benevole system user

Compte système « Bénévoles (accès partagé) » (#271, data-model.md §Addition) :
une ligne de données dans `users`, pas une migration de schéma — la table
existe déjà (#114). Aucune ligne `identities` associée : ce compte ne
s'authentifie jamais par OAuth, il n'existe que comme cible de
`AdminActionLog.user_id` pour les gestes déclenchés depuis la page bénévoles
(renommage d'épreuve, réattribution, validation).

**Ce semis ne se rejoue jamais**, sur le patron de `f6a7b8c9d0e1` (RBAC) :
aucune migration ultérieure ne recompose ce compte.

Revision ID: 595676d81c48
Revises: c9d0e1f2a3b4
Create Date: 2026-08-15 12:00:00.000000
"""
from datetime import UTC, datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.services.benevole_access import SYSTEM_USER_EMAIL

revision: str = '595676d81c48'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.bulk_insert(
        sa.table(
            'users',
            sa.column('email', sa.String),
            sa.column('display_name', sa.String),
            sa.column('is_active', sa.Boolean),
            sa.column('created_at', sa.DateTime),
        ),
        [
            {
                'email': SYSTEM_USER_EMAIL,
                'display_name': 'Bénévoles (accès partagé)',
                'is_active': True,
                'created_at': datetime.now(UTC).replace(tzinfo=None),
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM users WHERE email = :email").bindparams(email=SYSTEM_USER_EMAIL)
    )
