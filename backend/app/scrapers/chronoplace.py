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
from datetime import date
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .base import ScrapedResult
from .classify import classify_event_type
from .utils import normalize_rank, normalize_time, parse_fr_date, split_athlete_name

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
# Utilisé par `_parse_event_date` pour compter les liens /classement/ d'un ancêtre.
_CLASSEMENT_HREF_RE = re.compile(r"/classement/")
# Ce à quoi doit ressembler une valeur pour être prise pour un temps. Le site
# rend « — » sur un split vide et « -- » / « +5:16 » dans la colonne d'écart :
# `normalize_time` les laisse passer tels quels, il faut donc filtrer ici.
_TIME_RE = re.compile(r"^\d{1,3}:\d{2}:\d{2}$")

# Marqueurs d'une participation en équipe dans la colonne `categorie`
# (« Relais Mixte », « Duo Masculin »…), comparés sans accents ni casse.
_ACCENTS = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")
_RELAY_HINTS = ("relais", "duo", "equipe")

# Ids de catégorie de l'annuaire /recherche, relevés dans le `<select name="categorie">`
# de /classements. Table statique : 17 entrées, changement improbable, et la date
# n'est qu'un bonus (catégorie inconnue → pas de recherche, pas de date).
_CATEGORY_IDS = {
    "caisse à savon": 10, "canicross": 14, "course à pied": 2,
    "courses de tracteurs tondeuses": 19, "cyclisme": 4, "cyclo-cross": 3,
    "duathlon": 18, "fauteuils roulants": 17, "gravel": 13, "hyrox": 16,
    "moto cross": 11, "multiple": 9, "trail": 1, "triathlon": 12,
    "voiture à pédales": 15, "vtt": 5, "xco": 7,
}

# Colonne source → slot positionnel de ScrapedResult. Les slots portent des noms
# triathlon par convention ; services/mapping.build_splits les ré-étiquette selon
# `event_type` (duathlon → course1/course2, swimrun → swim/run…).
_SPLIT_FIELDS = {
    "T_natation": "swim_time",
    "T1": "t1_time",
    "T_velo": "bike_time",
    "T2": "t2_time",
    "T_course_a_pied": "run_time",
}


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
    unwrapped = {key: _unwrap(value) for key, value in data.items()}
    # Garde-fou : si Livewire changeait sa sérialisation, `analyticsContext`
    # pourrait rester une liste après déballage. Les appelants font tous
    # `.get(...)` dessus ; un dict vide évite un `AttributeError` cryptique.
    if not isinstance(unwrapped.get("analyticsContext"), dict):
        unwrapped["analyticsContext"] = {}
    return unwrapped


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


def _find_table(soup: BeautifulSoup):
    """La `<table>` du composant `classement-table`, repérée via `wire:snapshot`.

    Scoper à cet élément porteur évite de prendre « la première table de la
    page » si une autre `<table>` (bandeau, pub…) précède le composant. Repli
    sur le document entier **seulement si l'élément est absent** : les HTML de
    test réduits (`test_parse_table_ignore_une_ligne_desalignee`) sont une
    `<table>` nue, sans `wire:snapshot` — un ciblage strict casserait ce cas
    légitime. En revanche, un composant présent mais privé de sa `<table>` est
    une anomalie de markup : `None` laisse `_parse_table` la journaliser, là où
    un repli irait lire une table décorative hors composant.
    """
    container = soup.find(attrs={"wire:snapshot": True})
    if container is not None:
        return container.find("table")
    return soup.find("table")


def _parse_table(html: str) -> list[dict[str, str]]:
    """Lignes du classement : une ligne = {clé de colonne → texte de la cellule}.

    `thead` et `tbody` partagent les mêmes conditions d'affichage Livewire
    (`<!--[if BLOCK]-->`), donc l'alignement en-tête ↔ cellule est garanti ; une
    ligne au compte divergent est une anomalie, journalisée et sautée plutôt
    que décalée.

    Deux anomalies structurelles sont journalisées (`<table>` absente, ou
    aucune clé `sortBy` dans le `thead` : le markup a changé) car un import
    silencieux à 0 participant ne se distinguerait pas d'un succès. À
    l'inverse, un `<tbody>` vide (épreuve créée mais pas encore chronométrée)
    est un cas légitime : `[]` sans un mot.
    """
    table = _find_table(BeautifulSoup(html, "lxml"))
    if table is None:
        logger.warning("Page de classement sans <table> : markup chronoplace inattendu.")
        return []
    keys = _column_keys(table)
    if not any(keys):
        logger.warning(
            "Aucune clé de colonne (wire:click=\"sortBy(...)\") dans le <thead> : "
            "markup chronoplace inattendu."
        )
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


# Marqueurs connus d'une cellule de temps vide de sens (case vide, tiret cadratin
# de split non chronométré, écart nul ou signé) : leur rejet par `_time_or_empty`
# est normal et ne doit rien journaliser.
_KNOWN_NON_TIME_VALUES = ("", "—", "--")


def _is_unknown_time_rejection(raw: str) -> bool:
    """Vrai si `_time_or_empty` rejette `raw` sans que ce soit un marqueur connu.

    Distingue le cas légitime (`""`, `—`, `--`, `+5:16`) d'un format de temps
    réellement inattendu (ex. des dixièmes ajoutés par le site) : ce dernier ne
    doit pas se noyer en DNF silencieux (Important 2 de la revue).
    """
    value = (raw or "").strip()
    if value in _KNOWN_NON_TIME_VALUES or value.startswith("+"):
        return False
    return _time_or_empty(value) == ""


# Colonnes passées à `_time_or_empty` dans `_build_result` : le temps total, plus
# les 5 splits positionnels. `ecart` et `nb_tours` n'en font pas partie : ce ne
# sont pas des temps (cf. `raw_data`).
_TIME_COLUMNS = ("temps", *_SPLIT_FIELDS.keys())


def _log_unknown_time_rejections(rows: list[dict[str, str]], slug: str) -> None:
    """Signal agrégé (une fois par épreuve, pas une fois par cellule) des rejets
    de temps au format inconnu. Pas d'état global : tout vit dans cet appel.

    L'échantillon nomme la colonne, car la conséquence en dépend : seul un rejet
    sur `temps` prive la participation de temps total, donc la fait classer DNF
    par `mapping.derive_status` ; un split rejeté laisse juste ce segment vide.
    """
    inconnues = [
        f"{column}={row[column]!r}"
        for row in rows
        for column in _TIME_COLUMNS
        if column in row and _is_unknown_time_rejection(row[column])
    ]
    if inconnues:
        logger.warning(
            "Épreuve %s : %d cellule(s) de temps au format inattendu — un rejet "
            "sur « temps » fait classer la participation DNF, un rejet sur un "
            "split laisse le segment vide (échantillon : %s)",
            slug, len(inconnues), inconnues[:5],
        )


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
    n'a rien à faire dans l'import. `urlparse(href).path` neutralise le cas d'un
    href absolu (`https://www.chronoplace.fr/classement/...`) : sans lui, un
    passage du site aux URLs absolues ferait disparaître les épreuves sœurs en
    silence.
    """
    pattern = re.compile(rf"^/classement/{re.escape(slug)}/epreuve/(\d+)/?$")
    ids: list[str] = []
    for a in BeautifulSoup(html, "lxml").find_all("a", href=True):
        m = pattern.match(urlparse(a["href"].strip()).path)
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


def _fetch(client: httpx.Client, path: str, *, message_404: str | None = None) -> str:
    """GET sur le site. 404 → `ValueError` explicite (le site exige slug + id exacts).

    `message_404` permet aux appelants dont la page 404 n'est pas un classement
    (l'annuaire /recherche, par ex.) de fournir un message adapté : le défaut
    parle d'« épreuve », ce qui serait trompeur ailleurs.
    """
    response = client.get(f"{BASE_URL}{path}")
    if response.status_code == 404:
        raise ValueError(
            message_404
            or f"Épreuve chronoplace introuvable ({path}) : slug obsolète ou épreuve retirée."
        )
    response.raise_for_status()
    return response.text


def _parse_event_date(html: str, slug: str) -> date | None:
    """Date lue sur la carte de l'annuaire qui pointe vers ce slug.

    La carte porte `<time datetime="2025-09-21 00:00:00">21 septembre 2025</time>`
    dans un ancêtre du lien : on remonte les parents jusqu'à le trouver. Repli sur
    le texte français si l'attribut manque.

    Garde-fou : un ancêtre n'est retenu que s'il ne contient qu'un seul lien
    `/classement/` — sur un markup aplati (cartes non isolées par un conteneur
    propre), un ancêtre plus large engloberait plusieurs événements et son
    premier `<time>` en document ne serait pas forcément le bon. Mieux vaut
    `None` (contrat du design) qu'une date d'un autre événement.
    """
    for a in BeautifulSoup(html, "lxml").find_all("a", href=True):
        if f"/classement/{slug}/" not in a["href"]:
            continue
        node = a
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            time_el = node.find("time")
            if not time_el:
                continue
            if len(node.find_all("a", href=_CLASSEMENT_HREF_RE)) > 1:
                continue  # ancêtre trop large : plusieurs événements dedans
            try:
                return date.fromisoformat((time_el.get("datetime") or "")[:10])
            except ValueError:
                return parse_fr_date(time_el.get_text(" ", strip=True))
    return None


def _fetch_event_date(client: httpx.Client, slug: str, year: str, category_label: str) -> date | None:
    """Date de l'événement via l'annuaire filtré (1 requête). `None` en cas de doute.

    La page de classement ne porte aucune date. Filtrer par année + catégorie
    ramène l'annuaire à une seule page, donc pas de pagination à parcourir.
    """
    if not year:
        logger.info("Date non cherchée pour %s : année d'événement inconnue.", slug)
        return None
    category_id = _CATEGORY_IDS.get((category_label or "").strip().lower())
    if not category_id:
        logger.info("Date non cherchée pour %s (catégorie %r inconnue)", slug, category_label)
        return None
    path = f"/recherche?module=classement&annee={year}&categorie={category_id}"
    try:
        html = _fetch(
            client,
            path,
            message_404=f"Annuaire chronoplace introuvable ({path}).",
        )
    except (ValueError, httpx.HTTPError) as exc:
        logger.warning("Annuaire /recherche indisponible pour %s : %s", slug, exc)
        return None
    return _parse_event_date(html, slug)


def _build_result(
    row: dict[str, str],
    *,
    url: str,
    event_name: str,
    event_type: str,
    event_date: date | None,
    is_team: bool,
) -> ScrapedResult:
    """Une ligne de classement → un participant.

    `status` reste vide : aucun label DNF/DNS/DSQ n'a été observé sur les épreuves
    sondées, et `services/mapping.derive_status` applique alors son heuristique.
    """
    surname, firstname = split_athlete_name(row.get("nom", ""))
    category = (row.get("categorie") or "").strip()

    result = ScrapedResult(source_url=url, provider="chronoplace")
    result.event_name = event_name
    result.event_type = event_type
    result.event_date = event_date
    result.athlete_name = surname
    result.athlete_firstname = firstname
    result.bib_number = (row.get("dossard") or "").strip()
    result.club = (row.get("club") or "").strip()
    result.category = category
    result.gender = (row.get("genre") or "").strip()
    result.rank_overall = normalize_rank(row.get("position"))
    result.rank_gender = normalize_rank(row.get("clasmt_genre"))
    # rank_category reste None : aucune colonne source ne le porte (contrairement
    # à `status`, aucune classe cachée n'a été observée à corriger davantage).
    result.total_time = _time_or_empty(row.get("temps", ""))
    for column, field in _SPLIT_FIELDS.items():
        setattr(result, field, _time_or_empty(row.get(column, "")))
    result.is_relay = bool(is_team) or _is_relay_category(category)
    # Tout le brut est conservé : `nb_tours` et `ecart` ne vivent que là.
    result.raw_data = dict(row)
    return result


def _epreuve_results(
    html: str, url: str, slug: str, event_date: date | None
) -> list[ScrapedResult]:
    """HTML d'une page de classement → participants. Pur : aucune requête."""
    snapshot = _parse_snapshot(html)
    analytics = snapshot.get("analyticsContext") or {}
    event_name = _event_name(html, slug)
    event_type = _event_type(analytics, event_name)
    is_team = bool(snapshot.get("isTeam"))
    rows = _parse_table(html)
    _log_unknown_time_rejections(rows, slug)
    return [
        _build_result(
            row,
            url=url,
            event_name=event_name,
            event_type=event_type,
            event_date=event_date,
            is_team=is_team,
        )
        for row in rows
    ]


def _resolve_epreuve_id(client: httpx.Client, slug: str) -> str:
    """Id de la première épreuve d'un événement, pour une URL sans `/epreuve/<id>`.

    Le site redirige bien `/classement/<slug>` vers cette épreuve, mais la
    redirection **perd la query string** : suivre le 302 avec `?perPage=all`
    rendrait les 50 premières lignes seulement. On résout donc l'id d'abord.
    """
    html = _fetch(client, f"/classement/{slug}")
    epreuve_id = str(_parse_snapshot(html).get("epreuveId") or "")
    if not epreuve_id:
        raise ValueError(f"Aucune épreuve trouvée pour l'événement chronoplace « {slug} ».")
    return epreuve_id


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Tous les participants de **toutes** les épreuves de l'événement.

    Une URL pointe une épreuve, mais la page liste ses sœurs (onglets) : on les
    importe toutes, comme les heats Breizh Chrono. Coût : une requête par épreuve.
    """
    slug, epreuve_id = _parse_url(url)
    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        if not epreuve_id:
            epreuve_id = _resolve_epreuve_id(client, slug)
        html = _fetch(client, _epreuve_path(slug, epreuve_id))

        # La date vaut pour l'événement entier : une seule requête d'annuaire.
        analytics = _parse_snapshot(html).get("analyticsContext") or {}
        event_date = _fetch_event_date(
            client, slug, analytics.get("event_year", ""), analytics.get("event_type", "")
        )

        results = _epreuve_results(html, url, slug, event_date)
        done = {epreuve_id}
        for sibling in _list_epreuves(html, slug):
            if sibling in done:
                continue
            done.add(sibling)
            try:
                page = _fetch(client, _epreuve_path(slug, sibling))
            except (ValueError, httpx.HTTPError) as exc:
                # Une sœur en échec ne doit pas emporter l'épreuve demandée.
                logger.warning("Épreuve sœur %s ignorée : %s", sibling, exc)
                continue
            results.extend(_epreuve_results(page, url, slug, event_date))
    return results
