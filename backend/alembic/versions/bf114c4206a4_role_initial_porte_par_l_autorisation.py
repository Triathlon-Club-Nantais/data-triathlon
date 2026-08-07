"""role initial porte par l autorisation

Le rôle qu'un compte porte **à sa naissance** (#239), rangé sur l'autorisation.

Nullable, et il le restera : autoriser sans donner de rôle reste le cas
ordinaire, et c'est l'état de toutes les lignes existantes.

**Sans `ondelete`**, comme les autres clés étrangères de #114/#170 : la
contrainte serait inerte en SQLite (`database.py` n'émet aucun
`PRAGMA foreign_keys=ON`) et active en PostgreSQL. La suppression d'un rôle
encore posé est refusée par `authorization.delete_role`, en 409, avec le nombre
d'adresses concernées — comme elle le fait déjà pour les porteurs.

La contrainte est **nommée** : `None` rendrait le `downgrade` inapplicable en
PostgreSQL, où l'on ne peut pas retirer une contrainte anonyme.

Revision ID: bf114c4206a4
Revises: a107b77b53e8
Create Date: 2026-08-07 15:50:41.458910
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'bf114c4206a4'
down_revision: Union[str, None] = '2fde0831cb40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

CONTRAINTE = "fk_allowed_emails_role_id_roles"


def upgrade() -> None:
    with op.batch_alter_table('allowed_emails', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(CONTRAINTE, 'roles', ['role_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('allowed_emails', schema=None) as batch_op:
        batch_op.drop_constraint(CONTRAINTE, type_='foreignkey')
        batch_op.drop_column('role_id')
