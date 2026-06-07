"""
Generate anonymized reliability-test fixture from xlsx_urls.json.

Output: tests/e2e/fixtures/reliability_urls.json  (gitignored)

Rules:
- Strip all personal params (search=, query=, B=, b=, dossard=, inter=, sex=, category=)
- Deduplicate by event-level URL
- No names, no bibs — event URLs only (public data)

Run after extract_xlsx_urls.py.
"""
import json, sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

sys.stdout.reconfigure(encoding="utf-8")

PERSONAL_PARAMS = {"search", "query", "b", "B", "dossard", "inter", "sex", "category", "sexe"}
SKIP_PROVIDERS  = {"breizhchrono_live", "breizhchrono_dead", "unknown"}

SRC  = Path(__file__).parent / "xlsx_urls.json"
DEST = Path(__file__).parent.parent / "tests/e2e/fixtures/reliability_urls.json"


def strip_personal_params(url: str) -> str:
    parsed = urlparse(url)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()
              if k not in PERSONAL_PARAMS}
    return urlunparse(parsed._replace(query=urlencode(params)))


def main():
    if not SRC.exists():
        sys.exit(f"[error] {SRC} not found — run extract_xlsx_urls.py first.")

    with open(SRC, encoding="utf-8") as f:
        grouped: dict[str, list] = json.load(f)

    seen_urls: set[str] = set()
    cases: list[dict] = []
    stats = {}

    for provider, entries in grouped.items():
        if provider in SKIP_PROVIDERS:
            print(f"[skip] {provider}: {len(entries)} entries (unsupported/personal)")
            continue

        added = 0
        for entry in entries:
            url = strip_personal_params(entry["url"])
            if url in seen_urls:
                continue
            seen_urls.add(url)
            cases.append({"provider": provider, "url": url})
            added += 1

        stats[provider] = added
        print(f"[ok]   {provider}: {added} unique event URLs")

    DEST.parent.mkdir(parents=True, exist_ok=True)
    with open(DEST, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

    print(f"\n[done] {len(cases)} total event URLs → {DEST.name}")
    print("[reminder] reliability_urls.json is gitignored — never commit it.")


if __name__ == "__main__":
    main()
