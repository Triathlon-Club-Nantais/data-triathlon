#!/usr/bin/env python3
"""
seed_demo.py — Remplit le frontend avec des résultats réels Klikego + TimePulse.

Couvre tous les types d'épreuves : triathlon / duathlon / swimrun / aquathlon / bike-run.

Usage :
    cd backend
    python scripts/seed_demo.py [--api http://localhost:8001] [--per-event 2] [--clear]

Options :
    --api URL        URL de base du backend  (défaut : http://localhost:8001)
    --per-event N    Athlètes à seeder par événement Klikego (défaut : 2)
    --clear          Supprime tous les résultats existants avant de seeder
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# ── import du détecteur d'URL klikego ──────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ═══════════════════════════════════════════════════════════════════════════
# Constantes
# ═══════════════════════════════════════════════════════════════════════════

KLIKEGO_BASE = "https://www.klikego.com"

_KLIKEGO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://www.klikego.com/",
    "Accept": "text/html,*/*",
}

# Catalogue d'événements — une entrée par épreuve à seeder
# Klikego : event_id, slug, heat (vide = auto-detect), desc
# TimePulse : id_event, bibs (list), desc
CATALOG: list[dict] = [
    # ── Klikego ─────────────────────────────────────────────────────────
    {
        "provider": "klikego",
        "desc": "Triathlon L — Coteaux du Vendômois 2026",
        "event_id": "1695506183783-4",
        "slug": "triathlon-des-coteaux-du-vendomois-2026",
        "heat": "",  # auto-detect
    },
    {
        "provider": "klikego",
        "desc": "Duathlon S — 3 Villages 2026",
        "event_id": "1579145109237-15",
        "slug": "duathlon-des-3-villages-2026-5-eme-edition",
        "heat": "",
    },
    {
        "provider": "klikego",
        "desc": "Duathlon S — Cesson-Sévigné 2026 (Course à pied labels)",
        "event_id": "1723364024007-2",
        "slug": "duathlons-de-cesson-sevigne-2026",
        "heat": "",
    },
    {
        "provider": "klikego",
        "desc": "SwimRun L — Côte Beauté 2025",
        "event_id": "1643670876505-4",
        "slug": "swimrun-cote-beaute-2025",
        "heat": "format-l-individuel",
    },
    {
        "provider": "klikego",
        "desc": "Aquathlon — Des 2 Amants 2025",
        "event_id": "1643334174070-7",
        "slug": "aquathlon-des-2-amants-2025",
        "heat": "aquathlon-s-champnat",
    },
    # ── TimePulse ────────────────────────────────────────────────────────
    {
        "provider": "timepulse",
        "desc": "Triathlon — GOUBAUD Manon (id=3090)",
        "id_event": "3090",
        "bibs": ["41"],
    },
    {
        "provider": "timepulse",
        "desc": "Triathlon — Sablé Dimanche (id=2957)",
        "id_event": "2957",
        "bibs": ["116", "117"],
    },
    {
        "provider": "timepulse",
        "desc": "Bike & Run — Bignon (id=2917)",
        "id_event": "2917",
        "bibs": ["1"],
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Helpers Klikego
# ═══════════════════════════════════════════════════════════════════════════

def _detect_heat(event_id: str, kl_client: httpx.Client) -> str:
    """Auto-détecte le premier heat= disponible sur la page résultats."""
    import re
    try:
        r = kl_client.get(f"{KLIKEGO_BASE}/resultats/{event_id}")
        heats = re.findall(r'heat=([^&<>\s"\']+)', r.text)
        return heats[0] if heats else ""
    except httpx.HTTPError:
        return ""


def _sample_athletes(event_id: str, heat: str, n: int, kl_client: httpx.Client) -> list[str]:
    """
    Retourne jusqu'à n noms de famille d'athlètes ayant un résultat (td.font-mono non vide).
    Ignore les équipes/relais (nom contenant '/').
    """
    try:
        r = kl_client.get(
            f"{KLIKEGO_BASE}/v8/evenement/resultats-search.jsp",
            params={"event": event_id, "heat": heat, "search": "",
                    "city": "", "category": "", "sexe": "", "page": ""},
        )
    except httpx.HTTPError as exc:
        print(f"    [klikego] sampling error: {exc}")
        return []

    soup = BeautifulSoup(r.text, "lxml")
    athletes: list[str] = []
    for row in soup.select("tr.result-row[data-dossard]"):
        # Ignorer les athlètes sans temps (événement à venir ou pas encore démarré)
        time_cell = row.select_one("td.font-mono")
        if not time_cell or not time_cell.get_text(strip=True):
            continue
        name_cell = row.select_one("td.truncate")
        if not name_cell:
            continue
        tokens = name_cell.get_text(strip=True).split()
        surname = " ".join(t for t in tokens if t.isupper())
        if not surname or "/" in surname:
            continue
        athletes.append(surname)
        if len(athletes) >= n:
            break
    return athletes


# ═══════════════════════════════════════════════════════════════════════════
# Pipeline API
# ═══════════════════════════════════════════════════════════════════════════

def _scrape_and_save(url: str, api: httpx.Client) -> dict:
    """
    1. POST /api/scrape — récupère les données de l'athlète
    2. POST /api/results — sauvegarde dans la DB

    Retourne un dict de résultat (avec 'status': 'OK'|'ERR' et 'error').
    """
    try:
        resp = api.post("/api/scrape", json={"url": url}, timeout=30)
        if resp.status_code != 200:
            return {"status": "ERR", "error": f"HTTP {resp.status_code}: {resp.text[:120]}"}
        data = resp.json()
    except Exception as exc:
        return {"status": "ERR", "error": str(exc)}

    try:
        save = api.post("/api/results", json=data, timeout=10)
        if save.status_code not in (200, 201):
            return {"status": "ERR", "error": f"Save HTTP {save.status_code}", "data": data}
    except Exception as exc:
        return {"status": "ERR", "error": f"Save error: {exc}", "data": data}

    return {"status": "OK", "data": data}


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the triathlon frontend with real results.")
    parser.add_argument("--api", default="http://localhost:8001",
                        help="Backend base URL (default: http://localhost:8001)")
    parser.add_argument("--per-event", type=int, default=2,
                        help="Athletes to seed per Klikego event (default: 2)")
    parser.add_argument("--clear", action="store_true",
                        help="Delete all existing results before seeding")
    args = parser.parse_args()

    api = httpx.Client(base_url=args.api, follow_redirects=True)
    kl_client = httpx.Client(follow_redirects=True, timeout=15, headers=_KLIKEGO_HEADERS)

    # ── health check ──────────────────────────────────────────────────────
    try:
        health = api.get("/api/health", timeout=5)
        if health.status_code != 200:
            print(f"Backend non disponible ({args.api}) — code {health.status_code}")
            sys.exit(1)
    except Exception as exc:
        print(f"Backend non disponible ({args.api}) : {exc}")
        sys.exit(1)

    print(f"Backend connecte : {args.api}")

    # ── clear ─────────────────────────────────────────────────────────────
    if args.clear:
        print("Suppression des resultats existants...")
        existing = api.get("/api/results", params={"page_size": 100}).json()
        for r in existing:
            api.delete(f"/api/results/{r['id']}")
        print(f"  {len(existing)} resultat(s) supprime(s).")

    # ── seed ──────────────────────────────────────────────────────────────
    rows: list[dict] = []  # pour le tableau final

    for entry in CATALOG:
        print(f"\n[{entry['provider'].upper()}] {entry['desc']}")

        if entry["provider"] == "klikego":
            event_id = entry["event_id"]
            slug = entry["slug"]
            heat = entry.get("heat") or ""

            # Auto-detect heat si non fourni
            if not heat:
                heat = _detect_heat(event_id, kl_client)
                if not heat:
                    print("  Impossible de detecter le heat — evenement ignore.")
                    continue
                print(f"  heat detecte : {heat}")

            surnames = _sample_athletes(event_id, heat, args.per_event, kl_client)
            if not surnames:
                print("  Aucun athlete trouve avec un resultat disponible.")
                continue

            for surname in surnames:
                url = (
                    f"{KLIKEGO_BASE}/resultats/{slug}/{event_id}"
                    f"?heat={heat}&search={surname}"
                )
                print(f"  Scraping {surname} ...", end=" ", flush=True)
                result = _scrape_and_save(url, api)
                _print_status(result)
                rows.append(_make_row(entry["desc"], surname, result))
                time.sleep(0.5)  # politesse

        elif entry["provider"] == "timepulse":
            for bib in entry.get("bibs", []):
                url = f"https://www.timepulse.fr/resultats/?id_event={entry['id_event']}&bib={bib}"
                print(f"  Scraping bib={bib} ...", end=" ", flush=True)
                result = _scrape_and_save(url, api)
                _print_status(result)
                rows.append(_make_row(entry["desc"], f"bib={bib}", result))
                time.sleep(0.3)

    kl_client.close()
    api.close()

    # ── résumé ────────────────────────────────────────────────────────────
    ok = sum(1 for r in rows if r["status"] == "OK")
    err = sum(1 for r in rows if r["status"] == "ERR")

    print(f"\nSeed termine : {ok} resultat(s) sauvegardes, {err} erreur(s)\n")
    print(f"{'Type':<22} {'Athlete':<24} {'Temps':<12} {'Status'}")
    print("-" * 72)
    for row in rows:
        print(f"{row['type']:<22} {row['athlete']:<24} {row['temps']:<12} {row['status']}")


def _print_status(result: dict) -> None:
    if result["status"] == "OK":
        d = result["data"]
        print(f"OK  ({d.get('event_type', '?')} / {d.get('total_time', '?')})")
    else:
        print(f"ERR — {result['error']}")


def _make_row(desc: str, athlete: str, result: dict) -> dict:
    if result["status"] == "OK":
        d = result["data"]
        return {
            "type": d.get("event_type") or desc[:20],
            "athlete": (
                (d.get("athlete_name") or athlete)[:22]
            ),
            "temps": d.get("total_time") or "?",
            "status": "OK",
        }
    return {
        "type": desc[:20],
        "athlete": athlete[:22],
        "temps": "-",
        "status": "ERR",
    }


if __name__ == "__main__":
    main()
