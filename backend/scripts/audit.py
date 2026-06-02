#!/usr/bin/env python3
"""
audit.py — Automated coherence checker for Klikego and TimePulse scrapers.

Discovers events across all supported sports (triathlon/duathlon/swimrun/
aquathlon/aquarun/bike-run), samples athletes, scrapes their results,
validates data quality, and produces a Markdown + JSON report.

Usage:
    cd backend
    python scripts/audit.py [options]

Options:
    --limit N        Max events to discover per sport (default: 6)
    --athletes N     Max athletes to sample per event/heat (default: 8)
    --out FILE       Output Markdown report path (default: audit_report.md)
    --provider       klikego | timepulse | all (default: all)
    --json           Also write raw JSON results
    --timepulse-start N  First id_event to probe (default: 2900)
    --timepulse-end N    Last id_event to probe  (default: 3300)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# ── make sure backend/ is on the path ──────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scrapers.base import ScrapedResult
import scrapers.klikego as klikego_scraper
import scrapers.timepulse as timepulse_scraper
from scrapers.timepulse import _fetch_xml, _attrs as tp_attrs, _detect_event_type as tp_detect

# ── constants ───────────────────────────────────────────────────────────────
KLIKEGO_BASE = "https://www.klikego.com"
KLIKEGO_SPORTS = [
    "triathlon", "duathlon", "swimrun", "aquathlon", "aquarun", "bike run",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://www.klikego.com/",
    "Accept": "text/html,*/*",
}

# Pattern for valid category codes
CAT_RE = re.compile(
    r"^(SE[HF]?|S[1-9]\d*[HF]?|MA[1-9]\d*[HF]?|V[1-5][HF]?|"
    r"JU[HF]?|ES[HF]?|CA[HF]?|BE[HF]?|MI[HF]?|PO[HF]?|"
    r"BEN[HF]?|CAD[HF]?|MIN[HF]?|PUP[HF]?|"
    r"YA?[HF]?|U\d+[HF]?)$",
    re.I,
)


# ═══════════════════════════════════════════════════════════════════════════
# Klikego — discovery + sampling
# ═══════════════════════════════════════════════════════════════════════════

def _discover_klikego_events(limit: int) -> list[dict]:
    """
    Search Klikego for each sport type and collect distinct event IDs.
    Uses /v8/resultats/search.jsp (the AJAX endpoint backing the search page).
    Returns list of {event_id, slug, sport} dicts (without heats yet).
    """
    seen: dict[str, dict] = {}
    search_headers = {**HEADERS, "X-Requested-With": "XMLHttpRequest",
                      "Accept": "text/html,application/json,*/*"}
    with httpx.Client(follow_redirects=True, timeout=15, headers=search_headers) as client:
        for sport in KLIKEGO_SPORTS:
            try:
                r = client.get(
                    f"{KLIKEGO_BASE}/v8/resultats/search.jsp",
                    params={"search": sport, "sport": "", "geo": "", "date": "", "page": "1"},
                )
                soup = BeautifulSoup(r.text, "lxml")
                found = 0
                # Links are absolute (https://www.klikego.com/resultats/slug/id)
                for a in soup.select("a[href*='/resultats/']"):
                    href: str = a.get("href", "")
                    # Normalise to path only
                    href = href.replace("https://www.klikego.com", "")
                    parts = [p for p in href.strip("/").split("/") if p]
                    if len(parts) < 2:
                        continue
                    event_id = parts[-1]
                    slug = parts[-2]
                    # Skip non-numeric-ish IDs (nav links, etc.)
                    if not re.search(r"\d{6,}", event_id):
                        continue
                    if event_id not in seen:
                        seen[event_id] = {
                            "event_id": event_id,
                            "slug": slug,
                            "sport": sport,
                        }
                        found += 1
                        if found >= limit:
                            break
                time.sleep(0.3)
            except Exception as exc:
                print(f"  [klikego] discovery error ({sport}): {exc}")

    return list(seen.values())


def _fetch_klikego_heats(event_id: str, client: httpx.Client) -> list[str]:
    """Return distinct heat values found on the event results page."""
    try:
        r = client.get(f"{KLIKEGO_BASE}/resultats/{event_id}")
        heats = list(dict.fromkeys(re.findall(r'heat=([^&<>\s"\']+)', r.text)))
        return [h for h in heats if h][:4]  # cap at 4 heats per event
    except Exception:
        return []


def _sample_klikego_athletes(event_id: str, heat: str, n: int, client: httpx.Client) -> list[str]:
    """
    Return up to *n* athlete display-names that have a non-empty result time.
    (empty search = first page; filter to rows with a time = event has results)
    """
    try:
        r = client.get(
            f"{KLIKEGO_BASE}/v8/evenement/resultats-search.jsp",
            params={
                "event": event_id, "heat": heat,
                "search": "", "city": "", "category": "", "sexe": "", "page": "",
            },
        )
        soup = BeautifulSoup(r.text, "lxml")
        names: list[str] = []
        for row in soup.select("tr.result-row[data-dossard]"):
            # Only include athletes with a real time — skips upcoming events
            time_cell = row.select_one("td.font-mono")
            if not time_cell or not time_cell.get_text(strip=True):
                continue
            cell = row.select_one("td.truncate")
            if cell:
                name = cell.get_text(strip=True)
                if name:
                    names.append(name)
            if len(names) >= n:
                break
        return names
    except Exception as exc:
        print(f"  [klikego] sample error ({event_id}/{heat}): {exc}")
        return []


def _surname_from_display(name: str) -> str:
    """
    Extract the search-friendly surname from a Klikego display name.
    "DESSENOIX Boris"  -> "DESSENOIX"
    "LE FLOCH Quentin" -> "LE FLOCH"   (multi-word uppercase surname)
    "TEAM BLEU CIEL ." -> skip (relay/team — returns "")
    "CONSTANTIN OLIVIER / GEFFRAY CLOTAIRE" -> skip (returns "")
    """
    name = name.strip().rstrip(".,")
    # Skip relay / team entries
    if "/" in name or " / " in name:
        return ""
    parts = name.split()
    # All-caps tokens at the start = surname
    surname_parts = []
    for part in parts:
        clean = re.sub(r"[^A-Za-zÀ-ÿ]", "", part)
        if clean and clean == clean.upper() and clean.isalpha():
            surname_parts.append(part)
        else:
            break
    if not surname_parts:
        return ""
    # Heuristic: if all tokens are uppercase it's probably a team name, skip
    if all(p == p.upper() and p.isalpha() for p in parts) and len(parts) >= 3:
        return ""
    return " ".join(surname_parts)


def build_klikego_urls(limit: int, max_athletes: int) -> list[dict]:
    """
    Full Klikego pipeline: discover → get heats → sample athletes → build URLs.
    Uses surname-only search to match what the Klikego API expects.
    Returns list of {url, provider, sport, event_id, heat, athlete} dicts.
    """
    print("\n=== Klikego discovery ===")
    events = _discover_klikego_events(limit)
    print(f"  Found {len(events)} distinct events")

    urls: list[dict] = []
    with httpx.Client(follow_redirects=True, timeout=20, headers=HEADERS) as client:
        for ev in events:
            event_id = ev["event_id"]
            slug = ev["slug"]
            heats = _fetch_klikego_heats(event_id, client)
            if not heats:
                print(f"  [{event_id}] no heats -- skipping")
                continue
            for heat in heats[:2]:
                athletes = _sample_klikego_athletes(event_id, heat, max_athletes, client)
                for name in athletes:
                    surname = _surname_from_display(name)
                    if not surname:
                        continue  # skip relay teams etc.
                    urls.append({
                        "url": (
                            f"{KLIKEGO_BASE}/resultats/{slug}/{event_id}"
                            f"?heat={heat}&search={surname}"
                        ),
                        "provider": "klikego",
                        "sport": ev["sport"],
                        "event_id": event_id,
                        "heat": heat,
                        "athlete": name,
                    })
                time.sleep(0.2)
            time.sleep(0.3)

    print(f"  Built {len(urls)} klikego URLs")
    return urls


# ═══════════════════════════════════════════════════════════════════════════
# TimePulse — discovery + sampling
# ═══════════════════════════════════════════════════════════════════════════

_TP_MULTISPORT_KW = (
    "triathlon", "duathlon", "swimrun", "swim-run", "aquathlon", "aquarun",
    "bike & run", "bike and run", "bike run", "bikerun",
    "run & bike", "run and bike",
)


def _is_multisport(name: str) -> bool:
    """True if the event name contains a multisport keyword."""
    n = name.lower()
    return any(kw in n for kw in _TP_MULTISPORT_KW)


def _discover_timepulse_events(id_start: int, id_end: int, limit: int) -> list[dict]:
    """
    Probe id_event values in [id_start, id_end] until *limit* multisport
    events are found.  Non-multisport events (running, trail, open-water
    swimming…) are skipped.
    Returns list of {id_event, event_name, event_type, xml} dicts.
    """
    events: list[dict] = []
    for id_event in range(id_start, id_end + 1):
        if len(events) >= limit:
            break
        xml = _fetch_xml(str(id_event))
        if not xml:
            continue
        m = re.search(r"<Epreuve\s[^>]+>", xml)
        if not m:
            continue
        ea = tp_attrs(m.group())
        name = ea.get("nom", "")
        if not name or not _is_multisport(name):
            continue
        if "<R " not in xml:
            continue
        etype = tp_detect(name)
        events.append({
            "id_event": str(id_event),
            "event_name": name,
            "event_type": etype,
            "xml": xml,
        })
        print(f"  [timepulse] id={id_event}: {name} -> {etype}")
        time.sleep(0.2)

    return events


def _sample_timepulse_athletes(xml: str, n: int) -> list[tuple[str, str]]:
    """Return up to *n* (bib, gender, category) tuples for athletes with results."""
    result_bibs: set[str] = set()
    for m in re.finditer(r"<R\s[^>]+/>", xml):
        a = tp_attrs(m.group())
        b = a.get("d", "")
        if b:
            result_bibs.add(b)

    samples: list[tuple[str, str, str]] = []
    for m in re.finditer(r"<E\s[^>]+/>", xml):
        if len(samples) >= n:
            break
        a = tp_attrs(m.group())
        bib = a.get("d", "")
        gender = a.get("x", "")
        category = a.get("ca", "")
        if bib in result_bibs:
            samples.append((bib, gender, category))

    return samples


def build_timepulse_urls(id_start: int, id_end: int, limit: int, max_athletes: int) -> list[dict]:
    """
    Full TimePulse pipeline: discover → sample athletes → build URLs.
    """
    print("\n=== TimePulse discovery ===")
    events = _discover_timepulse_events(id_start, id_end, limit)
    print(f"  Found {len(events)} valid events")

    urls: list[dict] = []
    for ev in events:
        id_event = ev["id_event"]
        samples = _sample_timepulse_athletes(ev["xml"], max_athletes)
        for bib, gender, category in samples:
            urls.append({
                "url": f"https://www.timepulse.fr/resultats/?id_event={id_event}&bib={bib}",
                "provider": "timepulse",
                "sport": ev["event_type"],
                "id_event": id_event,
                "bib": bib,
                "athlete": f"bib={bib}",
                # Hint for validation (from XML, before scraping)
                "_hint_gender": gender,
                "_hint_category": category,
            })

    print(f"  Built {len(urls)} timepulse URLs")
    return urls


# ═══════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════

def _secs(t: str) -> int:
    if not t:
        return 0
    p = t.split(":")
    try:
        return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])
    except (IndexError, ValueError):
        return 0


def validate(r: ScrapedResult) -> list[dict]:
    """
    Run all coherence checks.
    Returns list of {level, code, message} dicts.
    level: "error" | "warning" | "info"
    """
    issues: list[dict] = []

    def err(code: str, msg: str):
        issues.append({"level": "error", "code": code, "message": msg})

    def warn(code: str, msg: str):
        issues.append({"level": "warning", "code": code, "message": msg})

    def info(code: str, msg: str):
        issues.append({"level": "info", "code": code, "message": msg})

    # ── mandatory presence ──────────────────────────────────────────────────
    if not r.athlete_name:
        err("MISSING_NAME", "athlete_name vide")
    if not r.event_type:
        warn("MISSING_EVENT_TYPE", "event_type vide")
    if not r.total_time:
        warn("MISSING_TOTAL_TIME", "total_time vide")
    if not r.category:
        warn("MISSING_CATEGORY", "category vide")
    if not r.gender:
        warn("MISSING_GENDER", "gender vide")
    if not r.club:
        info("MISSING_CLUB", "club vide")

    # ── category / club cross-check ─────────────────────────────────────────
    if r.club and CAT_RE.match(r.club.strip()):
        err("CLUB_IS_CATEGORY",
            f"club='{r.club}' ressemble à un code catégorie")

    if r.category and not CAT_RE.match(r.category.strip()):
        warn("UNKNOWN_CATEGORY",
             f"category='{r.category}' ne correspond pas aux patterns connus")

    # ── event_type specificity ──────────────────────────────────────────────
    if r.event_type == "triathlon":
        warn("GENERIC_EVENT_TYPE",
             "event_type='triathlon' pourrait être S/M/L/XL")
    if r.event_type == "duathlon":
        warn("GENERIC_EVENT_TYPE",
             "event_type='duathlon' pourrait être XS/S/M/L")
    if r.event_type == "swimrun":
        info("GENERIC_EVENT_TYPE",
             "event_type='swimrun' pourrait être S/M/L")

    # ── split time consistency ──────────────────────────────────────────────
    total_s = _secs(r.total_time)
    if total_s > 0:
        named_splits = [r.swim_time, r.t1_time, r.bike_time, r.t2_time, r.run_time]
        split_secs = [_secs(t) for t in named_splits if t]
        if split_secs:
            split_sum = sum(split_secs)
            ratio = split_sum / total_s
            if ratio > 1.10:
                err("SPLITS_EXCEED_TOTAL",
                    f"somme splits {split_sum}s > total {total_s}s ({ratio:.1%})")
            elif ratio < 0.75 and len(split_secs) >= 3:
                warn("SPLITS_BELOW_TOTAL",
                     f"somme splits {split_sum}s << total {total_s}s ({ratio:.1%}), "
                     "possiblement incomplet")

    # ── sport-specific splits ───────────────────────────────────────────────
    etype = r.event_type or ""

    if etype.startswith("triathlon") and r.total_time:
        missing = []
        if not r.swim_time: missing.append("swim")
        if not r.bike_time: missing.append("bike")
        if not r.run_time:  missing.append("run")
        if missing:
            warn("MISSING_SPLITS",
                 f"triathlon sans splits: {', '.join(missing)}")

    elif etype.startswith("duathlon") and r.total_time:
        missing = []
        if not r.swim_time: missing.append("run1(slot swim)")
        if not r.bike_time: missing.append("bike")
        if not r.run_time:  missing.append("run2")
        if missing:
            warn("MISSING_SPLITS",
                 f"duathlon sans splits: {', '.join(missing)}")

    elif etype == "aquathlon" and r.total_time:
        missing = []
        if not r.swim_time: missing.append("swim")
        if not r.run_time:  missing.append("run")
        if missing:
            warn("MISSING_SPLITS",
                 f"aquathlon sans splits: {', '.join(missing)}")

    elif etype == "aquarun" and r.total_time:
        missing = []
        if not r.swim_time: missing.append("swim")
        if not r.run_time:  missing.append("run")
        if missing:
            warn("MISSING_SPLITS",
                 f"aquarun sans splits: {', '.join(missing)}")

    elif etype == "bike-run" and r.total_time:
        missing = []
        if not r.bike_time: missing.append("bike")
        if not r.run_time:  missing.append("run")
        if missing:
            warn("MISSING_SPLITS",
                 f"bike-run sans splits: {', '.join(missing)}")

    elif etype.startswith("swimrun") and r.total_time:
        if not r.swim_time and not r.run_time:
            warn("MISSING_SPLITS", "swimrun: ni swim ni run renseigné")

    # ── rank sanity ─────────────────────────────────────────────────────────
    if r.rank_overall and r.rank_gender:
        if r.rank_gender > r.rank_overall:
            warn("RANK_ANOMALY",
                 f"rank_gender({r.rank_gender}) > rank_overall({r.rank_overall})")
    if r.rank_gender and r.rank_category:
        if r.rank_category > r.rank_gender:
            warn("RANK_ANOMALY",
                 f"rank_category({r.rank_category}) > rank_gender({r.rank_gender})")

    return issues


# ═══════════════════════════════════════════════════════════════════════════
# Scraping runner
# ═══════════════════════════════════════════════════════════════════════════

def scrape_one(item: dict) -> dict:
    """
    Scrape a single URL, validate, return audit record.
    """
    url = item["url"]
    provider = item["provider"]
    record: dict = {
        "provider": provider,
        "url": url,
        "sport": item.get("sport", ""),
        "athlete": item.get("athlete", ""),
        "event_type": "",
        "result": None,
        "issues": [],
        "error": None,
    }
    try:
        if provider == "klikego":
            r = klikego_scraper.scrape(url)
        else:
            r = timepulse_scraper.scrape(url)

        record["event_type"] = r.event_type
        record["result"] = {
            "athlete": f"{r.athlete_name} {r.athlete_firstname}".strip(),
            "club": r.club,
            "category": r.category,
            "gender": r.gender,
            "bib": r.bib_number,
            "event_name": r.event_name,
            "event_type": r.event_type,
            "event_date": str(r.event_date) if r.event_date else "",
            "total_time": r.total_time,
            "swim": r.swim_time,
            "t1": r.t1_time,
            "bike": r.bike_time,
            "t2": r.t2_time,
            "run": r.run_time,
            "rank_overall": r.rank_overall,
            "rank_gender": r.rank_gender,
            "rank_category": r.rank_category,
        }
        record["issues"] = validate(r)

    except Exception as exc:
        record["error"] = str(exc)

    return record


def run_audit(
    limit: int,
    max_athletes: int,
    providers: list[str],
    tp_start: int,
    tp_end: int,
) -> list[dict]:
    urls: list[dict] = []

    if "klikego" in providers:
        urls += build_klikego_urls(limit=limit, max_athletes=max_athletes)

    if "timepulse" in providers:
        urls += build_timepulse_urls(
            id_start=tp_start, id_end=tp_end,
            limit=limit * 4,       # scan more events to cover sport variety
            max_athletes=max_athletes,
        )

    total = len(urls)
    print(f"\n=== Scraping {total} URLs ===")

    records: list[dict] = []
    for i, item in enumerate(urls, 1):
        print(f"  [{i}/{total}] {item['provider']} {item.get('athlete', '')} ...", end=" ", flush=True)
        rec = scrape_one(item)
        n_err = len([x for x in rec["issues"] if x["level"] == "error"])
        n_warn = len([x for x in rec["issues"] if x["level"] == "warning"])
        status = "OK" if not rec["error"] and n_err == 0 else ("ERR" if rec["error"] else f"!{n_err}e{n_warn}w")
        print(status)
        records.append(rec)
        # Polite rate-limiting
        time.sleep(0.4 if item["provider"] == "klikego" else 0.15)

    return records


# ═══════════════════════════════════════════════════════════════════════════
# Report
# ═══════════════════════════════════════════════════════════════════════════

def _issue_table(issue_counts: dict[str, tuple[int, str]]) -> list[str]:
    rows = sorted(issue_counts.items(), key=lambda x: -x[1][0])
    lines = [
        "| Level | Code | Occurrences |",
        "|-------|------|-------------|",
    ]
    for code, (cnt, level) in rows:
        emoji = "🔴" if level == "error" else "🟡" if level == "warning" else "🔵"
        lines.append(f"| {emoji} {level} | `{code}` | {cnt} |")
    return lines


def generate_report(records: list[dict], out_path: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(records)
    errors = [r for r in records if r.get("error")]
    with_issues = [r for r in records if r.get("issues")]
    clean = [r for r in records if not r.get("error") and not r.get("issues")]

    kl = [r for r in records if r["provider"] == "klikego"]
    tp = [r for r in records if r["provider"] == "timepulse"]

    # Issue frequency map: code → (count, level)
    issue_freq: dict[str, tuple[int, str]] = {}
    for rec in records:
        seen_in_rec: set[str] = set()
        for iss in rec.get("issues", []):
            key = iss["code"]
            if key not in seen_in_rec:
                n, lv = issue_freq.get(key, (0, iss["level"]))
                issue_freq[key] = (n + 1, iss["level"])
                seen_in_rec.add(key)

    # By event_type
    by_type: dict[str, list[dict]] = {}
    for r in records:
        t = r.get("event_type") or "?"
        by_type.setdefault(t, []).append(r)

    # Functional enrichment gaps
    gaps: list[str] = []
    club_is_cat = issue_freq.get("CLUB_IS_CATEGORY", (0, ""))[0]
    missing_cat = issue_freq.get("MISSING_CATEGORY", (0, ""))[0]
    generic_type = issue_freq.get("GENERIC_EVENT_TYPE", (0, ""))[0]
    missing_splits = issue_freq.get("MISSING_SPLITS", (0, ""))[0]
    splits_exceed = issue_freq.get("SPLITS_EXCEED_TOTAL", (0, ""))[0]
    unknown_cat = issue_freq.get("UNKNOWN_CATEGORY", (0, ""))[0]

    if club_is_cat > 0:
        gaps.append(
            f"**Regex catégorie incomplète** ({club_is_cat} cas) — "
            "certains codes ne sont pas reconnus et tombent dans le champ `club`. "
            "Action : étendre le pattern de reconnaissance."
        )
    if missing_cat > 5:
        gaps.append(
            f"**Catégorie manquante** ({missing_cat} cas) — "
            "la méta-ligne Klikego ou les balises TimePulse n'exposent pas la catégorie pour certains formats. "
            "Action : analyser les meta-lines non parsées (ajouter au rapport JSON les champs `meta`)."
        )
    if unknown_cat > 0:
        # Collect unknown category values
        unknowns: set[str] = set()
        for rec in records:
            for iss in rec.get("issues", []):
                if iss["code"] == "UNKNOWN_CATEGORY":
                    m = re.search(r"category='([^']+)'", iss["message"])
                    if m:
                        unknowns.add(m.group(1))
        gaps.append(
            f"**Catégories inconnues** ({unknown_cat} cas) — "
            f"valeurs rencontrées : `{'`, `'.join(sorted(unknowns)[:20])}`. "
            "Action : ajouter ces codes à la regex de catégorie."
        )
    if generic_type > 0:
        generic_events = set()
        for rec in records:
            for iss in rec.get("issues", []):
                if iss["code"] == "GENERIC_EVENT_TYPE":
                    res = rec.get("result", {})
                    if res:
                        generic_events.add(res.get("event_name", "?"))
        gaps.append(
            f"**Type d'épreuve trop générique** ({generic_type} cas) — "
            f"événements concernés : {', '.join(list(generic_events)[:10])}. "
            "Action : améliorer la détection S/M/L/XL depuis le nom ou le heat."
        )
    if missing_splits > 5:
        gaps.append(
            f"**Splits manquants** ({missing_splits} cas) — "
            "certains formats ne retournent pas tous les segments attendus. "
            "Action : vérifier les labels de segments non mappés (champs `split_*` dans raw_data)."
        )
    if splits_exceed > 0:
        gaps.append(
            f"**Somme des splits > temps total** ({splits_exceed} cas) — "
            "possible bug de détection cumulatif ou double-comptage de segments. "
            "Action : inspecter les records concernés dans le JSON."
        )

    # ── Write markdown ──────────────────────────────────────────────────────
    lines: list[str] = [
        f"# Rapport d'audit scrapers — {now}",
        "",
        "## Vue d'ensemble",
        "",
        "| Métrique | Valeur |",
        "|----------|--------|",
        f"| Total URLs testées | **{total}** |",
        f"| Erreurs scraper | {len(errors)} ({len(errors)/max(total,1)*100:.1f}%) |",
        f"| Records avec anomalies | {len(with_issues)} ({len(with_issues)/max(total,1)*100:.1f}%) |",
        f"| Records propres | {len(clean)} ({len(clean)/max(total,1)*100:.1f}%) |",
        f"| Klikego | {len(kl)} ({len([r for r in kl if not r.get('error')])} OK) |",
        f"| TimePulse | {len(tp)} ({len([r for r in tp if not r.get('error')])} OK) |",
        "",
        "## Couverture par type d'épreuve",
        "",
        "| Type | Records | Erreurs | Avec anomalies | Propres |",
        "|------|---------|---------|----------------|---------|",
    ]
    for etype in sorted(by_type):
        recs = by_type[etype]
        n_err = sum(1 for r in recs if r.get("error"))
        n_issues = sum(1 for r in recs if r.get("issues"))
        n_clean = sum(1 for r in recs if not r.get("error") and not r.get("issues"))
        lines.append(f"| `{etype}` | {len(recs)} | {n_err} | {n_issues} | {n_clean} |")

    lines += [
        "",
        "## Fréquence des anomalies",
        "",
        *_issue_table(issue_freq),
        "",
        "## Enrichissements fonctionnels identifiés",
        "",
    ]
    if gaps:
        for gap in gaps:
            lines.append(f"- {gap}")
            lines.append("")
    else:
        lines.append("_Aucun enrichissement critique identifié._")
        lines.append("")

    lines += [
        "## Erreurs scraper (échantillon)",
        "",
    ]
    if errors:
        for rec in errors[:50]:
            short_url = rec["url"][:100] + ("…" if len(rec["url"]) > 100 else "")
            lines.append(f"- **{rec['provider']}** `{short_url}`")
            lines.append(f"  ```")
            lines.append(f"  {rec['error']}")
            lines.append(f"  ```")
    else:
        lines.append("_Aucune erreur scraper._")

    lines += [
        "",
        "## Anomalies détaillées (erreurs + warnings)",
        "",
    ]
    shown = 0
    for rec in records:
        issues = [i for i in rec.get("issues", []) if i["level"] in ("error", "warning")]
        if not issues:
            continue
        if shown >= 100:
            remaining = sum(1 for r in records if any(
                i["level"] in ("error", "warning") for i in r.get("issues", [])
            )) - shown
            lines.append(f"_… {remaining} autres anomalies dans le fichier JSON._")
            break
        res = rec.get("result") or {}
        athlete = res.get("athlete") or rec.get("athlete", "?")
        event_name = res.get("event_name") or "?"
        etype = rec.get("event_type") or "?"
        lines.append(
            f"### {athlete} — {event_name} (`{etype}` / {rec['provider']})"
        )
        lines.append(f"- cat: `{res.get('category','')}` | club: `{res.get('club','')}` | "
                     f"temps: `{res.get('total_time','')}` | "
                     f"splits: sw={res.get('swim','')} bi={res.get('bike','')} ru={res.get('run','')}")
        lines.append(f"- URL: `{rec['url'][:100]}`")
        for iss in issues:
            emoji = "🔴" if iss["level"] == "error" else "🟡"
            lines.append(f"  - {emoji} `{iss['code']}` : {iss['message']}")
        lines.append("")
        shown += 1

    content = "\n".join(lines)
    Path(out_path).write_text(content, encoding="utf-8")
    print(f"\nRapport ecrit -> {out_path}")


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Audit scrapers Klikego + TimePulse")
    parser.add_argument("--limit",    type=int,   default=6,
                        help="Nb max événements à découvrir par sport (défaut: 6)")
    parser.add_argument("--athletes", type=int,   default=8,
                        help="Nb max d'athlètes à tester par event/heat (défaut: 8)")
    parser.add_argument("--out",      default="audit_report.md",
                        help="Fichier rapport Markdown (défaut: audit_report.md)")
    parser.add_argument("--provider", choices=["klikego", "timepulse", "all"],
                        default="all")
    parser.add_argument("--json",     action="store_true",
                        help="Écrire aussi les résultats bruts en JSON")
    parser.add_argument("--timepulse-start", type=int, default=2900,
                        dest="tp_start", metavar="N")
    parser.add_argument("--timepulse-end",   type=int, default=3300,
                        dest="tp_end",   metavar="N")
    args = parser.parse_args()

    providers = ["klikego", "timepulse"] if args.provider == "all" else [args.provider]

    t0 = time.monotonic()
    records = run_audit(
        limit=args.limit,
        max_athletes=args.athletes,
        providers=providers,
        tp_start=args.tp_start,
        tp_end=args.tp_end,
    )
    elapsed = time.monotonic() - t0

    print(f"\nDurée : {elapsed:.0f}s | Records : {len(records)}")

    out = args.out
    generate_report(records, out)

    if args.json:
        json_out = out.replace(".md", ".json")
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2, default=str)
        print(f"JSON écrit → {json_out}")


if __name__ == "__main__":
    main()
