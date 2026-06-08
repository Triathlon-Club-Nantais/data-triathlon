#!/usr/bin/env python3
"""
audit_scrapers.py — Vérifie l'état de santé de chaque provider de chronométrage.

Tape sur les vrais sites via le registre (`registry.scrape_event_all`), une URL
d'épreuve réelle par provider, et produit un rapport Markdown : OK/KO, nombre de
participants, champs peuplés, type d'épreuve détecté, première erreur éventuelle.

Usage :
    cd backend-v2
    python scripts/audit_scrapers.py [--provider <nom|all>] [--out FICHIER] [--json]

Les URLs de référence sont dans FIXTURE_URLS (événements passés/stables).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

# ── rendre app/ importable ───────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.scrapers import registry  # noqa: E402
from app.scrapers.base import ScrapedResult  # noqa: E402

# ── URLs de référence : 1 épreuve réelle par provider ────────────────────────
FIXTURE_URLS: dict[str, str] = {
    "klikego": "https://www.klikego.com/resultats/triathlon-de-vierzon-2026/1674523163798-4",
    "breizhchrono": (
        "https://resultats.breizhchrono.com/resultats-courses/"
        "triathlon-de-la-cote-de-granit-rose-tregastel-2026-1295405190290-19/triathlon-m"
    ),
    "wiclax": "https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/",
    "timepulse": "https://www.timepulse.fr/epreuves/resultats/live/3232",
    "prolivesport": "https://www.prolivesport.fr/result/1082/6",
    "sportinnovation": "https://sportinnovation.fr/Evenements/Resultats/7031",
}


def _pct(n: int, total: int) -> int:
    return round(100 * n / total) if total else 0


def _has_split(r: ScrapedResult) -> bool:
    return any([r.swim_time, r.t1_time, r.bike_time, r.t2_time, r.run_time])


def _has_rank(r: ScrapedResult) -> bool:
    return any(v is not None for v in (r.rank_overall, r.rank_category, r.rank_gender))


def audit_one(name: str, url: str) -> dict:
    """Lance scrape_event_all et calcule des métriques de qualité."""
    detected = registry.detect_provider(url)
    entry: dict = {
        "provider": name,
        "url": url,
        "detected_provider": detected,
        "detection_ok": detected == name,
        "ok": False,
        "count": 0,
        "elapsed_s": 0.0,
        "error": None,
    }
    t0 = time.monotonic()
    try:
        results = registry.scrape_event_all(url)
    except Exception as exc:  # noqa: BLE001 — on veut tout capturer pour le rapport
        entry["elapsed_s"] = round(time.monotonic() - t0, 2)
        entry["error"] = f"{type(exc).__name__}: {exc}"
        entry["traceback"] = traceback.format_exc()
        return entry

    entry["elapsed_s"] = round(time.monotonic() - t0, 2)
    n = len(results)
    entry["count"] = n
    entry["ok"] = n > 0
    if n:
        entry["with_name_pct"] = _pct(sum(1 for r in results if r.athlete_name), n)
        entry["with_time_pct"] = _pct(sum(1 for r in results if r.total_time), n)
        entry["with_split_pct"] = _pct(sum(1 for r in results if _has_split(r)), n)
        entry["with_rank_pct"] = _pct(sum(1 for r in results if _has_rank(r)), n)
        entry["event_types"] = sorted({r.event_type for r in results if r.event_type})
        entry["sample"] = asdict(results[0])
    return entry


def render_markdown(entries: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Audit scrapers — {now}",
        "",
        "| Provider | Détection | Statut | Participants | Nom% | Temps% | Splits% | Rang% | Type(s) | Temps(s) |",
        "|---|---|:--:|--:|--:|--:|--:|--:|---|--:|",
    ]
    for e in entries:
        status = "✅" if e["ok"] else "❌"
        det = "✅" if e["detection_ok"] else f"⚠️ {e['detected_provider']}"
        types = ", ".join(e.get("event_types", [])) or "—"
        lines.append(
            f"| {e['provider']} | {det} | {status} | {e['count']} | "
            f"{e.get('with_name_pct', 0)} | {e.get('with_time_pct', 0)} | "
            f"{e.get('with_split_pct', 0)} | {e.get('with_rank_pct', 0)} | "
            f"{types} | {e['elapsed_s']} |"
        )
    lines.append("")
    # Détails erreurs
    errs = [e for e in entries if e["error"]]
    if errs:
        lines.append("## Erreurs")
        for e in errs:
            lines.append(f"- **{e['provider']}** (`{e['url']}`) → `{e['error']}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit des scrapers de chronométrage")
    ap.add_argument("--provider", default="all", help="nom du provider ou 'all'")
    ap.add_argument("--out", default="audit_report.md", help="fichier Markdown de sortie")
    ap.add_argument("--json", action="store_true", help="écrit aussi le JSON brut")
    args = ap.parse_args()

    if args.provider != "all":
        if args.provider not in FIXTURE_URLS:
            print(f"Provider inconnu : {args.provider}. Choix : {', '.join(FIXTURE_URLS)}")
            return 2
        targets = {args.provider: FIXTURE_URLS[args.provider]}
    else:
        targets = FIXTURE_URLS

    entries = []
    for name, url in targets.items():
        print(f"→ {name} … ", end="", flush=True)
        e = audit_one(name, url)
        print("OK" if e["ok"] else f"KO ({e['error']})")
        entries.append(e)

    md = render_markdown(entries)
    Path(args.out).write_text(md, encoding="utf-8")
    print(f"\nRapport écrit : {args.out}")
    if args.json:
        json_path = Path(args.out).with_suffix(".json")
        json_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2, default=str))
        print(f"JSON écrit    : {json_path}")
    print("\n" + md)
    return 0 if all(e["ok"] for e in entries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
