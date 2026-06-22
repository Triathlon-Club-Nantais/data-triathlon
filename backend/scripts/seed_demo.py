#!/usr/bin/env python3
"""
seed_demo.py — Remplit la base de dev avec des résultats réels (toutes disciplines).

Aligné sur le modèle v2 « import d'épreuve complète » : pour chaque URL d'épreuve
du catalogue, on appelle directement `import_service.import_event` (athlètes +
courses + participations, dédupliqués). Aucune logique HTTP/athlète-unique.

Couvre triathlon / duathlon / swimrun / aquathlon / bike-run via des épreuves
réelles, déjà passées et stables. Seules des URLs d'**épreuve** sont utilisées
(données publiques) — jamais de paramètres `search=`/`query=`/`B=` (identité).

Usage :
    cd backend
    python scripts/seed_demo.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# ── rendre app/ importable ───────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.services.import_service import import_event  # noqa: E402

# ── Catalogue : 1 URL d'épreuve réelle par entrée ────────────────────────────
# Sources : audit_scrapers.FIXTURE_URLS (triathlon, 1/provider) + entrées
# duathlon/swimrun/aquathlon/bike&run reconstruites depuis l'ancien seed v1.
CATALOG: list[dict] = [
    # ── Triathlon (un provider chacun) ───────────────────────────────────────
    {
        "desc": "Triathlon — Vierzon 2026 (Klikego)",
        "url": "https://www.klikego.com/resultats/triathlon-de-vierzon-2026/1674523163798-4",
    },
    {
        "desc": "Triathlon M — Trégastel 2026 (Breizh Chrono)",
        "url": (
            "https://resultats.breizhchrono.com/resultats-courses/"
            "triathlon-de-la-cote-de-granit-rose-tregastel-2026-1295405190290-19/triathlon-m"
        ),
    },
    {
        "desc": "Triathlon — La Roche 2026 (Wiclax)",
        "url": "https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/",
    },
    {
        "desc": "Triathlon — épreuve live 3232 (TimePulse)",
        "url": "https://www.timepulse.fr/epreuves/resultats/live/3232",
    },
    # ── Autres disciplines (Klikego, URL d'épreuve = /resultats/{slug}/{id}) ──
    {
        "desc": "Duathlon S — 3 Villages 2026 (Klikego)",
        "url": (
            "https://www.klikego.com/resultats/"
            "duathlon-des-3-villages-2026-5-eme-edition/1579145109237-15"
        ),
    },
    {
        "desc": "SwimRun L — Côte Beauté 2025 (Klikego)",
        "url": "https://www.klikego.com/resultats/swimrun-cote-beaute-2025/1643670876505-4",
    },
    {
        "desc": "Aquathlon — Des 2 Amants 2025 (Klikego)",
        "url": "https://www.klikego.com/resultats/aquathlon-des-2-amants-2025/1643334174070-7",
    },
]


def main() -> int:
    settings = get_settings()
    print(f"Seed démo → {settings.database_url}\n")

    rows: list[tuple[str, str]] = []  # (desc, résumé)
    total_imported = 0
    errors = 0

    for entry in CATALOG:
        print(f"  {entry['desc']:<45} … ", end="", flush=True)
        db = SessionLocal()
        try:
            res = import_event(db, entry["url"], settings)
            total_imported += res.get("imported", 0)
            summary = (
                f"OK — {res.get('imported', 0)} importé(s), "
                f"{res.get('skipped', 0)} ignoré(s)"
                + (" [cache]" if res.get("cached") else "")
            )
        except Exception as exc:  # noqa: BLE001 — on rapporte sans tout interrompre
            errors += 1
            summary = f"ERREUR — {type(exc).__name__}: {exc}"
        finally:
            db.close()
        print(summary)
        rows.append((entry["desc"], summary))
        time.sleep(0.5)  # politesse réseau

    print(
        f"\nSeed terminé : {len(CATALOG) - errors}/{len(CATALOG)} épreuve(s), "
        f"{total_imported} participation(s) importée(s), {errors} erreur(s)."
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
