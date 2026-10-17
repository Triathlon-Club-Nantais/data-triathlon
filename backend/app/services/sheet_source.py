"""Source Google Sheet : téléchargement du CSV, extraction et normalisation des liens.

Aucun accès DB, aucun scraping — juste la lecture de la source d'entrée de
l'import de masse.
"""
import csv
import io
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from app.core import http
from app.core.exceptions import DomainError
from app.core.text import strip_accents
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
    """Dédoublonne par URL normalisée en conservant l'ordre et la forme d'origine.

    `setdefault` garde la **première** forme rencontrée, pas la dernière : c'est
    ce qui interdit un simple `dict.fromkeys`, qui garderait la clé normalisée.
    Même motif que `rescrape_service._dedupe_by_url`.
    """
    unique: dict[str, str] = {}
    for url in links:
        unique.setdefault(normalize_url(url), url)
    return list(unique.values())


class UnsupportedFileError(DomainError):
    status_code = 422
    message = "Format non pris en charge. Seuls les fichiers .csv et .xlsx sont lus."


class UnreadableFileError(DomainError):
    status_code = 422
    message = "Fichier illisible. Vérifiez qu'il s'agit bien d'un .csv ou d'un .xlsx."


def read_table(content: bytes, filename: str) -> tuple[list[str], list[list[str]]]:
    """(en-têtes, lignes) d'un `.csv` ou d'un `.xlsx`, **en mémoire**.

    Le fichier téléversé n'est jamais écrit côté serveur (FR-011) : il arrive en
    octets et repart en listes. Le navigateur, lui, le garde entre l'appel qui
    liste les colonnes et celui qui lance le batch.

    Toute cellule ressort en `str` : `openpyxl` rend `None` pour une case vide
    et un `int` pour un nombre, et les deux feraient tomber `.startswith` en
    aval. Un en-tête vide devient « Colonne N » — une colonne qu'on ne peut pas
    nommer est une colonne qu'on ne peut pas désigner.
    """
    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if extension == "csv":
        rows = _csv_rows(content)
    elif extension == "xlsx":
        rows = _xlsx_rows(content)
    else:
        raise UnsupportedFileError

    if not rows:
        return [], []
    # Rang **à partir de 1** : c'est un libellé lu par un humain, et « Colonne 0 »
    # ne désigne rien pour lui. L'`index` du contrat, lui, reste à partir de 0 —
    # il ne s'affiche jamais.
    headers = [
        cell or f"Colonne {position}" for position, cell in enumerate(rows[0], 1)
    ]
    return headers, rows[1:]


def header_key(header: str) -> str:
    """En-tête comparable : sans accents, ponctuation ni casse (« E-mail » → « email »)."""
    return "".join(c for c in strip_accents(header) if c.isalnum()).casefold()


def column_index(headers: list[str], accepted: set[str]) -> int | None:
    """Rang de la première colonne dont l'en-tête normalisé est accepté."""
    return next((i for i, h in enumerate(headers) if header_key(h) in accepted), None)


def _csv_rows(content: bytes) -> list[list[str]]:
    # Les exports d'un tableur français arrivent souvent en cp1252 ; échouer sur
    # un accent rendrait l'écran inutilisable un jour sur deux. `cp1252` accepte
    # tout octet, donc ce repli ne lève jamais.
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1252")
    # Une cellule au-delà de `csv.field_size_limit` (131 072 caractères) n'est
    # pas un lien d'épreuve : refusée comme illisible plutôt qu'en 500 (#1098).
    try:
        return [
            [(cell or "").strip() for cell in row]
            for row in csv.reader(io.StringIO(text))
        ]
    except csv.Error as error:
        raise UnreadableFileError from error


def _xlsx_rows(content: bytes) -> list[list[str]]:
    from openpyxl import load_workbook

    try:
        # `read_only` ne charge pas la feuille entière en mémoire ; `data_only`
        # rend la valeur calculée d'une formule plutôt que la formule elle-même
        # — un lien produit par `=CONCATENER(...)` sortirait sinon en texte de
        # formule, et ne compterait pour aucun lien.
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as error:
        raise UnreadableFileError from error
    # En `read_only`, la feuille n'est parsée qu'ici : une feuille corrompue
    # lève pendant `iter_rows`, hors du `try` de `load_workbook` (#1098).
    try:
        return [
            ["" if cell is None else str(cell).strip() for cell in row]
            for row in workbook.active.iter_rows(values_only=True)
        ]
    except Exception as error:
        raise UnreadableFileError from error
    finally:
        workbook.close()


@dataclass(frozen=True)
class ColumnLinks:
    """Ce qu'une colonne porte, vu avant tout lancement."""

    links: list[str]           # dédoublonnés, ordre d'origine conservé
    supported: list[str]       # ceux qu'un scraper du registre reconnaît
    ignored_by_host: dict[str, int]  # les autres, groupés par hôte
    rows_without_link: int     # lignes non vides ne portant pas d'URL

    @property
    def count(self) -> int:
        """Le compte affiché en face de la colonne dans le sélecteur."""
        return len(self.links)


def links_in_column(rows: list[list[str]], index: int) -> ColumnLinks:
    """Les liens d'une colonne, dédoublonnés et partagés supportés / ignorés.

    Le partage est fait **avant** le lancement, et c'est ce qui permet à l'écran
    d'annoncer ce qui ne sera jamais soumis. Un lien ignoré n'est ni un succès
    ni un échec ; le confondre avec l'un des deux fausse tous les compteurs.
    """
    raw_links: list[str] = []
    without_link = 0
    for row in rows:
        value = row[index].strip() if index < len(row) else ""
        if value.startswith("http"):
            raw_links.append(value)
        elif value:
            without_link += 1

    links = dedupe_links(raw_links)
    supported = [url for url in links if registry.is_supported(url)]
    ignored: dict[str, int] = {}
    for url in links:
        if url not in supported:
            ignored[host_of(url)] = ignored.get(host_of(url), 0) + 1
    return ColumnLinks(
        links=links,
        supported=supported,
        ignored_by_host=ignored,
        rows_without_link=without_link,
    )


def parse_sheet_csv(csv_text: str) -> tuple[list[str], int]:
    """Extrait la colonne des liens du CSV — **défauts de la commande CLI**.

    `LINK_HEADER` et l'index 9 sont les repères du Sheet historique du club, et
    ils restent ici : la CLI, elle, n'a personne pour désigner une colonne.
    L'écran d'administration passe par `read_table` + `links_in_column` et
    demande la colonne, ce qui est précisément la différence entre les deux
    guichets.

    Ne dédoublonne pas : `bulk_import_service` le fait plus loin, et le compte
    brut de liens fait partie de son bilan.
    """
    headers, rows = read_table(csv_text.encode("utf-8"), "sheet.csv")
    if not headers:
        return [], 0
    try:
        col = headers.index(LINK_HEADER)
    except ValueError:
        col = LINK_COLUMN_FALLBACK_INDEX

    links: list[str] = []
    without_link = 0
    for row in rows:
        value = row[col].strip() if col < len(row) else ""
        if value.startswith("http"):
            links.append(value)
        elif any(cell.strip() for cell in row):
            without_link += 1
    return links, without_link


def host_of(url: str) -> str:
    """Host en minuscule, pour grouper les liens ignorés dans le rapport."""
    return (urlparse(url).netloc or "").lower() or "(inconnu)"


def download_csv(url: str) -> str:
    """Télécharge le CSV public du Sheet (sans auth).

    L'export d'un Google Sheet redirige vers `googleusercontent.com`, un autre
    domaine : c'est le cas qui a fait écarter l'allowlist de hosts par provider
    au profit de la politique par classe d'IP (#101).
    """
    with http.client(timeout=30) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text
