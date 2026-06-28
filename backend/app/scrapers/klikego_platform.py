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

import httpx
from bs4 import BeautifulSoup

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ
from .utils import normalize_time

_XOR_KEY = ord("K")
_PAGE_SIZE = 50

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,*/*",
}


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
    raw = base64.b64decode(raw_b64)
    text = bytes(b ^ _XOR_KEY for b in raw).decode("utf-8")
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
