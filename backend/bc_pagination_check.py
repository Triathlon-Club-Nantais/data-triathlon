"""
Regression test for Breizh Chrono pagination completeness.

BC exposes a "default" page (page="") that contains athletes not always
present on numbered pages (page=1,2,3…). This test verifies that
scrape_event_all captures ALL athletes across both page types.

For each BC URL in the fixture, the test:
  1. Fetches page="" directly from BC to get the "hidden" athletes
  2. Runs scrape_event_all via the backend API
  3. Verifies that ALL bibs from page="" appear in the import

Usage:
    python bc_pagination_check.py [--limit N] [--verbose]

Output: bc_pagination_report.json (gitignored)

Run locally — never commit results (may contain bib numbers).
"""
import argparse, json, sys, httpx
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

FIXTURE = Path(__file__).parent.parent / "tests/e2e/fixtures/reliability_urls.json"
REPORT  = Path(__file__).parent / "bc_pagination_report.json"
BC_BASE = "https://resultats.breizhchrono.com"
HEADERS = {"User-Agent": "Mozilla/5.0 Chrome/124.0", "Referer": BC_BASE}


def _parse_bc_url(url: str):
    from scrapers.breizhchrono import _parse_bc_url
    return _parse_bc_url(url)


def _bc_page_empty_bibs(event_id: str, heat: str, client: httpx.Client) -> set[str]:
    """Fetch BC page='' and return the set of bib numbers found."""
    resp = client.get(
        f"{BC_BASE}/v8/evenement/resultats-search.jsp"
        f"?event={event_id}&heat={heat}&search=&city=&category=&sexe=&page=",
        headers=HEADERS, timeout=20
    )
    if resp.status_code != 200:
        return set()
    soup = BeautifulSoup(resp.text, "lxml")
    return {r.get("data-dossard","") for r in soup.select("tr.result-row[data-dossard]")}


def _scrape_all_bibs(url: str) -> set[str]:
    """Run scrape_event_all and return the set of bib numbers imported."""
    from scrapers import scrape_event_all
    try:
        results = scrape_event_all(url)
        return {r.bib_number for r in results if r.bib_number}
    except Exception as e:
        return set()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",   type=int, default=0)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if not FIXTURE.exists():
        sys.exit(f"[error] {FIXTURE} not found — run generate_test_fixtures.py first.")

    with open(FIXTURE, encoding="utf-8") as f:
        all_cases = json.load(f)

    bc_cases = [c for c in all_cases if c["provider"] == "breizhchrono"]
    if args.limit:
        bc_cases = bc_cases[:args.limit]

    print(f"Testing {len(bc_cases)} Breizh Chrono URLs for pagination completeness")
    print("-" * 70)

    results = []
    failures = []

    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        for i, case in enumerate(bc_cases, 1):
            url = case["url"]
            event_id, heat, slug = _parse_bc_url(url)

            if not event_id or not heat:
                print(f"[{i:3}/{len(bc_cases)}] SKIP  {url[:60]} — URL invalide")
                continue

            # Step 1 — BC page="" bibs (the "hidden" athletes)
            hidden_bibs = _bc_page_empty_bibs(event_id, heat, client)

            # Step 2 — Our scraper bibs
            scraped_bibs = _scrape_all_bibs(url)

            missing = hidden_bibs - scraped_bibs
            status = "OK  " if not missing else "FAIL"

            detail = f"page='' {len(hidden_bibs)} bibs, scraped {len(scraped_bibs)}"
            if missing:
                detail += f", MANQUANTS: {sorted(missing)[:5]}"

            print(f"[{i:3}/{len(bc_cases)}] {status} {url[len(BC_BASE):len(BC_BASE)+60]}")
            if args.verbose or missing:
                print(f"       {detail}")

            entry = {
                "url": url,
                "heat": heat,
                "hidden_bibs_count": len(hidden_bibs),
                "scraped_count": len(scraped_bibs),
                "missing_bibs": sorted(missing),
                "ok": not missing,
            }
            results.append(entry)
            if missing:
                failures.append(entry)

    ok_count = sum(1 for r in results if r["ok"])
    print(f"\n{'='*70}")
    print(f"Score : {ok_count}/{len(results)} OK")
    if failures:
        print(f"\n{len(failures)} URL(s) avec des athletes manquants :")
        for f in failures:
            print(f"  {f['url']}")
            print(f"    page='' bibs manquants: {f['missing_bibs'][:10]}")

    REPORT.write_text(json.dumps({
        "total": len(results),
        "ok": ok_count,
        "failures": failures,
        "details": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRapport: {REPORT.name}")

    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
