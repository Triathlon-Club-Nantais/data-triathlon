"""
Playwright fallback scraper for JS-heavy pages not covered by a dedicated scraper.
Runs in a subprocess (temp file) to avoid uvicorn event loop / Windows encoding issues.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

from .base import ScrapedResult

_PLAYWRIGHT_SCRIPT = r"""
import json, re, sys
from playwright.sync_api import sync_playwright

url = sys.argv[1]
result = {"title": "", "api_responses": [], "error": ""}

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ))
        api_data = []
        def on_response(resp):
            ct = resp.headers.get("content-type","")
            if resp.status == 200 and "json" in ct:
                try:
                    api_data.append({"url": resp.url, "body": resp.json()})
                except Exception:
                    pass
        page.on("response", on_response)
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        result["title"] = page.title()
        result["api_responses"] = api_data[:5]
        browser.close()
except Exception as e:
    result["error"] = str(e)

sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
"""


def scrape(url: str) -> ScrapedResult:
    result = ScrapedResult(source_url=url, provider="playwright")
    raw: dict = {"url": url}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                     encoding="utf-8", delete=False) as tf:
        tf.write(_PLAYWRIGHT_SCRIPT)
        tmp_path = tf.name

    try:
        proc = subprocess.run(
            [sys.executable, tmp_path, url],
            capture_output=True, timeout=60,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    finally:
        os.unlink(tmp_path)

    if proc.returncode != 0:
        raw["stderr"] = proc.stderr.decode("utf-8", errors="replace")
        result.raw_data = raw
        return result

    try:
        data = json.loads(proc.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        result.raw_data = raw
        return result

    result.event_name = data.get("title", "")
    raw.update(data)

    for api_resp in data.get("api_responses", []):
        body = api_resp.get("body")
        if body:
            _try_extract_from_json(body, result)
            if result.athlete_name:
                break

    result.raw_data = raw
    return result


def _try_extract_from_json(data, result: ScrapedResult):
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        return
    for k in ("nom", "name", "lastName", "last_name"):
        if data.get(k):
            result.athlete_name = str(data[k])
            break
    for k in ("prenom", "firstname", "firstName", "first_name"):
        if data.get(k):
            result.athlete_firstname = str(data[k])
            break
    result.club = str(data.get("club", ""))
    result.category = str(data.get("categorie", data.get("category", "")))
    result.total_time = str(data.get("temps", data.get("time", "")))
    for k in ("classement", "rank", "position"):
        if data.get(k):
            try:
                result.rank_overall = int(re.sub(r"[^\d]", "", str(data[k])))
            except ValueError:
                pass
            break
