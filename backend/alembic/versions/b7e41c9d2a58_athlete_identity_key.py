"""athlete identity key

L'identité d'un athlète devient une clé normalisée stockée, plus un rang
d'homonyme (#907, epic #1146) : `UNIQUE(last_name_key, first_name_key,
homonym_rank)` remplace `UNIQUE(nom, prenom, birth_date)`, inopérante (la date
de naissance vaut toujours NULL, et deux NULL ne se heurtent pas, #981).

Les doublons existants (~1 900 groupes en production au 2026-09-24) ne font pas
échouer la contrainte : chaque groupe de même clé reçoit des rangs par `id`
croissant, la plus ancienne fiche restant la fiche principale. Échouer ici
bloquerait le déploiement Render, qui applique les migrations au démarrage ;
la reprise (#906) fusionne ensuite ces groupes.

La règle de normalisation est **figée ici** plutôt qu'importée de
`app.core.athlete_identity` : un rejeu futur doit produire les mêmes clés.
`tests/test_migrations.py` vérifie que les deux copies concordent.

Revision ID: b7e41c9d2a58
Revises: d49e03833de6
Create Date: 2026-10-01 16:00:00.000000
"""
import unicodedata
from collections import defaultdict
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b7e41c9d2a58'
down_revision: str | None = 'd49e03833de6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

_LIGATURES = str.maketrans({"œ": "oe", "æ": "ae", "ø": "o", "ł": "l", "đ": "d"})
_BATCH_SIZE = 5000


def _identity_key(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    folded = "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
    return "".join(c for c in folded.translate(_LIGATURES) if c.isalnum())


def _identity_keys(nom: str | None, prenom: str | None) -> tuple[str, str] | None:
    last_name_key, first_name_key = _identity_key(nom), _identity_key(prenom)
    if not last_name_key:
        return (first_name_key, "") if first_name_key else None
    return last_name_key, first_name_key


def _backfill(connexion) -> None:
    rows = connexion.execute(sa.text("SELECT id, nom, prenom FROM athletes ORDER BY id")).all()
    next_rank: dict[tuple[str, str], int] = defaultdict(int)
    updates = []
    for athlete_id, nom, prenom in rows:
        key = _identity_keys(nom, prenom)
        if key is None:
            continue
        updates.append({"b_id": athlete_id, "b_last": key[0], "b_first": key[1], "b_rank": next_rank[key]})
        next_rank[key] += 1
    statement = sa.text(
        "UPDATE athletes SET last_name_key = :b_last, first_name_key = :b_first, homonym_rank = :b_rank"
        " WHERE id = :b_id"
    )
    for start in range(0, len(updates), _BATCH_SIZE):
        connexion.execute(statement, updates[start:start + _BATCH_SIZE])


def upgrade() -> None:
    op.drop_index('ix_athletes_identity', table_name='athletes')
    with op.batch_alter_table('athletes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_name_key', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('first_name_key', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('homonym_rank', sa.Integer(), server_default='0', nullable=False))

    _backfill(op.get_bind())

    with op.batch_alter_table('athletes', schema=None) as batch_op:
        batch_op.drop_constraint('uq_athlete_identity', type_='unique')
        batch_op.create_unique_constraint(
            'uq_athlete_identity', ['last_name_key', 'first_name_key', 'homonym_rank']
        )
    op.create_index(
        'ix_athletes_identity_last_first', 'athletes', [sa.text('(last_name_key || first_name_key)')]
    )
    op.create_index(
        'ix_athletes_identity_first_last', 'athletes', [sa.text('(first_name_key || last_name_key)')]
    )


def downgrade() -> None:
    # Seules deux fiches datées identiques heurtent l'ancienne contrainte : on les
    # nomme plutôt que de laisser passer une IntegrityError opaque.
    duplicates = op.get_bind().execute(
        sa.text(
            'SELECT nom, prenom, birth_date, COUNT(*) AS n FROM athletes'
            ' WHERE birth_date IS NOT NULL'
            ' GROUP BY nom, prenom, birth_date HAVING COUNT(*) > 1'
        )
    ).fetchall()
    if duplicates:
        details = ', '.join(f'{row.nom} {row.prenom} ({row.birth_date}) : {row.n} fiches' for row in duplicates)
        raise RuntimeError(
            'Downgrade impossible : des fiches partagent (nom, prenom, birth_date). '
            f'Fusionnez-les avant le downgrade. Concernées : {details}'
        )
    op.drop_index('ix_athletes_identity_first_last', table_name='athletes')
    op.drop_index('ix_athletes_identity_last_first', table_name='athletes')
    with op.batch_alter_table('athletes', schema=None) as batch_op:
        batch_op.drop_constraint('uq_athlete_identity', type_='unique')
        batch_op.create_unique_constraint('uq_athlete_identity', ['nom', 'prenom', 'birth_date'])
        batch_op.drop_column('homonym_rank')
        batch_op.drop_column('first_name_key')
        batch_op.drop_column('last_name_key')
    op.create_index(
        'ix_athletes_identity', 'athletes', [sa.text('lower(nom)'), sa.text('lower(prenom)')], unique=False
    )
