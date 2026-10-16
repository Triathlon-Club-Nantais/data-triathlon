"""
Scraper fftri.t2area.com — plateforme de résultats officielle de la FFTRI.

Un Joomla qui rend le classement complet en HTML server-rendered : une requête
ramène toutes les lignes (901 sur La Baule M 2022), il n'y a **aucune
pagination**, donc ni API à rétro-concevoir ni Playwright.

La profondeur du chemin dit à quel niveau on est :

    /calendrier/<événement>.html                          événement (refusé)
    /calendrier/<événement>/<épreuve>.html                épreuve (année à résoudre)
    /calendrier/<événement>/<épreuve>/<année>.html        édition ← le classement
    /calendrier/<événement>/<épreuve>/<année>/<clé>.html  fiche individuelle

Flux (cf. docs/scrapers/t2area.md, re-sondé le 30/09/2026 pour #898) :
  1. `_parse_url`      → (événement, épreuve, année) ; une fiche est tronquée
                         vers son édition (le cas réel du Sheet)
  2. `_resolve_year`   → année absente : 1 GET sur l'épreuve, on prend la plus récente
  3. `_fetch_edition`  → GET du classement, en repérant la redirection vers l'accueil
  4. `_parse_edition`  → un `article.edition-result` par participant, splits compris
  5. `_parse_detail`   → pour les **seules** lignes `is_tcn` : GET de la fiche,
                         rangs « Sexe » et « Catégorie » (25 requêtes sur La Baule, pas 901)
"""
import logging
import re
from datetime import date
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core import http
from app.core.club import is_tcn
from app.core.text import strip_accents

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, ScrapedResult
from .classify import classify_event_type
from .utils import (
    DEFAULT_HEADERS,
    derive_status_from_label,
    heat_is_relay,
    normalize_rank,
    normalize_time,
    split_athlete_name,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://fftri.t2area.com"
HOST = "fftri.t2area.com"
HEADERS = {**DEFAULT_HEADERS}

_PREFIX = "/calendrier/"
_YEAR_RE = re.compile(r"^\d{4}$")

def _norm(text: str) -> str:
    """Minuscule, sans accents, espaces aplatis. « Détails » → « details »."""
    unaccented = strip_accents((text or "").strip().lower())
    return re.sub(r"\s+", " ", unaccented)


def _parse_url(url: str) -> tuple[str, str, str]:
    """(événement, épreuve, année). L'année est "" si l'URL n'en porte pas.

    Une **fiche individuelle est tronquée** vers son édition : c'est la forme que
    porte le Sheet. Une **URL d'événement est refusée** : ses épreuves ont des
    dernières éditions d'années différentes (La Baule : `triathlon-m` en 2022,
    `triathlon-jeunes-1` en 2024), un fan-out dont l'année varierait d'une
    épreuve à l'autre n'aurait pas de sens. Un appel = une `Course`.
    """
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() != HOST:
        raise ValueError(f"URL hors fftri.t2area.com : {url}")
    path = parsed.path
    if not path.startswith(_PREFIX) or not path.endswith(".html"):
        raise ValueError(f"URL fftri.t2area.com non reconnue : {url}")
    parts = path[len(_PREFIX):-len(".html")].split("/")
    if not all(parts):
        raise ValueError(f"URL fftri.t2area.com non reconnue : {url}")
    if len(parts) == 1:
        raise ValueError(
            f"URL d'événement fftri.t2area.com ({parts[0]}) : pointez une épreuve "
            "ou une édition, un événement en porte plusieurs."
        )
    if len(parts) > 4:
        raise ValueError(f"URL fftri.t2area.com non reconnue : {url}")
    event, race = parts[0], parts[1]
    if len(parts) == 2:
        return event, race, ""
    year = parts[2]
    if not _YEAR_RE.match(year):
        raise ValueError(f"Année illisible dans l'URL fftri.t2area.com : {url}")
    return event, race, year


def _race_url(event: str, race: str) -> str:
    return f"{BASE_URL}{_PREFIX}{event}/{race}.html"


def _edition_url(event: str, race: str, year: str) -> str:
    return f"{BASE_URL}{_PREFIX}{event}/{race}/{year}.html"


def _fetch(client: httpx.Client, url: str) -> str:
    response = client.get(url)
    response.raise_for_status()
    return response.text


class EditionNotFoundError(ValueError):
    """L'édition n'existe pas : le site répond **303 vers son calendrier**."""


def _fetch_edition(client: httpx.Client, url: str) -> str:
    """GET du classement. Une édition inexistante répond 303 vers
    `/calendrier.html`, donc 200 après la redirection : c'est l'URL finale qui la
    démasque, distincte d'un markup inconnu (#898)."""
    response = client.get(url)
    response.raise_for_status()
    final_url = str(getattr(response, "url", "") or url)
    if urlparse(final_url).path != urlparse(url).path:
        raise EditionNotFoundError(
            f"Édition inexistante sur fftri.t2area.com : {url} redirige vers {final_url}."
        )
    return response.text


def _resolve_year(client: httpx.Client, event: str, race: str) -> str:
    """Année de la dernière édition publiée, lue sur la page d'épreuve.

    Regex sur les `href` bruts plutôt que sur une classe CSS : les liens portent
    `class="btn-fx-1"`, un décor qui peut changer, alors que la forme de l'URL
    est structurelle.
    """
    url = _race_url(event, race)
    html = _fetch(client, url)
    pattern = re.compile(
        rf"{re.escape(_PREFIX)}{re.escape(event)}/{re.escape(race)}/(\d{{4}})\.html"
    )
    years = set(pattern.findall(html))
    if not years:
        raise ValueError(f"Aucune édition publiée pour l'épreuve fftri.t2area.com : {url}")
    return max(years)


_BIB_RE = re.compile(r"^bib-(\d+)$", re.I)

# Abréviation d'équipe propre aux slugs FFTRI (`swim-run-m-eq`), en jeton isolé :
# le « eq » de « equipe » ne doit pas être capté par accident. Les autres mots
# d'équipe viennent du détecteur commun (#963).
_TEAM_RE = re.compile(r"(?<![a-z0-9])eq(?![a-z0-9])")

# Le `<title>` porte l'en-tête (le `<h1>` ne dit plus que « Édition 2022 ») :
#   « Résultats du Triathlon de La Baule - M - 2022 - édition du 18-09-2022 »
# Deux regex **indépendantes** : un libellé inattendu ne doit pas faire perdre la
# date, qui entre dans l'identité de la Course (UNIQUE(name, event_date, event_type)).
_RE_NAME = re.compile(r"r[ée]sultats\s+d[eu]s?\s+(.+?)\s+-\s+\d{4}\s+-\s+[ée]dition\b", re.I)
_RE_DATE = re.compile(r"[ée]dition\s+du\s+(\d{2})-(\d{2})-(\d{4})", re.I)

#: Lien de la fiche individuelle, le seul `edition-details-link` qui reste sous
#: `/calendrier/` (les autres mènent à l'athlète et au club).
_DETAIL_LINK = "a.edition-details-link[href*='/calendrier/']"


def _text(card, selector: str) -> str:
    element = card.select_one(selector)
    return element.get_text(" ", strip=True) if element else ""


def _row(card) -> dict:
    """Une carte `article.edition-result` → ses champs bruts.

    Le club se lit sans son badge de catégorie ni le « · » qui les sépare ; un
    badge sans lettre ni chiffre (« --- », ligne anonyme) vaut catégorie absente.
    """
    club_element = card.select_one(".edition-club")
    badge = _text(card, ".edition-cat-badge")
    club = ""
    if club_element is not None:
        for child in club_element.select(".edition-cat-badge"):
            child.extract()
        club = club_element.get_text(" ", strip=True).rstrip("·").strip()
    link = card.select_one(_DETAIL_LINK)
    return {
        "clt": _text(card, ".edition-rank"),
        "nom": _text(card, ".edition-name"),
        "club": club,
        "cat": badge if any(c.isalnum() for c in badge) else "",
        "genre": (card.get("data-gender") or "").strip().upper(),
        "league": (card.get("data-league") or "").strip(),
        "temps": _text(card, ".edition-time"),
        "details_href": link["href"].strip() if link else "",
        "splits": [
            (_text(split, "small"), _text(split, "b"))
            for split in card.select(".edition-split")
        ],
    }


def _detail_key(href: str) -> str:
    """Dernier segment du href de la colonne Détails, sans son « .html »."""
    last_segment = urlparse(href).path.rsplit("/", 1)[-1]
    return last_segment[:-len(".html")] if last_segment.endswith(".html") else last_segment


def _bib(key: str) -> str:
    """Dossard **seulement** si la clé de fiche en est un (`bib-566` → « 566 »).

    La source n'affiche jamais de dossard ; la clé de fiche est tantôt un dossard,
    tantôt une licence FFTRI (`A44719`), tantôt un identifiant interne
    (`id-1153352`). Remplir `bib_number` avec les deux autres ferait mentir le
    champ — le front afficherait « #A44719 ». Les éditions sans dossard retombent
    sur l'appariement par athlète (`import_persistence`).
    """
    found = _BIB_RE.match(key)
    return found.group(1) if found else ""


def _time_or_empty(raw: str) -> str:
    """Temps normalisé. **`00:00:00` vaut temps absent** — un DNF sort avec cette
    valeur (La Baule 2022, EPP Arnaud) et la laisser ferait basculer
    `mapping.derive_status` sur « finisher »."""
    raw = (raw or "").strip()
    if raw in ("—", "-", "--"):
        return ""
    normalized = normalize_time(raw)
    return "" if normalized in ("", "00:00:00") else normalized


def _gender(category: str) -> str:
    """Préfixe M/F de la catégorie fédérale (`MS2`, `FV1`, `MHAN`, `MT1`)."""
    initial = (category or "").strip()[:1].upper()
    return initial if initial in ("M", "F") else ""


def _is_relay(race: str) -> bool:
    """Déduit du slug d'épreuve. Non vérifié sur données réelles (§8.3 du design) :
    aucune épreuve équipe sondée n'a de classement publié."""
    return heat_is_relay(race) or _TEAM_RE.search(race.lower()) is not None


def _title(soup) -> str:
    """L'en-tête de résultats : le `<title>`, à défaut un `<h1>` qui le porte."""
    candidates = [soup.title.get_text(" ", strip=True)] if soup.title else []
    candidates += [h1.get_text(" ", strip=True) for h1 in soup.find_all("h1")]
    return next((text for text in candidates if _norm(text).startswith("resultats")), "")


def _header(soup, event: str, race: str) -> tuple[str, date | None]:
    """(nom d'épreuve, date), lus indépendamment dans l'en-tête (`_title`).

    Le nom est déjà qualifié par l'épreuve (« - M ») : pas de `qualify_event_name`.
    """
    title = _title(soup)
    found = _RE_NAME.search(title)
    if found:
        name = found.group(1)
    else:
        name = f"{event} {race}".replace("-", " ").title()
        logger.warning(
            "Titre fftri illisible (%r) : nom d'épreuve replié sur les slugs (%s)", title, name
        )
    event_date = None
    day = _RE_DATE.search(title)
    if day:
        try:
            event_date = date(int(day.group(3)), int(day.group(2)), int(day.group(1)))
        except ValueError:
            logger.warning("Date d'édition fftri illisible : %r", day.group(0))
    else:
        logger.warning("Date d'édition absente du titre fftri : %r", title)
    return name, event_date


def _build(
    row: dict,
    *,
    source_url: str,
    event: str,
    race: str,
    event_name: str,
    event_type: str,
    event_date: date | None,
    timekeeper: tuple[str, str],
) -> ScrapedResult:
    """Une carte de classement → un participant.

    Les rangs par genre et par catégorie ne figurent plus sur la liste : ils se
    lisent sur la fiche, chargée pour les seuls membres du club (`scrape_event_all`).
    Les recalculer depuis l'ordre de la liste s'écarte d'une place au-delà de
    quelques centaines de lignes (mesuré, #898).
    """
    last_name, first_name = split_athlete_name(row.get("nom", ""))
    key = _detail_key(row.get("details_href", ""))
    category = row.get("cat", "")
    place = row.get("clt", "")

    result = ScrapedResult(source_url=source_url, provider="t2area")
    result.event_name = event_name
    result.event_type = event_type
    result.event_date = event_date
    result.athlete_name = last_name
    result.athlete_firstname = first_name
    result.club = row.get("club", "")
    result.category = category
    gender = row.get("genre", "")
    result.gender = gender if gender in ("M", "F") else _gender(category)
    result.bib_number = _bib(key)
    result.rank_overall = normalize_rank(place)
    result.total_time = _time_or_empty(row.get("temps", ""))
    # La place porte le statut quand elle ne porte pas de rang (DNF, DSQ).
    result.status = derive_status_from_label(place)
    result.is_relay = _is_relay(race)
    _apply_splits(result, [(label, _time_or_empty(time)) for label, time in row.get("splits", [])])
    # De quoi diagnostiquer sans re-scraper : clé brute, ligue, chronométreur.
    result.raw_data = {
        "cle_fiche": key,
        "fiche_url": row.get("details_href", ""),
        "clt": place,
        "temps": row.get("temps", ""),
        "league": row.get("league", ""),
        "chronometreur": timekeeper[0],
        "chronometreur_url": timekeeper[1],
        "evenement": event,
        "epreuve": race,
    }
    # La FFTRI publie parfois un temps sur ses disqualifiés (ALLARD Pierre,
    # `42:23:00` sur La Baule 2022 — une aberration de saisie côté source).
    # Invariant du dépôt, partagé avec wiclax/sportinnovation/raceresult/
    # timepulse : un non-finisher n'a ni temps total ni rang.
    if result.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
        result.total_time = ""
        result.rank_overall = None
        result.rank_category = None
        result.rank_gender = None
    return result


_RE_TIMEKEEPER = re.compile(r"r[ée]sultats\s+produits\s+par", re.I)


def _timekeeper(soup) -> tuple[str, str]:
    """(nom, lien) du chronométreur amont : « Résultats produits par X »."""
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if not _RE_TIMEKEEPER.search(text):
            continue
        link = p.find("a", href=True)
        if link:
            return link.get_text(" ", strip=True), link["href"].strip()
        return _RE_TIMEKEEPER.sub("", text).strip(), ""
    return "", ""


def _warn_upstream_source(name: str, link: str, url: str) -> None:
    """Journalise quand le chronométreur amont est un provider **supporté**.

    La FFTRI ne chronomètre pas, elle republie : à la source, on aurait les
    dossards de tout le monde et les splits de tous les participants. Cette
    délégation ne peut pas être automatisée — la mention ne lie que la page
    d'accueil du chronométreur, jamais l'épreuve, et aucun identifiant d'épreuve
    n'est récupérable (§1.1 du design). L'opérateur reste seul à pouvoir fournir
    l'URL source.

    Import local de `registry` : `registry` importe ce module au chargement,
    l'inverse au niveau module créerait un cycle (même procédé que les helpers
    Klikego appelés depuis `registry`).
    """
    if not link:
        return
    from app.scrapers.registry import detect_provider

    provider = detect_provider(link)
    if not provider:
        return
    logger.warning(
        "%s : résultats produits par %s (%s) — le provider « %s » est supporté et "
        "sa source est plus riche (dossards et splits de tous les participants). "
        "L'URL d'épreuve n'est pas déductible de cette page : à fournir à la main.",
        url, name or provider, link, provider,
    )


def _parse_edition(
    html: str, source_url: str, event: str, race: str
) -> list[ScrapedResult]:
    """HTML d'une édition → participants. **Pur** : aucune requête.

    Aucune carte sur une page qui n'est pas une redirection (`_fetch_edition`
    l'a déjà écartée) : le markup a changé, et mieux vaut une erreur qu'un
    classement vide importé en silence.
    """
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("article.edition-result")
    if not cards:
        raise ValueError(
            f"Aucun classement (article.edition-result) sur {source_url} : "
            "markup fftri modifié."
        )
    event_name, event_date = _header(soup, event, race)
    # Le type vient du **slug d'épreuve**, vérifié sur les slugs réels :
    # `swim-run-m` → swimrun-m, `triathlon-xs-jeunes` → triathlon-xs,
    # `bike-run-s-open-eq` → bike-run.
    event_type = classify_event_type(race)
    timekeeper = _timekeeper(soup)
    _warn_upstream_source(timekeeper[0], timekeeper[1], source_url)
    return [
        _build(
            _row(card),
            source_url=source_url,
            event=event,
            race=race,
            event_name=event_name,
            event_type=event_type,
            event_date=event_date,
            timekeeper=timekeeper,
        )
        for card in cards
    ]


# Libellé de split normalisé → slot positionnel de ScrapedResult. Les libellés
# **changent selon le sport** (triathlon : Natation / T1 / Vélo / T2 / Course à
# Pied ; duathlon : CàP 1 / T1 / Vélo / T2 / CàP 2), d'où un mapping par libellé
# et jamais par position : un mapping positionnel rangerait le 3ᵉ segment d'un
# aquathlon (Natation / T1 / CàP) dans le vélo.
_SLOTS = {
    "natation": "swim_time",
    "cap 1": "swim_time",
    "t1": "t1_time",
    "transition 1": "t1_time",
    "velo": "bike_time",
    "t2": "t2_time",
    "transition 2": "t2_time",
    "course a pied": "run_time",
    "cap 2": "run_time",
}

_DETAIL_RANKS = {"sexe": "rank_gender", "categorie": "rank_category"}


def _parse_detail(html: str) -> dict[str, int]:
    """Rangs officiels d'une fiche individuelle : `{"rank_gender": …, "rank_category": …}`.

    Le bandeau porte « 453 Global », « 419 Sexe », « 89 Catégorie » : la liste
    ne publie plus que le rang global.
    """
    soup = BeautifulSoup(html, "lxml")
    ranks: dict[str, int] = {}
    for block in soup.select(".rd-rank"):
        words = block.get_text(" ", strip=True).split()
        if len(words) < 2:
            continue
        field = _DETAIL_RANKS.get(_norm(words[-1]))
        rank = normalize_rank(words[0])
        if field and rank is not None:
            ranks[field] = rank
    return ranks


def _apply_splits(result: ScrapedResult, segments: list[tuple[str, str]]) -> None:
    """Range les segments dans les 5 slots, ou bascule **tout** sur `segments`.

    Filet : un seul libellé hors table suffit à basculer sur la liste ordonnée
    étiquetée, déplafonnée et prioritaire dans `mapping.build_splits`. Rien n'est
    perdu silencieusement sur un sport au découpage inattendu, et le cas nominal
    garde les clés canoniques que le front sait afficher.
    """
    slotted: dict[str, str] = {}
    for label, time in segments:
        slot = _SLOTS.get(_norm(label))
        if slot is None:
            result.segments = [(seg_label, seg_time) for seg_label, seg_time in segments if seg_time]
            return
        if time:
            slotted[slot] = time
    for slot, time in slotted.items():
        setattr(result, slot, time)


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Tous les participants d'une **édition**. Un appel = une `Course`.

    Les splits de tous les participants sont sur la liste. Les rangs par genre
    et par catégorie, eux, ne sont que sur la fiche individuelle, soit une
    requête par participant : ils ne sont chargés que pour les lignes dont le
    club passe `core.club.is_tcn`. Coût mesuré sur La Baule M 2022 : 25 requêtes
    (1 classement + 24 membres TCN sur 901 lignes), borné par l'effectif du
    club. Le scraper devient conscient du club, mais **réutilise** la définition
    unique de `core/club.py` (règle de #76).

    Chaque `ScrapedResult` porte `source_url` = l'URL **soumise** par l'appelant.
    C'est cette URL qui devient `Course.source_url` (clé de cache TTL), pas
    l'URL canonique de l'édition à laquelle elle est tronquée : si le Sheet
    donne une URL de fiche, l'idempotence tient à cette troncature répétée
    par ce scraper, pas à une réécriture de la clé stockée.
    """
    event, race, year = _parse_url(url)
    with http.client(timeout=30, headers=HEADERS) as client:
        if not year:
            year = _resolve_year(client, event, race)
        edition_url = _edition_url(event, race, year)
        results = _parse_edition(
            _fetch_edition(client, edition_url), edition_url, event, race
        )
        for result in results:
            result.source_url = url
        tcn_members = 0
        detail_pages = 0
        for result in results:
            if not is_tcn(result.club) or result.status:
                continue
            tcn_members += 1
            raw = result.raw_data.get("fiche_url") or ""
            if not raw:
                continue
            # `urljoin` + contrôle de host : un lien de fiche relatif ne doit ni
            # suivre un chemin résolu contre le mauvais host, ni lever une
            # exception masquée par l'`except` ci-dessous.
            detail_url = urljoin(BASE_URL, raw)
            if (urlparse(detail_url).hostname or "").lower() != HOST:
                continue
            try:
                html = _fetch(client, detail_url)
            except httpx.HTTPError as exc:
                # Une fiche qui tombe ne doit pas emporter l'épreuve entière.
                logger.warning("Fiche fftri %s ignorée : %s", detail_url, exc)
                continue
            for field, rank in _parse_detail(html).items():
                setattr(result, field, rank)
            detail_pages += 1
    logger.info(
        "fftri.t2area.com : %d participants sur %s (%d membre(s) TCN classé(s), "
        "%d fiche(s) chargée(s))",
        len(results), edition_url, tcn_members, detail_pages,
    )
    return results
