"""active unaccent (recherche d'athlète insensible aux accents)

Revision ID: d5e6f7a8b9c0
Revises: 371ba3919468
Create Date: 2026-08-03 21:40:00.000000
"""
from collections.abc import Sequence

from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "371ba3919468"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Recherche par nom sans accents (#163) : `ilike` ignore la casse mais jamais
    # les accents, sur les deux moteurs — `lower('LEMÉE')` rend `lemée`.
    # Côté SQLite (dev), `unaccent` est une fonction applicative enregistrée à la
    # connexion par `core/database.py` : rien à créer ici.
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    # Créer l'extension ne suffit pas : sur Supabase elle est conventionnellement
    # installée dans le schéma `extensions`, et si celui-ci n'est pas dans le
    # `search_path` du rôle applicatif, `unaccent(...)` ne résout pas. Alembic
    # tourne sur la même URL, donc le même rôle et le même `search_path` que
    # l'application : cet appel fait **échouer le déploiement**, bruyamment,
    # plutôt que de laisser la recherche rendre un 500 des semaines plus tard
    # sur la requête d'un visiteur, sans que personne ne le voie.
    op.execute("SELECT unaccent('É')")


def downgrade() -> None:
    # L'extension n'est pas supprimée : d'autres objets pourraient en dépendre,
    # et la laisser en place est sans effet de bord. Même parti pris que la
    # migration pg_trgm.
    pass
