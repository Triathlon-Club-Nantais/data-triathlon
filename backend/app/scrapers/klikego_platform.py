"""
Moteur partagé pour la plateforme Klikego / Breizh Chrono.

Les deux fournisseurs utilisent le même back-office. Leur page de résultats
charge l'intégralité de la liste (finishers + DNF/DNS/DSQ) dans une iframe
`/bc/resultats/course-result.jsp` qui embarque les données dans un
`<script id="data">` encodé base64 + XOR (clé 'K'). C'est la source de vérité,
contrairement à `/v8/evenement/resultats-search.jsp` qui n'expose que les
classés et sous-pagine.

Format d'une ligne (séparateur `|`), 12 champs :
  dossard|diploma|classement|classementCat|nom|cat|sexe|club_ou_ville|inter|officiel|reel|endurance
"""
import base64
import re
from datetime import date as _date

import httpx
from bs4 import BeautifulSoup

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, ScrapedResult
from .utils import normalize_time

_XOR_KEY = ord("K")
_PAGE_SIZE = 50

def decode_data_block(html: str) -> list[list[str]]:
    """Décode le `<script id="data">` d'une page course-result.jsp.

    Retourne une liste de lignes, chaque ligne = liste de ses champs (str).
    `[]` si le bloc est absent ou vide.
    """
    el = BeautifulSoup(html, "lxml").find(id="data")
    if not el:
        return []
    raw_b64 = el.get_text().strip()
    if not raw_b64:
        return []
    try:
        raw = base64.b64decode(raw_b64)
        text = bytes(b ^ _XOR_KEY for b in raw).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        # HTML externe : un bloc corrompu ne doit pas faire échouer l'import.
        return []
    return [line.split("|") for line in text.split("\n") if line.strip()]


_STATUS_BY_TOKEN = {
    "DNF": STATUS_DNF,
    "AB": STATUS_DNF,
    "ABANDON": STATUS_DNF,
    "DNS": STATUS_DNS,
    "NP": STATUS_DNS,
    "DSQ": STATUS_DSQ,
    "DQ": STATUS_DSQ,
    "DISQ": STATUS_DSQ,
}


def _split_name(full: str) -> tuple[str, str]:
    """`"DE POORTER Axel"` -> ("DE POORTER", "Axel"). Nom = tokens MAJUSCULES de tête."""
    parts = full.split()
    i = 0
    while i < len(parts) and parts[i].isupper():
        i += 1
    return " ".join(parts[:i]), " ".join(parts[i:])


def _parse_rank(value: str) -> int | None:
    m = re.match(r"\d+", value.strip())
    return int(m.group(0)) if m else None


def parse_data_row(fields: list[str]) -> dict:
    """Transforme une ligne du data block (12 champs) en dict de champs ScrapedResult."""
    f = (fields + [""] * 12)[:12]
    dossard, _diploma, clt, cltcat, nom, cat, sexe, club, inter, officiel, reel, _end = f

    status = _STATUS_BY_TOKEN.get(clt.strip().upper(), "")
    nom_fam, prenom = _split_name(nom.strip())
    gender = sexe.strip().upper()
    if gender == "H":  # alias utilisé par certains systèmes
        gender = "M"

    return {
        "bib_number": dossard.strip(),
        "athlete_name": nom_fam,
        "athlete_firstname": prenom,
        "category": cat.strip(),
        "gender": gender if gender in ("M", "F") else "",
        "club": club.strip(),
        "rank_overall": None if status else _parse_rank(clt),
        "rank_category": None if status else _parse_rank(cltcat),
        "total_time": "" if status else normalize_time(officiel.strip()),
        "status": status,
    }


def _course_result_url(base: str, event_id: str, heat: str, inter: str, page: int) -> str:
    return (
        f"{base}/bc/resultats/course-result.jsp"
        f"?ref={event_id}&heat={heat}&query=&category=&sex=&inter={inter}&page={page}"
    )


def fetch_heat_rows(
    base: str, event_id: str, heat: str, client: httpx.Client, inter: str = ""
) -> list[list[str]]:
    """Pagine course-result.jsp et retourne toutes les lignes brutes (dédoublonnées)."""
    out: dict[str, list[str]] = {}
    page = 0
    prev_first: str | None = None
    while True:
        resp = client.get(_course_result_url(base, event_id, heat, inter, page))
        if resp.status_code != 200:
            break
        rows = decode_data_block(resp.text)
        if not rows:
            break
        first_bib = rows[0][0] if rows[0] else ""
        if first_bib and first_bib == prev_first:
            break  # la plateforme répète la dernière page
        prev_first = first_bib
        for r in rows:
            bib = r[0] if r else ""
            if bib and bib not in out:
                out[bib] = r
        if len(rows) < _PAGE_SIZE:
            break
        page += 1
    return list(out.values())


def discover_inter_options(heat_page_html: str) -> list[tuple[str, str]]:
    """Retourne les checkpoints (value, label) du <select name="inter">, sauf 'Arrivée'."""
    sel = BeautifulSoup(heat_page_html, "lxml").find("select", {"name": "inter"})
    if not sel:
        return []
    out = []
    for opt in sel.find_all("option"):
        value = (opt.get("value") or "").strip()
        if value:
            out.append((value, opt.get_text(strip=True)))
    return out


# Mapping label de checkpoint -> slot positionnel ScrapedResult.
# Ordre : motifs spécifiques (numérotés) avant génériques.
_INTER_SLOT_RULES = [
    ("course à pied 1", "swim"),
    ("course a pied 1", "swim"),
    ("cap 1", "swim"),
    ("course à pied 2", "run"),
    ("course a pied 2", "run"),
    ("cap 2", "run"),
    ("natation", "swim"),
    ("nat", "swim"),
    ("t1", "t1"),
    ("vélo", "bike"),
    ("velo", "bike"),
    ("bike", "bike"),
    ("t2", "t2"),
    ("course", "run"),
    ("cap", "run"),
    ("run", "run"),
]


def inter_label_to_slot(label: str) -> str | None:
    """Mappe un label de checkpoint (`"Natation + T1"`, `"Vélo"`…) vers un slot."""
    low = label.lower()
    for key, slot in _INTER_SLOT_RULES:
        if key in low:
            return slot
    return None


def fetch_inter_splits(
    base: str,
    event_id: str,
    heat: str,
    inter_options: list[tuple[str, str]],
    client: httpx.Client,
) -> dict[str, dict[str, str]]:
    """Collecte les temps de checkpoints pour tous les participants.

    Pour chaque option `inter` mappable sur un slot, pagine le data block et lit
    le champ `inter` (idx 8). Retourne `{bib: {slot: "HH:MM:SS"}}`.
    Les checkpoints dont le label ne mappe sur aucun slot sont ignorés.
    """
    out: dict[str, dict[str, str]] = {}
    for value, label in inter_options:
        slot = inter_label_to_slot(label)
        if slot is None:
            continue
        for row in fetch_heat_rows(base, event_id, heat, client, inter=value):
            f = (row + [""] * 12)[:12]
            bib, inter_time = f[0].strip(), normalize_time(f[8].strip())
            if bib and inter_time:
                out.setdefault(bib, {})[slot] = inter_time
    return out


def build_heat_results(
    *,
    base: str,
    provider: str,
    event_id: str,
    heat: str,
    heat_page_html: str,
    event_name: str,
    slug: str,
    event_type: str,
    source_url: str,
    event_date: _date | None,
    client: httpx.Client,
) -> list[ScrapedResult]:
    """Assemble la liste complète d'un heat (finishers + DNF/DNS/DSQ) avec splits inter."""
    rows = fetch_heat_rows(base, event_id, heat, client)
    inter_options = discover_inter_options(heat_page_html)
    splits = fetch_inter_splits(base, event_id, heat, inter_options, client) if inter_options else {}

    results: list[ScrapedResult] = []
    for raw in rows:
        d = parse_data_row(raw)
        r = ScrapedResult(source_url=source_url, provider=provider)
        r.event_name = event_name
        r.event_type = event_type
        r.event_date = event_date
        r.bib_number = d["bib_number"]
        r.athlete_name = d["athlete_name"]
        r.athlete_firstname = d["athlete_firstname"]
        r.category = d["category"]
        r.gender = d["gender"]
        r.club = d["club"]
        r.rank_overall = d["rank_overall"]
        r.rank_category = d["rank_category"]
        r.total_time = d["total_time"]
        r.status = d["status"]
        r.raw_data["heat_slug"] = heat
        for slot, t in splits.get(d["bib_number"], {}).items():
            setattr(r, f"{slot}_time", t)
        results.append(r)
    return results
