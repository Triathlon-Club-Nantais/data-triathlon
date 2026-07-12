"""Source Google Sheet : téléchargement du CSV, extraction et normalisation des liens.

Aucun accès DB, aucun scraping — juste la lecture de la source d'entrée de
l'import de masse.
"""
import csv
import io
from urllib.parse import urlparse, urlunparse

import httpx

from app.scrapers import registry

DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1rtiVRFOQUGcaWCTDPTR4xA9UL22UsWosKjsYMcRMsew/export?format=csv&gid=1961918487"
)
LINK_HEADER = "Donne-nous un lien pour accéder aux résultats."
LINK_COLUMN_FALLBACK_INDEX = 9  # 10e colonne, repli si l'en-tête n'est pas trouvé


def normalize_url(url: str) -> str:
    """Normalise pour la déduplication : trim, host en minuscule, slash final et
    fragment supprimés. La query est conservée (elle distingue deux heats)."""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))


def dedupe_links(links: list[str]) -> list[str]:
    """Dédoublonne par URL normalisée en conservant l'ordre et la forme d'origine."""
    seen: set[str] = set()
    out: list[str] = []
    for url in links:
        key = normalize_url(url)
        if key not in seen:
            seen.add(key)
            out.append(url)
    return out


def parse_sheet_csv(csv_text: str) -> tuple[list[str], int]:
    """Extrait la colonne des liens du CSV. Renvoie (liens_http, nb_lignes_sans_lien).

    Sélection par nom d'en-tête (LINK_HEADER), repli sur l'index 9. Les lignes
    entièrement vides sont ignorées ; une ligne non vide sans lien http est comptée
    dans nb_lignes_sans_lien.
    """
    rows = list(csv.reader(io.StringIO(csv_text)))
    if not rows:
        return [], 0
    header = rows[0]
    try:
        col = header.index(LINK_HEADER)
    except ValueError:
        col = LINK_COLUMN_FALLBACK_INDEX

    links: list[str] = []
    sans_lien = 0
    for row in rows[1:]:
        value = row[col].strip() if col < len(row) else ""
        if value.startswith("http"):
            links.append(value)
        elif any(cell.strip() for cell in row):
            sans_lien += 1
    return links, sans_lien


def is_supported(url: str) -> bool:
    """Supporté pour l'import de masse ⇔ le provider détecté n'est pas playwright."""
    return registry.detect_provider(url) != "playwright"


def host_of(url: str) -> str:
    """Host en minuscule, pour grouper les liens ignorés dans le rapport."""
    return (urlparse(url).netloc or "").lower() or "(inconnu)"


def download_csv(url: str) -> str:
    """Télécharge le CSV public du Sheet (httpx, sans auth)."""
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text
