"""
Competitor / WTC — moteur des résultats IRONMAN et IRONMAN 70.3 (issue #54).

`ironman.com` n'affiche aucun résultat en propre : sa page « Results » encastre
une iframe `labs-v2.competitor.com`, application Next.js (Pages Router) dont les
données sont embarquées dans `__NEXT_DATA__`. Le provider est donc nommé
`competitor` — c'est le moteur réel, commun à toutes les épreuves de la marque.

Flux d'appels :

    scrape_event_all(url)
      ├─ _uuid_depuis_url(url)              → uuid porté par une URL competitor.com
      ├─ _resoudre_uuid(client, url)        → sinon, GET ironman.com + iframe
      ├─ _fetch_next_data(client, uuid)     → GET labs-v2 → pageProps
      ├─ _choisir_edition(props, uuid)      → l'édition (année) à importer
      └─ _lignes(client, edition_id)        → proxy OData, pagination suivie

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
from .utils import normalize_rank, normalize_time, split_athlete_name

logger = logging.getLogger(__name__)

LABS_BASE = "https://labs-v2.competitor.com"
# Cible du proxy. Le `@odata.nextLink` de la source revient en
# `/web/wtc_results?`, forme que l'API rejette en 404 : le front la réécrit en
# `/web/results?` avant de la passer au proxy, on fait pareil.
API_RESULTS = "https://api.competitor.com/web/results"

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
_RANG_NON_CLASSE = 99999
_TEMPS_ABSENT = "0:00:00"

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


def _uuid_depuis_url(url: str) -> str | None:
    """UUID porté par une URL competitor.com, ou None s'il faut le résoudre."""
    match = _RE_UUID_PATH.search(urlparse(url).path)
    return match.group(1).lower() if match else None


def _resoudre_uuid(client: httpx.Client, url: str) -> str:
    """UUID d'épreuve extrait de l'iframe Competitor d'une page ironman.com."""
    reponse = client.get(url)
    reponse.raise_for_status()
    match = _RE_IFRAME.search(reponse.text)
    if not match:
        raise ValueError(
            "Aucune iframe de résultats Competitor dans la page : "
            f"{url} — pointez la page « Results » de l'épreuve "
            "(ex. https://www.ironman.com/races/<slug>/results)."
        )
    return match.group(1).lower()


def _fetch_next_data(client: httpx.Client, uuid: str) -> dict:
    """`props.pageProps` de la page Next.js de la série."""
    reponse = client.get(f"{LABS_BASE}/results/event/{uuid}")
    reponse.raise_for_status()
    match = _RE_NEXT_DATA.search(reponse.text)
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


def _choisir_edition(props: dict, uuid: str) -> dict:
    """L'édition à importer : celle que vise l'URL, sinon la plus récente publiée."""
    editions = props.get("subevents") or []
    par_id = {
        (edition.get("wtc_eventid") or "").lower(): edition for edition in editions
    }
    ciblee = par_id.get(uuid)
    if ciblee is not None:
        return ciblee
    derniere = (props.get("latestResultSubeventId") or "").lower()
    return par_id.get(derniere) or editions[0]


def _date_edition(edition: dict) -> date | None:
    brut = (edition.get("wtc_eventdate") or "").strip()
    if brut:
        try:
            return datetime.fromisoformat(brut.replace("Z", "+00:00")).date()
        except ValueError:
            logger.warning("Date d'édition Competitor illisible : %r", brut)
    # Repli sur la forme américaine `6/29/2025`.
    formate = (edition.get("wtc_eventdate_formatted") or "").strip()
    try:
        return datetime.strptime(formate, "%m/%d/%Y").date()
    except ValueError:
        return None


def _url_odata(edition_id: str) -> str:
    """Requête OData d'un classement complet, telle que la construit le front."""
    return (
        f"{API_RESULTS}?$filter=_wtc_eventid_value eq {edition_id}"
        "&$orderby=wtc_finishrankoverall"
    )


def _fetch_proxy(client: httpx.Client, url_odata: str) -> dict:
    """Une page de résultats, via le proxy de l'app (seule porte ouverte).

    Une erreur HTTP remonte volontairement : dégrader en silence figerait un
    import tronqué dans le cache 30 jours.
    """
    cible = url_odata.replace("/web/wtc_results?", "/web/results?")
    reponse = client.get(f"{LABS_BASE}/api/results-proxy?url={quote(cible, safe='')}")
    reponse.raise_for_status()
    return reponse.json()


def _lignes(client: httpx.Client, edition_id: str) -> list[dict]:
    """Toutes les lignes de résultat de l'édition, pagination suivie.

    On ne réutilise **jamais** `latestResults` de la page, même pour l'édition
    courante : il est amputé de l'Open Division (cf. piège 3 en tête de module).
    """
    lignes: list[dict] = []
    suivante = _url_odata(edition_id)
    pages = 0
    while suivante and pages < _MAX_PAGES:
        payload = _fetch_proxy(client, suivante)
        lignes.extend(payload.get("value") or [])
        suivante = payload.get("@odata.nextLink")
        pages += 1
    if suivante:
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
    vues: set[str] = set()
    uniques = []
    for ligne in lignes:
        cle = ligne.get("wtc_resultid")
        if cle and cle in vues:
            continue
        if cle:
            vues.add(cle)
        uniques.append(ligne)
    return uniques


def _temps(valeur: str | None) -> str:
    texte = (valeur or "").strip()
    if not texte or texte == _TEMPS_ABSENT:
        return ""
    return normalize_time(texte)


def _rang(valeur) -> int | None:
    if valeur is None or str(valeur).strip() in ("", str(_RANG_NON_CLASSE)):
        return None
    return normalize_rank(valeur) or None


def _statut(ligne: dict) -> str:
    """Statut sportif, ou "" si la source ne se prononce pas."""
    if ligne.get("wtc_dq"):
        return STATUS_DSQ
    if ligne.get("wtc_dns"):
        return STATUS_DNS
    if ligne.get("wtc_dnf"):
        return STATUS_DNF
    if ligne.get("wtc_finisher"):
        return STATUS_FINISHER
    # Mesuré : 3 lignes sur 1585 (Vichy 2024) n'ont aucun des quatre drapeaux.
    # On laisse l'infra trancher sur la présence d'un temps plutôt que de deviner.
    return ""


def _genre(agegroup: dict) -> str:
    """Genre lu sur la catégorie d'âge, **pas** sur la fiche de contact.

    `wtc_ContactId.gendercode` est faux sur 77 lignes / 1585 mesurées (Vichy
    2024) : le vainqueur masculin d'IRONMAN France y est « Female ». La
    catégorie (`M30-34`) porte l'information de façon fiable.
    """
    libelle = (agegroup.get("wtc_gender_formatted") or "").strip().lower()
    if libelle.startswith("m"):
        return "M"
    if libelle.startswith("f"):
        return "F"
    return ""


def _dossard(ligne: dict) -> str:
    for champ in ("wtc_bibnumber", "wtc_bibnumber_v2"):
        valeur = ligne.get(champ)
        if valeur not in (None, ""):
            return str(valeur).strip()
    return ""


def _build_result(
    ligne: dict,
    *,
    url: str,
    event_name: str,
    event_date: date | None,
    event_type: str,
) -> ScrapedResult:
    contact = ligne.get("wtc_ContactId") or {}
    agegroup = ligne.get("wtc_AgeGroupId") or {}

    resultat = ScrapedResult(source_url=url, provider="competitor")

    nom = (contact.get("lastname") or "").strip()
    prenom = (contact.get("firstname") or "").strip()
    if not nom and not prenom:
        # Repli : `fullname` est en « Prénom NOM », que sait découper utils.
        nom, prenom = split_athlete_name(contact.get("fullname") or "")
    resultat.athlete_name = nom
    resultat.athlete_firstname = prenom

    # La source ne publie **aucun club** — ni colonne, ni entité liée. Un import
    # Competitor ne peut donc pas être rattaché au TCN par ce champ (cf. design).
    resultat.club = ""
    resultat.category = (
        ligne.get("_wtc_agegroupid_value_formatted")
        or agegroup.get("wtc_agegroupname")
        or ""
    ).strip()
    resultat.gender = _genre(agegroup)
    resultat.bib_number = _dossard(ligne)

    resultat.event_name = event_name
    resultat.event_date = event_date
    resultat.event_type = event_type

    resultat.status = _statut(ligne)
    resultat.total_time = _temps(ligne.get("wtc_finishtimeformatted"))
    for champ, slot in _SPLIT_FIELDS.items():
        setattr(resultat, slot, _temps(ligne.get(champ)))

    resultat.rank_overall = _rang(ligne.get("wtc_finishrankoverall"))
    resultat.rank_category = _rang(ligne.get("wtc_finishrankgroup"))
    resultat.rank_gender = _rang(ligne.get("wtc_finishrankgender"))

    resultat.is_relay = bool(ligne.get("_wtc_teamresult_value"))
    resultat.raw_data = dict(ligne)

    # Un non-finisher garde ses splits partiels (ils sont réels) mais ne peut
    # porter ni temps final ni rang : la source y laisse 99999 et des nulls.
    if resultat.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
        resultat.total_time = ""
        resultat.rank_overall = None
        resultat.rank_category = None
        resultat.rank_gender = None

    return resultat


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Tous les participants de l'édition visée par l'URL."""
    with http.client(timeout=30, headers=HEADERS) as client:
        uuid = _uuid_depuis_url(url)
        if uuid is None:
            uuid = _resoudre_uuid(client, url)

        props = _fetch_next_data(client, uuid)
        edition = _choisir_edition(props, uuid)
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
        event_date = _date_edition(edition)
        event_type = classify_event_type(event_name)

        lignes = _lignes(client, edition_id)
        if not lignes:
            raise ValueError(
                f"Épreuve Competitor « {event_name} » : aucun résultat publié."
            )
        logger.info(
            "Competitor : %d résultats pour « %s » (%s)",
            len(lignes),
            event_name,
            edition_id,
        )
        return [
            _build_result(
                ligne,
                url=url,
                event_name=event_name,
                event_date=event_date,
                event_type=event_type,
            )
            for ligne in lignes
        ]
