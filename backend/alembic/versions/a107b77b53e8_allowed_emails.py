"""allowed emails — la liste d'autorisation passe de l'environnement à la base (#170)

Revision ID: a107b77b53e8
Revises: 7f53922f6c73
Create Date: 2026-08-06 18:16:37.442614

Deux gestes, et le second est le plus important : la table est créée, **puis
remplie depuis `AUTH_ALLOWED_EMAILS`**. Sans cette reprise, le déploiement qui
livre cette révision mettrait dehors tous les contributeurs de la production,
administrateurs compris — donc sans recours par l'écran. Le `startCommand` de
Render exécute `alembic upgrade head` avant `uvicorn` : la reprise a lieu avant
la première requête, il n'y a pas de fenêtre (FR-013, SC-005).

**`os.environ` et non `Settings`** : le réglage `auth_allowed_emails` disparaît
de la configuration dans la même livraison, il n'y a plus rien à lire par là. La
règle « plus aucun `os.getenv` éparpillé dans le code » de `core/config.py` porte
sur le code applicatif ; une migration est un script d'exploitation à usage
unique et daté, et l'exception ne sort pas de ce fichier.

Une variable absente ou vide n'écrit rien — c'est le cas nominal d'une base
neuve, où l'amorçage passe par `python -m app.cli allow-email`.
"""
import os
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a107b77b53e8'
# Rebasée sur les groupes d'appartenance (#197), livrés entre-temps : les deux
# révisions descendaient de `f6a7b8c9d0e1`, ce qui donnait **deux têtes** et
# faisait échouer le `alembic upgrade head` du `startCommand` — au démarrage du
# service, donc en production.
down_revision: Union[str, None] = '7f53922f6c73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    table = op.create_table(
        "allowed_emails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("allowed_emails", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_allowed_emails_email"), ["email"], unique=True
        )

    reprises = _adresses_de_l_environnement()
    if reprises:
        maintenant = datetime.now(timezone.utc).replace(tzinfo=None)
        op.bulk_insert(
            table,
            [
                {"email": adresse, "created_at": maintenant, "created_by_user_id": None}
                for adresse in reprises
            ],
        )


def _adresses_de_l_environnement() -> list[str]:
    """`AUTH_ALLOWED_EMAILS` normalisée et dédoublonnée, dans l'ordre de saisie.

    Même normalisation que `allowed_email_repository.normalize` — minuscules,
    espaces retirés — sans l'importer : une migration ne doit pas dépendre d'un
    module applicatif qui bougera après elle. `dict.fromkeys` dédoublonne sans
    perdre l'ordre, la contrainte `UNIQUE` refusant de toute façon la répétition.
    """
    brut = os.environ.get("AUTH_ALLOWED_EMAILS", "")
    return list(
        dict.fromkeys(
            adresse.strip().lower() for adresse in brut.split(",") if adresse.strip()
        )
    )


def downgrade() -> None:
    """Rend la table. L'index tombe avec elle — pas de `drop_index` séparé."""
    op.drop_table("allowed_emails")
