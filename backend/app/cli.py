"""
Outillage CLI (Typer) : import de masse depuis le Google Sheet & rescrape DB.

CLI mince par-dessus les services : aucune logique de scraping ni d'accès DB
direct. Invocable depuis backend/ :
    python -m app.cli import-sheet --dry-run
    python -m app.cli rescrape-db --dry-run
"""
import csv
import io
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from urllib.parse import urlparse, urlunparse

import httpx
import typer

from app.core.config import get_settings
from app.core.database import session_scope
from app.scrapers import registry
from app.services import import_service

logger = logging.getLogger(__name__)

DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1rtiVRFOQUGcaWCTDPTR4xA9UL22UsWosKjsYMcRMsew/export?format=csv&gid=1961918487"
)
LINK_HEADER = "Donne-nous un lien pour accéder aux résultats."
LINK_COLUMN_FALLBACK_INDEX = 9  # 10e colonne, repli si l'en-tête n'est pas trouvé

app = typer.Typer(help="Outillage d'import de masse et de rescrape.")


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


@dataclass
class SheetOutcome:
    """Bilan d'un import-sheet."""
    imported: int = 0
    skipped: int = 0
    errors: int = 0
    rows_without_link: int = 0
    unique_supported: int = 0
    ignored_by_host: dict[str, int] = field(default_factory=dict)


def _host(url: str) -> str:
    return (urlparse(url).netloc or "").lower() or "(inconnu)"


def run_import_sheet(
    db,
    csv_text: str,
    settings,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    only_provider: str | None = None,
    delay: float = 1.0,
) -> SheetOutcome:
    """Détecte, dédoublonne et importe les liens supportés du CSV du Sheet.

    En dry-run : ne scrape rien, ne persiste rien, ne temporise pas.
    Les liens non supportés vont au rapport (ignored_by_host) ; jamais une erreur.
    """
    links, rows_without_link = parse_sheet_csv(csv_text)
    unique = dedupe_links(links)

    supported: list[str] = []
    ignored_by_host: dict[str, int] = {}
    for url in unique:
        if is_supported(url):
            if only_provider and registry.detect_provider(url) != only_provider:
                continue
            supported.append(url)
        else:
            host = _host(url)
            ignored_by_host[host] = ignored_by_host.get(host, 0) + 1

    if limit is not None:
        supported = supported[:limit]

    outcome = SheetOutcome(
        rows_without_link=rows_without_link,
        unique_supported=len(supported),
        ignored_by_host=ignored_by_host,
    )
    if dry_run:
        return outcome

    for i, url in enumerate(supported):
        try:
            res = import_service.import_event(db, url, settings, force=False)
            outcome.imported += res.get("imported", 0)
            outcome.skipped += res.get("skipped", 0)
        except Exception as exc:
            outcome.errors += 1
            logger.warning("Échec import %s : %s", url, exc)
        if delay and i < len(supported) - 1:
            time.sleep(delay)

    return outcome


def render_sheet_report(outcome: SheetOutcome, *, dry_run: bool) -> str:
    """Rapport texte lisible : compteurs + table des ignorés groupés par host."""
    lignes = []
    titre = "IMPORT SHEET (dry-run)" if dry_run else "IMPORT SHEET"
    lignes.append(f"=== {titre} ===")
    lignes.append(f"Liens supportés uniques : {outcome.unique_supported}")
    lignes.append(f"Lignes sans lien        : {outcome.rows_without_link}")
    if not dry_run:
        lignes.append(f"Importées : {outcome.imported}")
        lignes.append(f"Ignorées  : {outcome.skipped}")
        lignes.append(f"En erreur : {outcome.errors}")
    if outcome.ignored_by_host:
        lignes.append("Liens non supportés (suivis dans #33) :")
        for host, count in sorted(outcome.ignored_by_host.items()):
            lignes.append(f"  - {host} : {count}")
    return "\n".join(lignes)


def _download_csv(url: str) -> str:
    """Télécharge le CSV public du Sheet (httpx, sans auth)."""
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


@app.command("import-sheet")
def import_sheet(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Détecte et dédoublonne sans scraper ni persister."
    ),
    limit: int | None = typer.Option(None, "--limit", help="Borne le nombre d'épreuves."),
    only_provider: str | None = typer.Option(
        None, "--only-provider", help="Restreint à un provider (ex. klikego)."
    ),
    sheet_url: str = typer.Option(
        DEFAULT_SHEET_URL, "--sheet-url", envvar="IMPORT_SHEET_URL",
        help="Override la source CSV.",
    ),
    delay: float = typer.Option(
        1.0, "--delay", help="Pause de politesse entre scrapes réels (s)."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Rapport machine-lisible en plus du texte."
    ),
) -> None:
    """Amorce la base depuis le Google Sheet des adhérents."""
    settings = get_settings()
    csv_text = _download_csv(sheet_url)
    with session_scope() as db:
        outcome = run_import_sheet(
            db, csv_text, settings,
            dry_run=dry_run, limit=limit, only_provider=only_provider, delay=delay,
        )
    typer.echo(render_sheet_report(outcome, dry_run=dry_run))
    if json_output:
        typer.echo(json.dumps(asdict(outcome), ensure_ascii=False))


if __name__ == "__main__":
    app()
