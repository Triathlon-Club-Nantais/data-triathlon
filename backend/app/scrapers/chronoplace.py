"""
Scraper chronoplace.fr — chronométreur sarthois, application Laravel + Livewire.

URL de classement :
  https://www.chronoplace.fr/classement/<slug>/epreuve/<id>

Le composant Livewire `classement-table` synchronise ses paramètres avec l'URL
(son `wire:effects` déclare `search`, `sortField`, `perPage`, `page`) : un simple
`GET ?perPage=all` rend le classement complet (219 lignes sur l'épreuve sondée,
contre 50 par défaut). D'où ni POST `/livewire/update` — dont le snapshot et le
checksum seraient à re-signer à chaque déploiement du site — ni parsing du PDF
de classement.

Flux (cf. docs/superpowers/specs/2026-07-25-chronoplace-scraper-design.md) :
  1. `_parse_url`        → (slug, epreuve_id)
  2. `_fetch`            → GET de l'épreuve avec `?perPage=all`
  3. `_parse_snapshot`   → isTeam + analyticsContext (année, type, nom d'épreuve)
  4. `_parse_table`      → une ligne = {clé de colonne → cellule}, lues **par clé**
                           (`sortBy('...')` du `<th>`), jamais par position
  5. `_fetch_event_date` → 1 GET sur l'annuaire /recherche (la date est absente
                           de la page de classement)
  6. les épreuves sœurs de l'événement (onglets) sont importées elles aussi
"""
import json
import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .classify import classify_event_type
from .utils import normalize_time

logger = logging.getLogger(__name__)

BASE_URL = "https://www.chronoplace.fr"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

_URL_RE = re.compile(r"^/classement/(?P<slug>[^/]+)(?:/epreuve/(?P<id>\d+))?/?$")
_SORT_RE = re.compile(r"sortBy\('([^']+)'\)")
# Ce à quoi doit ressembler une valeur pour être prise pour un temps. Le site
# rend « — » sur un split vide et « -- » / « +5:16 » dans la colonne d'écart :
# `normalize_time` les laisse passer tels quels, il faut donc filtrer ici.
_TIME_RE = re.compile(r"^\d{1,3}:\d{2}:\d{2}$")

# Marqueurs d'une participation en équipe dans la colonne `categorie`
# (« Relais Mixte », « Duo Masculin »…), comparés sans accents ni casse.
_ACCENTS = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")
_RELAY_HINTS = ("relais", "duo", "equipe")


def _parse_url(url: str) -> tuple[str, str]:
    """(slug, id d'épreuve). L'id est "" si l'URL ne pointe que l'événement."""
    m = _URL_RE.match(urlparse(url).path)
    if not m:
        raise ValueError(f"URL chronoplace.fr non reconnue : {url}")
    return m.group("slug"), m.group("id") or ""


def _epreuve_path(slug: str, epreuve_id: str) -> str:
    """Chemin du classement **complet** d'une épreuve."""
    return f"/classement/{slug}/epreuve/{epreuve_id}?perPage=all"


def _unwrap(value):
    """Déballe un tableau sérialisé par Livewire : `[valeur, {"s": "arr"}]` → valeur."""
    if (
        isinstance(value, list) and len(value) == 2
        and isinstance(value[1], dict) and value[1].get("s") == "arr"
    ):
        return value[0]
    return value


def _parse_snapshot(html: str) -> dict:
    """Le `data` du composant `classement-table`, tableaux déballés.

    Préféré aux attributs `data-track-*` dispersés dans le markup : tout y est
    déjà structuré (isTeam, inventaire des colonnes, contexte analytics).
    """
    el = BeautifulSoup(html, "lxml").find(attrs={"wire:snapshot": True})
    if not el:
        return {}
    try:
        data = json.loads(el["wire:snapshot"]).get("data", {})
    except (json.JSONDecodeError, TypeError):
        logger.warning("wire:snapshot illisible")
        return {}
    return {key: _unwrap(value) for key, value in data.items()}


def _column_keys(table) -> list[str]:
    """Clé de chaque colonne, lue dans `wire:click="sortBy('<clé>')"` du `<th>`.

    Vocabulaire fermé : position, dossard, nom, genre, club, categorie,
    clasmt_genre, nb_tours, ecart, temps, T_natation, T1, T_velo, T2,
    T_course_a_pied. Un `<th>` sans `sortBy` occupe une place vide pour ne pas
    décaler les colonnes suivantes.
    """
    keys = []
    for th in table.select("thead th"):
        m = _SORT_RE.search(th.get("wire:click") or "")
        keys.append(m.group(1) if m else "")
    return keys


def _parse_table(html: str) -> list[dict[str, str]]:
    """Lignes du classement : une ligne = {clé de colonne → texte de la cellule}.

    `thead` et `tbody` partagent les mêmes conditions d'affichage Livewire
    (`<!--[if BLOCK]-->`), donc l'alignement en-tête ↔ cellule est garanti ; une
    ligne au compte divergent est une anomalie, journalisée et sautée plutôt
    que décalée.
    """
    table = BeautifulSoup(html, "lxml").find("table")
    if table is None:
        return []
    keys = _column_keys(table)
    if not any(keys):
        return []
    rows = []
    for tr in table.select("tbody tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(cells) != len(keys):
            logger.warning("Ligne ignorée : %d cellules pour %d colonnes", len(cells), len(keys))
            continue
        rows.append({key: value for key, value in zip(keys, cells, strict=True) if key})
    return rows


def _time_or_empty(raw: str) -> str:
    """Temps normalisé, ou "" si la valeur n'en est pas un."""
    normalized = normalize_time((raw or "").strip())
    return normalized if _TIME_RE.match(normalized) else ""


def _event_name(html: str, slug: str) -> str:
    """Nom de la Course : « <événement> - <épreuve> », depuis le `<h1>`.

    Le nom de l'épreuve **doit** y figurer, sinon deux épreuves d'un même
    événement partageant date et type fusionneraient (`uq_course_identity`).
    Replis : meta `description` privée de son préfixe « Résultats », puis slug.
    """
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    if h1:
        text = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)).strip()
        if text:
            return text
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return re.sub(r"^Résultats\s+", "", meta["content"].strip())
    return slug.replace("-", " ").title()


def _list_epreuves(html: str, slug: str) -> list[str]:
    """Ids des épreuves sœurs, lus dans les onglets de la page (ordre du document).

    Filtre sur le slug de l'événement courant : un lien vers un autre événement
    n'a rien à faire dans l'import.
    """
    pattern = re.compile(rf"^/classement/{re.escape(slug)}/epreuve/(\d+)/?$")
    ids: list[str] = []
    for a in BeautifulSoup(html, "lxml").find_all("a", href=True):
        m = pattern.match(a["href"].strip())
        if m and m.group(1) not in ids:
            ids.append(m.group(1))
    return ids


def _event_type(analytics: dict, event_name: str) -> str:
    """Type d'épreuve, classé sur le **nom d'épreuve**.

    `analyticsContext.event_type` décrit l'**événement**, pas l'épreuve : celui de
    Spay'cific est typé « Triathlon » alors qu'il porte aussi un swimrun. Il ne
    sert donc que de repli.
    """
    label = analytics.get("epreuve_name") or analytics.get("event_type") or event_name
    return classify_event_type(label)


def _is_relay_category(category: str) -> bool:
    """Vrai si la catégorie désigne une équipe (« Relais Mixte », « Duo Masculin »)."""
    normalized = (category or "").strip().lower().translate(_ACCENTS)
    return any(hint in normalized for hint in _RELAY_HINTS)
