#!/usr/bin/env python3
"""
reset_db.py — Réinitialise la base de développement (SQLite uniquement).

Vide complètement la base, réapplique les migrations Alembic, puis (par défaut)
ré-importe un jeu de données démo réel via `scripts/seed_demo.py`.

⚠️ Garde-fou : le script REFUSE de s'exécuter si `DATABASE_URL` n'est pas SQLite.
Il ne touche donc jamais une base PostgreSQL / Supabase (prod).

Usage :
    cd backend
    python scripts/reset_db.py            # vide + migre + seed démo
    python scripts/reset_db.py --no-seed  # schéma vierge seulement
    python scripts/reset_db.py --yes      # sans confirmation interactive
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ── rendre app/ importable ───────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

import app.models  # noqa: E402,F401 — enregistre toutes les tables sur Base.metadata
from app.core.config import get_settings  # noqa: E402
from app.core.database import Base, engine  # noqa: E402


def _reset_schema() -> None:
    """Drop de toutes les tables (+ table de version Alembic), puis upgrade head."""
    from alembic import command
    from alembic.config import Config

    print("  Suppression des tables…")
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

    print("  Réapplication des migrations (alembic upgrade head)…")
    cfg = Config(str(ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")
    print("  Schéma réinitialisé.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Réinitialise la base de dev (SQLite).")
    parser.add_argument("--no-seed", action="store_true",
                        help="ne pas ré-importer les données démo après le reset")
    parser.add_argument("--yes", action="store_true",
                        help="ne pas demander de confirmation interactive")
    args = parser.parse_args()

    settings = get_settings()

    # ── Garde-fou : SQLite uniquement ────────────────────────────────────────
    if not settings.is_sqlite:
        print(
            f"REFUS : DATABASE_URL n'est pas SQLite ({settings.database_url}).\n"
            "Ce script est réservé au développement local et ne touche jamais "
            "une base PostgreSQL / Supabase.",
            file=sys.stderr,
        )
        return 1

    print(f"Cible : {settings.database_url}")

    # ── Confirmation ─────────────────────────────────────────────────────────
    if not args.yes:
        answer = input("Cette base va être ENTIÈREMENT vidée. Confirmer ? (oui/non) ")
        if answer.strip().lower() not in ("oui", "o", "yes", "y"):
            print("Annulé.")
            return 0

    _reset_schema()

    # ── Seed ─────────────────────────────────────────────────────────────────
    if args.no_seed:
        print("Données démo ignorées (--no-seed).")
        return 0

    print("\nImport des données démo…")
    import seed_demo

    return seed_demo.main()


if __name__ == "__main__":
    raise SystemExit(main())
