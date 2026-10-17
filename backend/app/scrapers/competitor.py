"""
Competitor / WTC — moteur des résultats IRONMAN et IRONMAN 70.3 (issue #54).

`ironman.com` n'affiche aucun résultat en propre : sa page « Results » encastre
une iframe `labs-v2.competitor.com`, application Next.js (Pages Router) dont les
données sont embarquées dans `__NEXT_DATA__`. Le provider est donc nommé
`competitor` — c'est le moteur réel, commun à toutes les épreuves de la marque.

Flux d'appels :

    scrape_event_all(url)
      ├─ _uuid_from_url(url)                → uuid porté par une URL competitor.com
      ├─ _resolve_uuid(client, url)         → sinon, GET ironman.com + iframe
      ├─ _fetch_next_data(client, uuid)     → GET labs-v2 → pageProps
      ├─ _choose_edition(props, uuid)       → l'édition (année) à importer
      └─ _rows(client, edition_id)          → proxy OData, pagination suivie

**Une URL désigne une série, pas une édition.** `…/results/event/{uuid}` rend les
21 éditions d'IRONMAN France (2005→2025) dans `subevents`, mais ne publie que
les résultats de la plus récente (`latestResultSubeventId`) : le sélecteur
d'année du site est purement client, aucune URL ne la porte. On importe donc la
dernière édition — sauf si l'uuid de l'URL désigne lui-même une édition de la
liste, auquel cas c'est celle-là. Cela donne une adressabilité par année que le
site n'offre pas, sans requête supplémentaire.

Trois pièges de la source qu'il ne faut pas réintroduire :

1. `api.competitor.com` n'est **pas** joignable en direct (401, clé d'abonnement
   APIM manquante). La seule porte est le proxy `labs-v2.competitor.com/api/
   results-proxy?url=…`, qui valide sa cible : seule l'entité `/web/results`
   passe, toute autre sort en 400 « Invalid results URL ». Le `@odata.nextLink`
   revient sous la forme `/web/wtc_results?`, que l'API rejette en 404 : il doit
   être réécrit en `/web/results?`, exactement comme le fait le front.
2. `athlete`, `bib` et `countryiso2` sont fabriqués **côté navigateur** : ils
   sont présents dans `latestResults` (rendu serveur) mais absents des pages
   servies par le proxy. Toute lecture doit repartir de `wtc_ContactId` /
   `wtc_bibnumber`.
3. `latestResults` **n'est pas le classement complet** : le rendu serveur y
   applique déjà le filtre `wtc_AgeGroupId/wtc_agegroupname ne 'ODIV'` du site,
   qui écarte l'Open Division — 62 athlètes sur 1810 à IRONMAN France 2025. On
   ne le réutilise donc pas : le classement est toujours redemandé au proxy
   sans filtre de catégorie, ce qui rend aussi toutes les éditions comparables.

Sondage : `docs/superpowers/specs/2026-07-26-competitor-ironman-sondage.md`.
Design  : `docs/superpowers/specs/2026-07-26-competitor-ironman-design.md`.
"""
import json
import logging
import re
from datetime import date, datetime
from urllib.parse import quote, urlparse

import httpx

from app.core import http

from .base import (
    STATUS_DNF,
    STATUS_DNS,
    STATUS_DSQ,
    STATUS_FINISHER,
    ScrapedResult,
)
from .classify import classify_event_type
from .utils import anonymous_identity, normalize_rank, normalize_time, split_athlete_name

logger = logging.getLogger(__name__)

LABS_BASE = "https://labs-v2.competitor.com"
# Cible du proxy. Le `@odata.nextLink` de la source revient en
# `/web/wtc_results?`, forme que l'API rejette en 404 : le front la réécrit en
# `/web/results?` avant de la passer au proxy, on fait pareil.
API_RESULTS = "https://api.competitor.com/web/results"

# ponytail: User-Agent figé à Chrome/124.0.0.0, là où `utils.DEFAULT_HEADERS` porte
# Chrome/124.0. Écart non expliqué — probablement un copier-coller plus ancien,
# mais il tape un vrai site : à converger une fois `pytest -m integration`
# passé sur ce fournisseur, pas avant.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
    # Le proxy est une route interne de l'app Next.js : sans Referer cohérent,
    # rien ne garantit qu'il reste servi.
    "Referer": f"{LABS_BASE}/",
}

# Iframe de classement d'une page ironman.com. Les deux autres iframes de la
# page (`/results/event/odiv/…`, `/clubpoints/event/…`) ne matchent pas : le
# segment qui suit `event/` n'est alors pas un uuid.
_RE_IFRAME = re.compile(
    r"labs-v2\.competitor\.com/results/event/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})",
    re.I,
)
# URL competitor.com collée directement. `odiv/` est toléré : c'est la même série.
_RE_UUID_PATH = re.compile(
    r"/results/event/(?:odiv/)?([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})",
    re.I,
)
_RE_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)

# Sentinelles de la source, lues dans le bundle du front : le rang 99999 et le
# temps « 0:00:00 » y sont rendus « - ». Ce sont des absences, pas des valeurs.
_UNRANKED_RANK = 99999
_ABSENT_TIME = "0:00:00"

# Les cinq slots positionnels de `ScrapedResult`. Noter l'asymétrie de la source :
# T1 est `wtc_transition1timeformatted`, T2 est `wtc_transitiontime2formatted`.
_SPLIT_FIELDS = {
    "wtc_swimtimeformatted": "swim_time",
    "wtc_transition1timeformatted": "t1_time",
    "wtc_biketimeformatted": "bike_time",
    "wtc_transitiontime2formatted": "t2_time",
    "wtc_runtimeformatted": "run_time",
}

# Garde-fou de boucle : la source pagine par 2000. 50 pages = 100 000
# participants, très au-delà de la plus grosse épreuve de la marque.
_MAX_PAGES = 50


def _uuid_from_url(url: str) -> str | None:
    """UUID porté par une URL competitor.com, ou None s'il faut le résoudre."""
    match = _RE_UUID_PATH.search(urlparse(url).path)
    return match.group(1).lower() if match else None


def _resolve_uuid(client: httpx.Client, url: str) -> str:
    """UUID d'épreuve extrait de l'iframe Competitor d'une page ironman.com."""
    response = client.get(url)
    response.raise_for_status()
    match = _RE_IFRAME.search(response.text)
    if not match:
        raise ValueError(
            "Aucune iframe de résultats Competitor dans la page : "
            f"{url} — pointez la page « Results » de l'épreuve "
            "(ex. https://www.ironman.com/races/<slug>/results)."
        )
    return match.group(1).lower()


def _fetch_next_data(client: httpx.Client, uuid: str) -> dict:
    """`props.pageProps` de la page Next.js de la série."""
    response = client.get(f"{LABS_BASE}/results/event/{uuid}")
    response.raise_for_status()
    match = _RE_NEXT_DATA.search(response.text)
    if not match:
        raise ValueError(
            f"Page Competitor sans bloc __NEXT_DATA__ : {uuid} (markup modifié ?)."
        )
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Bloc __NEXT_DATA__ illisible pour l'épreuve {uuid}.") from exc
    props = (data.get("props") or {}).get("pageProps") or {}
    # Un uuid inconnu ne renvoie pas 404 : la page sort en 200 avec un pageProps
    # vide. C'est `subevents` qui fait foi.
    if not props.get("subevents"):
        raise ValueError(
            f"Épreuve Competitor introuvable : {uuid} — aucune édition publiée."
        )
    return props


def _choose_edition(props: dict, uuid: str) -> dict:
    """L'édition à importer : celle que vise l'URL, sinon la plus récente publiée."""
    editions = props.get("subevents") or []
    by_id = {
        (edition.get("wtc_eventid") or "").lower(): edition for edition in editions
    }
    requested = by_id.get(uuid)
    if requested is not None:
        return requested
    latest_id = (props.get("latestResultSubeventId") or "").lower()
    return by_id.get(latest_id) or editions[0]


def _edition_date(edition: dict) -> date | None:
    raw = (edition.get("wtc_eventdate") or "").strip()
    if raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError:
            logger.warning("Date d'édition Competitor illisible : %r", raw)
    # Repli sur la forme américaine `6/29/2025`.
    formatted = (edition.get("wtc_eventdate_formatted") or "").strip()
    try:
        return datetime.strptime(formatted, "%m/%d/%Y").date()
    except ValueError:
        return None


def _odata_url(edition_id: str) -> str:
    """Requête OData d'un classement complet, telle que la construit le front."""
    return (
        f"{API_RESULTS}?$filter=_wtc_eventid_value eq {edition_id}"
        "&$orderby=wtc_finishrankoverall"
    )


def _fetch_proxy(client: httpx.Client, odata_url: str) -> dict:
    """Une page de résultats, via le proxy de l'app (seule porte ouverte).

    Une erreur HTTP remonte volontairement : dégrader en silence figerait un
    import tronqué dans le cache 30 jours.
    """
    target = odata_url.replace("/web/wtc_results?", "/web/results?")
    response = client.get(f"{LABS_BASE}/api/results-proxy?url={quote(target, safe='')}")
    response.raise_for_status()
    return response.json()


def _rows(client: httpx.Client, edition_id: str) -> list[dict]:
    """Toutes les lignes de résultat de l'édition, pagination suivie.

    On ne réutilise **jamais** `latestResults` de la page, même pour l'édition
    courante : il est amputé de l'Open Division (cf. piège 3 en tête de module).
    """
    rows: list[dict] = []
    next_url = _odata_url(edition_id)
    pages = 0
    while next_url and pages < _MAX_PAGES:
        payload = _fetch_proxy(client, next_url)
        rows.extend(payload.get("value") or [])
        next_url = payload.get("@odata.nextLink")
        pages += 1
    if next_url:
        # Même raison que dans `_fetch_proxy` : rendre les pages déjà lues
        # figerait un classement tronqué dans le cache 30 jours. Atteindre le
        # garde-fou n'est pas une épreuve trop grosse (100 000 participants),
        # c'est un `nextLink` qui boucle — donc une panne, pas une limite.
        raise ValueError(
            f"Pagination Competitor interrompue après {_MAX_PAGES} pages pour "
            f"l'édition {edition_id} : le classement serait tronqué."
        )

    # Le front dédoublonne par `wtc_resultid` en recollant les pages ; on fait de
    # même, une ligne pouvant réapparaître si le classement bouge entre deux appels.
    seen: set[str] = set()
    unique_rows = []
    for row in rows:
        key = row.get("wtc_resultid")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        unique_rows.append(row)
    return unique_rows


def _time(value: str | None) -> str:
    text = (value or "").strip()
    if not text or text == _ABSENT_TIME:
        return ""
    return normalize_time(text)


def _rank(value) -> int | None:
    if value is None or str(value).strip() in ("", str(_UNRANKED_RANK)):
        return None
    return normalize_rank(value) or None


def _status(row: dict) -> str:
    """Statut sportif, ou "" si la source ne se prononce pas."""
    if row.get("wtc_dq"):
        return STATUS_DSQ
    if row.get("wtc_dns"):
        return STATUS_DNS
    if row.get("wtc_dnf"):
        return STATUS_DNF
    if row.get("wtc_finisher"):
        return STATUS_FINISHER
    # Mesuré : 3 lignes sur 1585 (Vichy 2024) n'ont aucun des quatre drapeaux.
    # On laisse l'infra trancher sur la présence d'un temps plutôt que de deviner.
    return ""


def _gender(agegroup: dict) -> str:
    """Genre lu sur la catégorie d'âge, **pas** sur la fiche de contact.

    `wtc_ContactId.gendercode` est faux sur 77 lignes / 1585 mesurées (Vichy
    2024) : le vainqueur masculin d'IRONMAN France y est « Female ». La
    catégorie (`M30-34`) porte l'information de façon fiable.
    """
    label = (agegroup.get("wtc_gender_formatted") or "").strip().lower()
    if label.startswith("m"):
        return "M"
    if label.startswith("f"):
        return "F"
    return ""


def _bib(row: dict) -> str:
    for field in ("wtc_bibnumber", "wtc_bibnumber_v2"):
        value = row.get(field)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _build_result(
    row: dict,
    *,
    url: str,
    event_name: str,
    event_date: date | None,
    event_type: str,
    edition_id: str,
) -> ScrapedResult:
    contact = row.get("wtc_ContactId") or {}
    agegroup = row.get("wtc_AgeGroupId") or {}

    result = ScrapedResult(source_url=url, provider="competitor")

    last_name = (contact.get("lastname") or "").strip()
    first_name = (contact.get("firstname") or "").strip()
    if not last_name and not first_name:
        # Repli : `fullname` est en « Prénom NOM », que sait découper utils.
        last_name, first_name = split_athlete_name(contact.get("fullname") or "")
    result.bib_number = _bib(row)
    # « Anonymous » sur 70 dossards distincts de la course 305 : une seule fiche (#897).
    result.athlete_name, result.athlete_firstname = anonymous_identity(
        last_name, first_name, bib=result.bib_number, scope=edition_id
    )

    # La source ne publie **aucun club** — ni colonne, ni entité liée. Un import
    # Competitor ne peut donc pas être rattaché au TCN par ce champ (cf. design).
    result.club = ""
    result.category = (
        row.get("_wtc_agegroupid_value_formatted")
        or agegroup.get("wtc_agegroupname")
        or ""
    ).strip()
    result.gender = _gender(agegroup)

    result.event_name = event_name
    result.event_date = event_date
    result.event_type = event_type

    result.status = _status(row)
    result.total_time = _time(row.get("wtc_finishtimeformatted"))
    for field, slot in _SPLIT_FIELDS.items():
        setattr(result, slot, _time(row.get(field)))

    result.rank_overall = _rank(row.get("wtc_finishrankoverall"))
    result.rank_category = _rank(row.get("wtc_finishrankgroup"))
    result.rank_gender = _rank(row.get("wtc_finishrankgender"))

    result.is_relay = bool(row.get("_wtc_teamresult_value"))
    result.raw_data = dict(row)

    # Un non-finisher garde ses splits partiels (ils sont réels) mais ne peut
    # porter ni temps final ni rang : la source y laisse 99999 et des nulls.
    if result.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
        result.total_time = ""
        result.rank_overall = None
        result.rank_category = None
        result.rank_gender = None

    return result


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Tous les participants de l'édition visée par l'URL."""
    with http.client(timeout=30, headers=HEADERS) as client:
        uuid = _uuid_from_url(url)
        if uuid is None:
            uuid = _resolve_uuid(client, url)

        props = _fetch_next_data(client, uuid)
        edition = _choose_edition(props, uuid)
        edition_id = (edition.get("wtc_eventid") or "").lower()
        if not edition_id:
            # Sans identifiant, le `$filter` OData part vide : le proxy répond
            # 400 sur une requête tronquée, illisible à froid.
            raise ValueError(
                f"Édition Competitor sans identifiant pour l'épreuve {uuid} : "
                "impossible de demander son classement."
            )

        event_name = (edition.get("wtc_name") or "").strip()
        if not event_name:
            raise ValueError(f"Édition Competitor sans nom : {edition_id}")
        event_date = _edition_date(edition)
        event_type = classify_event_type(event_name)

        rows = _rows(client, edition_id)
        if not rows:
            raise ValueError(
                f"Épreuve Competitor « {event_name} » : aucun résultat publié."
            )
        logger.info(
            "Competitor : %d résultats pour « %s » (%s)",
            len(rows),
            event_name,
            edition_id,
        )
        return [
            _build_result(
                row,
                url=url,
                event_name=event_name,
                event_date=event_date,
                event_type=event_type,
                edition_id=edition_id,
            )
            for row in rows
        ]
