"""
Reliability check — test scrape_event_all on all event URLs from the TCN xlsx.

Usage:
    python reliability_check.py [--limit N] [--provider klikego] [--timeout 60]

Output: reliability_report.json + reliability_report.md  (both gitignored)

No personal data in output — only URLs, provider, result counts and errors.
"""
import argparse, json, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

FIXTURE = Path(__file__).parent.parent / "tests/e2e/fixtures/reliability_urls.json"
REPORT_JSON = Path(__file__).parent / "reliability_report.json"
REPORT_MD   = Path(__file__).parent / "reliability_report.md"


def test_one(entry: dict, timeout: int) -> dict:
    url      = entry["url"]
    provider = entry["provider"]
    t0 = time.time()
    try:
        from scrapers import scrape_event_all
        results = scrape_event_all(url)
        elapsed = round(time.time() - t0, 1)
        return {
            "url": url,
            "provider": provider,
            "status": "ok",
            "count": len(results),
            "elapsed_s": elapsed,
            "error": None,
        }
    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        return {
            "url": url,
            "provider": provider,
            "status": "error",
            "count": 0,
            "elapsed_s": elapsed,
            "error": str(e)[:200],
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",    type=int, default=0,  help="Max URLs to test (0=all)")
    parser.add_argument("--provider", type=str, default="", help="Filter by provider")
    parser.add_argument("--workers",  type=int, default=4,  help="Parallel workers")
    parser.add_argument("--timeout",  type=int, default=60, help="Per-URL timeout (s)")
    args = parser.parse_args()

    if not FIXTURE.exists():
        sys.exit(f"[error] {FIXTURE} not found — run generate_test_fixtures.py first.")

    with open(FIXTURE, encoding="utf-8") as f:
        cases: list[dict] = json.load(f)

    if args.provider:
        cases = [c for c in cases if c["provider"] == args.provider]
    if args.limit:
        cases = cases[: args.limit]

    print(f"Testing {len(cases)} event URLs  (workers={args.workers}, timeout={args.timeout}s)")
    print("-" * 60)

    results = []
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(test_one, c, args.timeout): c for c in cases}
        for fut in as_completed(futures):
            r = fut.result()
            done += 1
            icon = "✓" if r["status"] == "ok" else "✗"
            print(f"[{done:3}/{len(cases)}] {icon} {r['provider']:20} {r['elapsed_s']:5.1f}s  "
                  f"{'count='+str(r['count']) if r['status']=='ok' else r['error'][:60]}")
            results.append(r)

    # ── Stats ─────────────────────────────────────────────────────────────────
    by_provider: dict[str, dict] = {}
    for r in results:
        p = r["provider"]
        s = by_provider.setdefault(p, {"ok": 0, "error": 0, "errors": []})
        if r["status"] == "ok":
            s["ok"] += 1
        else:
            s["error"] += 1
            s["errors"].append({"url": r["url"], "error": r["error"]})

    total_ok    = sum(r["status"] == "ok"    for r in results)
    total_error = sum(r["status"] == "error" for r in results)
    overall_pct = round(100 * total_ok / len(results), 1) if results else 0

    # ── JSON report ───────────────────────────────────────────────────────────
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(results),
        "ok": total_ok,
        "error": total_error,
        "success_rate_pct": overall_pct,
        "by_provider": {
            p: {
                "ok": s["ok"],
                "error": s["error"],
                "success_rate_pct": round(100 * s["ok"] / (s["ok"] + s["error"]), 1),
                "errors": s["errors"],
            }
            for p, s in by_provider.items()
        },
    }
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # ── Markdown report ───────────────────────────────────────────────────────
    lines = [
        f"# Rapport de fiabilité — {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        f"**Score global : {overall_pct}%** ({total_ok}/{len(results)} URLs OK)",
        "",
        "## Par provider",
        "",
        "| Provider | OK | Erreurs | Taux |",
        "|----------|---:|--------:|-----:|",
    ]
    for p, s in sorted(by_provider.items(), key=lambda x: -x[1]["ok"]/(x[1]["ok"]+x[1]["error"])):
        pct = round(100 * s["ok"] / (s["ok"] + s["error"]), 1)
        flag = " ⚠" if pct < 80 else ""
        lines.append(f"| {p} | {s['ok']} | {s['error']} | {pct}%{flag} |")

    lines += ["", "## URLs en erreur", ""]
    for p, s in by_provider.items():
        for e in s["errors"]:
            lines.append(f"- `{e['url'][:80]}`  \n  _{e['error']}_")

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"Score global : {overall_pct}% ({total_ok}/{len(results)})")
    for p, s in sorted(by_provider.items()):
        pct = round(100 * s["ok"] / (s["ok"] + s["error"]), 1)
        print(f"  {p:25} {pct:5.1f}%  ({s['ok']}/{s['ok']+s['error']})")
    print(f"\nRapport : {REPORT_MD}")


if __name__ == "__main__":
    main()
