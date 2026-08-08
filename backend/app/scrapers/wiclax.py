"""
Scraper for wiclax G-Live results (chronosmetron.wiclax-results.com, etc.)
URL example:
  https://chronosmetron.wiclax-results.com/G-Live/g-live.html
    ?f=../Triathlon%20de%20la%20Roche%202026/Triathlon%20de%20la%20Roche.clax&B=6159

The .clax file is an XML file containing all results.
We fetch it and find the competitor by bib number (B param).
"""
import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Callable
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from app.core import http

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, FanoutTrace, ScrapedResult
from .classify import classify_event_type
from .utils import (
    derive_status_from_label,
    normalize_rank,
    normalize_time,
    parse_fr_date,
    qualify_event_name,
    split_athlete_name,
    to_seconds,
)

logger = logging.getLogger(__name__)



HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


# Attributs candidats (forward-compat) ; le vrai signal Wiclax est le flag np.
_STATUS_ATTRS = ("Status", "status", "State", "state", "Etat", "etat", "st")


def _competitor_status(comp: ET.Element) -> str:
    """Statut explicite d'un élément (E/Competitor/R) ; "" sinon.

    Découverte (épreuve réelle) : Wiclax ne pose pas d'attribut de statut nommé
    mais un flag binaire np="1" sur le <E> pour les non-partants (→ DNS), comme
    TimePulse. Les attributs nommés restent scannés par sécurité/forward-compat.
    """
    for name in _STATUS_ATTRS:
        val = comp.get(name)
        if val:
            status = derive_status_from_label(val)
            if status:
                return status
    if (comp.get("np") or "").strip() not in ("", "0"):
        return STATUS_DNS
    return ""


def _parse_competitor(comp, url: str, event_name: str, event_type: str) -> ScrapedResult:
    """Build a ScrapedResult from a single competitor XML element.
    Handles both Wiclax Competitor/Runner format and TimePulse-style E format.
    """
    result = ScrapedResult(source_url=url, provider="wiclax", bib_number=_display_bib(comp))

    # p= (parcours) gives per-competitor discipline in ChronoSmetron format
    # e.g. "Triathlon M", "Triathlon L", "Relais S" — takes priority over root event name
    p_attr = comp.get("p") or comp.get("P") or ""
    if p_attr:
        result.is_relay = "relais" in p_attr.lower() or "relay" in p_attr.lower()
        # Chaque parcours ChronoSmetron est une épreuve distincte : classement
        # propre et dossards réutilisés d'un parcours à l'autre. On qualifie le
        # nom de course par le parcours pour éviter que plusieurs parcours de même
        # type ne fusionnent en une seule Course (issue #21 : collisions de
        # dossards → participants manquants, rangs dupliqués).
        event_name = _qualify_event_name(event_name, p_attr)
        # On classe le nom *qualifié*, pas le parcours nu : beaucoup de parcours ne
        # nomment pas le sport (« S Duo », « M Solo » chez ChronoWest) et le
        # classifieur retombe alors sur son défaut `triathlon` — un swimrun finissait
        # en triathlon-s. Le sport vient du nom d'épreuve, la taille du parcours ; un
        # parcours qui nomme explicitement une autre discipline (« Duathlon jeunes »)
        # reste prioritaire, les multisports étant testés avant le triathlon.
        event_type = classify_event_type(event_name)

    result.event_name = event_name
    result.event_type = event_type

    # Try standard Competitor/Runner attributes first
    name = comp.get("Name") or comp.get("name") or ""
    firstname = comp.get("FirstName") or comp.get("firstname") or ""
    if not name and not firstname:
        full = _get_competitor_fullname(comp)
        if full:
            surname, fname = split_athlete_name(full)
            name, firstname = surname, fname

    result.athlete_name = name
    result.athlete_firstname = firstname
    result.club = comp.get("Club") or comp.get("club") or comp.get("c") or ""
    result.category = comp.get("Category") or comp.get("category") or comp.get("ca") or ""
    result.gender = comp.get("Gender") or comp.get("gender") or comp.get("x") or ""
    # Rang général : Rank/rank en format Competitor uniquement. En ChronoSmetron
    # E/R le rang N'EST PAS stocké (l'attribut `v` est le dossard réel, pas le
    # rang) → il est calculé au tri par scrape_event_all (_compute_er_ranks).
    result.rank_overall = normalize_rank(comp.get("Rank") or comp.get("rank"))
    result.rank_category = normalize_rank(
        comp.get("CategoryRank") or comp.get("categoryrank")
    )
    result.rank_gender = normalize_rank(
        comp.get("GenderRank") or comp.get("genderrank")
    )
    result.total_time = normalize_time(comp.get("Time") or comp.get("time") or "")

    stages = comp.findall(".//SplitTime") + comp.findall(".//Stage")
    raw: dict = {}
    for s in stages:
        sname = (s.get("Name") or s.get("name") or "").lower()
        stime = normalize_time(s.get("Time") or s.get("time") or "")
        raw[f"split_{sname}"] = stime
        if "swim" in sname or "natation" in sname or "nage" in sname:
            if not result.swim_time:
                result.swim_time = stime
        elif "t1" in sname:
            if not result.t1_time:
                result.t1_time = stime
        elif "bike" in sname or "velo" in sname or "vélo" in sname or "cycle" in sname:
            if not result.bike_time:
                result.bike_time = stime
        elif "t2" in sname:
            if not result.t2_time:
                result.t2_time = stime
        elif "run" in sname or "cap" in sname or "course" in sname:
            if not result.run_time:
                result.run_time = stime

    result.status = _competitor_status(comp)
    if result.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
        result.total_time = ""
        result.rank_overall = None
        result.rank_category = None
        result.rank_gender = None

    result.raw_data = raw
    return result


def _qualify_event_name(event_name: str, parcours: str) -> str:
    """Qualifie le nom d'épreuve par le parcours ChronoSmetron.

    Logique factorisée dans `utils.qualify_event_name`, partagée avec RaceResult
    (qui qualifie par contest). Alias conservé : il est importé par les tests.
    """
    return qualify_event_name(event_name, parcours)


# Sauts max dans la chaîne « page épreuve → coquille → iframe G-Live ».
# Garde anti-boucle : une page qui se pointe elle-même s'arrête sur ValueError.
_MAX_RESOLVE_HOPS = 3
_HOST_RESULTATS = "wiclax-results.com"


def _find_glive_url(html: str, page_url: str) -> str | None:
    """URL absolue du moteur G-Live référencé par une <iframe> de la page.

    BeautifulSoup et non une regex : le `src` contient des apostrophes dès que le
    nom d'épreuve en a une (« LOC'orrida 2026.clax »), ce qui tronquait la capture
    d'une classe `[^"']*` et produisait un 404 (issue #35). Le parseur décode aussi
    les entités HTML. Le `src` est résolu contre l'URL de la page : correct pour un
    src absolu (ChronoWest) comme racine-relatif (ChronoSmetron).
    """
    soup = BeautifulSoup(html, "lxml")
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src") or ""
        if "g-live.html" in src.lower():
            return urljoin(page_url, src)
    return None


def _find_wiclax_link(html: str, page_url: str) -> str | None:
    """Lien sortant menant à une page de résultats Wiclax, ou None.

    Deux formes, unifiées ici :
      - un lien vers `*.wiclax-results.com` (page événement ChronoSmetron) ;
      - un lien vers la coquille `/resultats/<slug>/` du même host (page épreuve
        WordPress d'un déploiement type ChronoWest). Le lien de nav
        `/resultats-des-courses-et-classement/` ne matche pas : on exige le
        segment `resultats` exact suivi d'un unique slug.
    """
    soup = BeautifulSoup(html, "lxml")
    host = urlparse(page_url).netloc.lower()
    for a in soup.find_all("a", href=True):
        cible = urljoin(page_url, a["href"])
        parsed = urlparse(cible)
        cible_host = parsed.netloc.lower()
        # Domaine exact ou vrai sous-domaine : un suffixe brut suivrait aussi un
        # host sosie du type `evilwiclax-results.com`.
        if cible_host == _HOST_RESULTATS or cible_host.endswith(f".{_HOST_RESULTATS}"):
            # Les espaces du nom d'épreuve vivent tels quels dans le href.
            chemin = quote(parsed.path, safe="/%+").rstrip("/") + "/"
            return parsed._replace(path=chemin).geturl()
        if parsed.netloc.lower() == host and re.fullmatch(
            r"/resultats/[^/]+/?", parsed.path
        ):
            return cible
    return None


def _resolve_to_wiclax_url(url: str, client: httpx.Client, _hops: int = 0) -> str:
    """Remonte de n'importe quelle page Wiclax jusqu'à l'URL du `g-live.html`.

    Chaîne : page épreuve WordPress → coquille `/resultats/<slug>/` → iframe
    G-Live. Une page portant directement l'iframe court-circuite les sauts.
    """
    if _hops >= _MAX_RESOLVE_HOPS:
        raise ValueError(
            f"Trop de sauts en cherchant le moteur G-Live depuis : {url}"
        )

    resp = client.get(url, headers=HEADERS)
    resp.raise_for_status()

    glive_url = _find_glive_url(resp.text, url)
    if glive_url:
        return glive_url

    lien = _find_wiclax_link(resp.text, url)
    if lien:
        return _resolve_to_wiclax_url(lien, client, _hops + 1)

    raise ValueError(f"Impossible de trouver le lien G-Live dans la page Wiclax : {url}")


def _clax_event_date(event_elem: ET.Element):
    """Date de l'épreuve d'un `.clax`, `None` si le fichier n'en porte aucune.

    Trois attributs coexistent selon l'âge du fichier :
      - `dt1` : date ISO — absente des fichiers anciens ;
      - `dates` : libellé français (« dimanche 1 juin 2025 ») — le repli ;
      - `date` : numéro de série du logiciel. **Volontairement ignoré** : il vaut
        la date saisie à la création du fichier, parfois fausse (Couëron :
        sérial au 2024-10-01, épreuve courue le 2024-10-06). Pas de date vaut
        mieux qu'une date inventée.
    """
    from datetime import date as date_t

    iso = event_elem.get("dt1", "") or event_elem.get("Dt1", "")
    if iso:
        try:
            return date_t.fromisoformat(iso[:10])
        except ValueError:
            pass
    return parse_fr_date(event_elem.get("dates", "") or event_elem.get("Dates", ""))


def _clax_url(glive_url: str) -> str:
    """URL absolue du `.clax` depuis une URL de moteur `g-live.html?f=…`.

    Le `f=` est résolu contre l'URL réelle du `g-live.html` — et non contre un
    `/G-Live/` codé en dur. Ça couvre les deux familles connues : moteur sous
    `/G-Live/` avec un `f=` relatif (ChronoSmetron), et moteur sous
    `/wp-content/glive/` avec un `f=` racine-absolu (ChronoWest).
    """
    f_param = parse_qs(urlparse(glive_url).query).get("f", [""])[0]
    if not f_param:
        raise ValueError(f"Paramètre f= absent de l'URL G-Live : {glive_url}")
    return urljoin(glive_url, f_param)


def _fetch_clax(url: str) -> tuple[ET.Element, str, str, str, object]:
    """
    Fetch and parse a .clax XML file from a Wiclax G-Live URL.
    Directory URLs (no f= param) are resolved via iframe extraction first.
    Returns (root, clax_url, event_name, event_type, event_date).
    """
    with http.client(timeout=30) as client:
        # Toute URL qui ne porte pas déjà le `f=` du moteur (page épreuve, coquille
        # WordPress, annuaire ChronoSmetron) est remontée jusqu'au `g-live.html`.
        if not parse_qs(urlparse(url).query).get("f"):
            url = _resolve_to_wiclax_url(url, client)

        clax_url = _clax_url(url)
        f_param = parse_qs(urlparse(url).query).get("f", [""])[0]

        resp = client.get(clax_url, headers=HEADERS)
        resp.raise_for_status()
        xml_content = resp.text

    root = ET.fromstring(xml_content)
    event_elem = root.find(".//Event") or root.find(".//RACE") or root
    event_name = (
        event_elem.get("Name", "")
        or event_elem.get("name", "")
        or unquote(f_param).split("/")[-1].replace(".clax", "")
    )
    event_type = classify_event_type(event_name)

    return root, clax_url, event_name, event_type, _clax_event_date(event_elem)


def _get_competitor_fullname(comp) -> str:
    """Extract full name from a competitor element (handles both XML formats)."""
    # Format 1: Competitor/Runner with Name + FirstName attributes
    name = comp.get("Name") or comp.get("name") or ""
    firstname = comp.get("FirstName") or comp.get("firstname") or ""
    if name or firstname:
        return re.sub(r"\s+", " ", f"{firstname} {name}").strip()
    # Format 2: TimePulse/Wiclax E element with n="Firstname\xa0SURNAME"
    n = comp.get("n") or comp.get("N") or ""
    return re.sub(r"[\s\xa0]+", " ", n).strip()


def _get_competitor_bib(comp) -> str:
    """Clé de jointure E↔R (et bib en format Competitor).

    En ChronoSmetron, `d` est l'identifiant interne (numéroté par vague, ex.
    5176) qui relie le <E> à son <R> — c'est la clé de jointure, PAS le dossard
    affiché (cf. _display_bib)."""
    return (comp.get("Bib") or comp.get("bib") or
            comp.get("d") or comp.get("D") or "")


def _display_bib(comp) -> str:
    """Dossard affiché à l'athlète.

    Format Competitor : attribut Bib. Format ChronoSmetron E/R : l'attribut `v`
    porte le *dossard réel* (« NumVoitureOuDosRéel », ex. 176) ; `d` n'est qu'un
    id interne préfixé par vague (ex. 5176). On préfère donc `v`, repli sur `d`.
    """
    return (comp.get("Bib") or comp.get("bib") or
            comp.get("v") or comp.get("V") or
            comp.get("d") or comp.get("D") or "")


def _compute_er_ranks(
    root: ET.Element, r_by_bib: dict[str, ET.Element]
) -> dict[str, tuple[int, int, int]]:
    """Rangs (général, sexe, catégorie) des finishers, calculés au tri par temps.

    ChronoSmetron ne stocke pas le classement dans le .clax : la page live le
    calcule en triant les finishers par temps total, au sein de chaque parcours
    (`p`). On reproduit ce tri. Le dict renvoyé est indexé par la clé de jointure
    `d` ; les non-finishers et temps absents sont exclus du classement.
    """
    from collections import defaultdict

    by_parcours: dict[str, list[tuple[int, str, str, str]]] = defaultdict(list)
    for comp in root.iter("E"):
        d = comp.get("d") or comp.get("D")
        if not d:
            continue
        result_elem = r_by_bib.get(d)
        if result_elem is None:
            continue
        raw_t = result_elem.get("t", "")
        status = (_competitor_status(comp) or _competitor_status(result_elem)
                  or derive_status_from_label(raw_t))
        if status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
            continue
        secs = to_seconds(normalize_time(raw_t))
        if not secs:
            continue
        parcours = comp.get("p") or comp.get("P") or ""
        by_parcours[parcours].append((secs, d, comp.get("x") or "", comp.get("ca") or ""))

    ranks: dict[str, tuple[int, int, int]] = {}
    for entries in by_parcours.values():
        entries.sort(key=lambda e: e[0])
        overall = 0
        gender_pos: dict[str, int] = defaultdict(int)
        cat_pos: dict[tuple[str, str], int] = defaultdict(int)
        for _secs, d, gender, cat in entries:
            overall += 1
            gender_pos[gender] += 1
            # Catégorie = même sexe + même catégorie (les catégories sont
            # genrées en triathlon FR : S2H/S2F distincts).
            cat_pos[(gender, cat)] += 1
            ranks[d] = (overall, gender_pos[gender], cat_pos[(gender, cat)])
    return ranks


# Codes `disc` Wiclax → discipline (trans="1"/disc="-1" = transition, traité à part).
_DISC_KIND = {"5": "swim", "0": "bike", "6": "run"}


def _segment_kind(s: ET.Element) -> str:
    if s.get("trans") == "1" or s.get("disc") == "-1":
        return "transition"
    return _DISC_KIND.get(s.get("disc") or "", "other")


def _segment_chain(segments: list[ET.Element], parcours: str) -> list[tuple[int, str]]:
    """Splits « totaux » d'un parcours, ordonnés du départ à l'arrivée.

    Le `.clax` partage UN bloc <Segments> entre tous les parcours, chaque <S>
    étant scopé par l'attribut `pcs`. On filtre les segments du parcours, puis on
    voit chaque <S> comme une arête `ptg1→ptg2` et on prend le chemin du
    checkpoint de départ (`-999`) à l'arrivée (`999`) comptant le MOINS d'arêtes :
    il retient les segments totaux et écarte les tours/laps (qui subdivisent un
    total en plusieurs arêtes). Renvoie une liste de (index sN, nature) où
    nature ∈ {swim, bike, run, transition, other}.
    """
    from collections import defaultdict, deque

    adj: dict[str, list[tuple[str, int, ET.Element]]] = defaultdict(list)
    for idx, s in enumerate(segments):
        pcs = s.get("pcs") or ""
        names = {n.strip() for n in pcs.split(",") if n.strip()}
        # pcs vide → segment commun à tous les parcours (pas de filtrage).
        if names and parcours and parcours not in names:
            continue
        adj[s.get("ptg1")].append((s.get("ptg2"), idx, s))

    start, finish = "-999", "999"
    queue: deque[tuple[str, list[tuple[int, str]]]] = deque([(start, [])])
    visited = {start}
    while queue:
        node, path = queue.popleft()
        if node == finish:
            return path
        for nxt, idx, s in adj.get(node, []):
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, path + [(idx, _segment_kind(s))]))
    return []


def _parcours_split_map(
    segments: list[ET.Element], parcours: str
) -> tuple[dict[str, int], str | None]:
    """(mapping {slot ScrapedResult → index sN}, surcharge event_type | None).

    La discipline est déduite de la séquence des segments du parcours :
      - natation/vélo/CaP (+ T1/T2) → triathlon : slots swim/t1/bike/t2/run,
        pas de surcharge (on conserve l'event_type détecté depuis `p`).
      - CaP/vélo/CaP — course jeune run-bike-run, sans natation : 1re course à
        pied → slot swim, 2e course à pied → slot run, surcharge
        event_type="duathlon" pour que build_splits étiquette course1/bike/course2.
      - tout autre motif → rattachement par nature (best effort), sans surcharge.
    """
    chain = _segment_chain(segments, parcours)
    if not chain:
        return {}, None

    discs = [kind for _idx, kind in chain if kind != "transition"]
    trans = [idx for idx, kind in chain if kind == "transition"]

    def _with_transitions(split_map: dict[str, int]) -> dict[str, int]:
        if len(trans) >= 1:
            split_map["t1"] = trans[0]
        if len(trans) >= 2:
            split_map["t2"] = trans[1]
        return split_map

    # Course jeune run-bike-run : pas de natation, deux courses à pied autour du vélo.
    if discs == ["run", "bike", "run"]:
        runs = [idx for idx, kind in chain if kind == "run"]
        bike = next(idx for idx, kind in chain if kind == "bike")
        return _with_transitions({"swim": runs[0], "bike": bike, "run": runs[1]}), "duathlon"

    # Triathlon (et défaut) : un slot par nature, premier segment rencontré.
    split_map: dict[str, int] = {}
    for idx, kind in chain:
        if kind in ("swim", "bike", "run") and kind not in split_map:
            split_map[kind] = idx
    return _with_transitions(split_map), None


def _fill_er_splits(
    result_elem: ET.Element,
    r: ScrapedResult,
    split_idx: dict[str, int],
) -> None:
    """Fill split times on r from a ChronoSmetron R element using split_idx."""
    def get(key: str) -> str:
        n = split_idx.get(key)
        return normalize_time(result_elem.get(f"s{n}", "")) if n is not None else ""

    if split_idx:
        r.swim_time = get("swim")
        r.t1_time   = get("t1")
        r.bike_time = get("bike")
        r.t2_time   = get("t2")
        r.run_time  = get("run")
    else:
        # Fallback when no <Segments> definition found (older events)
        r.swim_time = normalize_time(result_elem.get("s2", ""))
        r.t1_time   = normalize_time(result_elem.get("s3", ""))
        r.bike_time = normalize_time(result_elem.get("s4", ""))
        r.t2_time   = normalize_time(result_elem.get("s5", ""))
        r.run_time  = normalize_time(result_elem.get("s10", ""))


def _parcours_slug(parcours: str) -> str:
    """Slug canonique d'un parcours Wiclax (fan-out #195).

    Contraintes : stable (mémoïsable), ASCII, URL-safe, distinct pour deux
    parcours distincts. Un parcours vide (rare — `.clax` très anciens) rend
    la chaîne vide, à traiter en amont.
    """
    # NFKD + drop combining marks : « S-Open Femmes » → « S-Open Femmes »,
    # « 6-9 Ans » → « 6-9-ans » (compatible avec ASCII de sortie).
    normalized = unicodedata.normalize("NFKD", parcours or "")
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))
    # Tout ce qui n'est pas [a-z0-9-] → tiret. Lower ensuite. On collapse les tirets.
    lowered = stripped.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug


def _sub_source_url(url: str, parcours: str) -> str:
    """URL canonique d'un parcours Wiclax — clé de cache TTL et de dédup source_url.

    Convention : URL débarrassée de `B=` (dossard sélecteur), avec un paramètre
    neuf `parcours=<slug>` ajouté. `p=` n'est PAS employé : la source Wiclax
    l'utilise déjà en query sur certains flux, on ne veut pas rentrer en collision.
    Un parcours vide → URL sans qualification (compat rétro `.clax` monoparcours).
    """
    parsed = urlparse(_strip_athlete_param(url))
    params = [(k, v) for k, v in parse_qs(parsed.query, keep_blank_values=True).items()]
    # parse_qs rend {clé: [valeurs]} → aplatir en liste de paires pour préserver
    # l'unicité (pas de reconstruction de liste sur des paramètres non répétés).
    flat: list[tuple[str, str]] = []
    for key, values in params:
        for value in values:
            flat.append((key, value))
    slug = _parcours_slug(parcours)
    if slug:
        # Écrase toute valeur `parcours=` préexistante — l'URL entrante ne doit pas
        # trancher à la place du fan-out.
        flat = [(k, v) for k, v in flat if k != "parcours"]
        flat.append(("parcours", slug))
    return urlunparse(parsed._replace(query=urlencode(flat)))


def _drop_orphelins(
    par_parcours: dict[str, list[ScrapedResult]], ordre: list[str], url: str,
) -> None:
    """Écarte les résultats sans attribut `p=` d'un événement multi-parcours.

    Un E sans `p=` (« DOSSARD INCONNU ***** ») créait une `Course` avec
    `source_url` = URL de l'événement, qui matchait au ré-import via
    `_cached_result` et court-circuitait tout le fan-out (issue #195 sur
    Vertou 2026 ; symptôme aussi documenté par le bug #79). L'écart n'a lieu
    que sur un événement multi-parcours : un `.clax` mono-parcours où aucun E
    ne porte `p=` (legacy) reste importé entier (rétro-compat).

    Journalisation en WARNING : le cas reste rare et l'exploitant doit pouvoir
    remonter les orphelins à la source.
    """
    if len(par_parcours) <= 1 or "" not in par_parcours:
        return
    orphelins = par_parcours.pop("")
    ordre.remove("")
    logger.warning(
        "Wiclax %s : %d participant(s) orphelin(s) sans parcours écartés",
        url, len(orphelins),
    )


def _iter_parcours_results(
    root: ET.Element, base_url: str, event_name: str, event_type: str,
    event_date: object, segments: list[ET.Element],
) -> tuple[dict[str, list[ScrapedResult]], list[str]]:
    """Construit les `ScrapedResult` groupés par parcours.

    Retour : `(par_parcours, ordre)` où `par_parcours[parcours]` liste les
    résultats du parcours et `ordre` préserve l'ordre d'apparition des parcours
    dans le `.clax` — critique pour reproduire fidèlement le rendu source dans
    le fan-out (index de progression, ordre des `Course` remontées).
    """
    par_parcours: dict[str, list[ScrapedResult]] = {}
    ordre: list[str] = []

    def _ajouter(parcours: str, r: ScrapedResult) -> None:
        if parcours not in par_parcours:
            par_parcours[parcours] = []
            ordre.append(parcours)
        par_parcours[parcours].append(r)

    # Format 1: Competitor / Runner / Participant elements
    for tag in ("Competitor", "COMPETITOR", "Runner", "RUNNER", "Participant"):
        found = list(root.iter(tag))
        if found:
            for comp in found:
                bib = comp.get("Bib") or comp.get("bib") or ""
                if not bib:
                    continue
                r = _parse_competitor(comp, base_url, event_name, event_type)
                r.event_date = event_date
                parcours = comp.get("p") or comp.get("P") or ""
                _ajouter(parcours, r)
            return par_parcours, ordre

    # Format 2: ChronoSmetron E/R elements (E = competitor, R = timing keyed by d=bib)
    split_cache: dict[str, tuple[dict[str, int], str | None]] = {}
    r_by_bib: dict[str, ET.Element] = {
        elem.get("d", ""): elem
        for elem in root.iter("R")
        if elem.get("d")
    }
    ranks_by_d = _compute_er_ranks(root, r_by_bib)
    for comp in root.iter("E"):
        join_key = _get_competitor_bib(comp)
        if not join_key:
            continue
        r = _parse_competitor(comp, base_url, event_name, event_type)
        parcours = comp.get("p") or comp.get("P") or ""
        if parcours not in split_cache:
            split_cache[parcours] = _parcours_split_map(segments, parcours)
        split_map, event_type_override = split_cache[parcours]
        if event_type_override:
            r.event_type = event_type_override
        result_elem = r_by_bib.get(join_key)
        if result_elem is not None:
            raw_t = result_elem.get("t", "")
            if not r.status:
                r.status = _competitor_status(result_elem) or derive_status_from_label(raw_t)
            if r.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
                r.total_time = ""
            elif not r.total_time:
                r.total_time = normalize_time(raw_t)
                _fill_er_splits(result_elem, r, split_map)
        if r.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
            r.rank_overall = r.rank_category = r.rank_gender = None
        else:
            rg = ranks_by_d.get(join_key)
            if rg is not None:
                r.rank_overall, r.rank_gender, r.rank_category = rg
        r.event_date = event_date
        _ajouter(parcours, r)

    return par_parcours, ordre


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """
    Fetch ALL participants from a Wiclax .clax event file.

    Contrat historique conservé (utilisé par les tests unitaires et
    l'échappatoire du `Provider`) : une seule requête sur le `.clax`, tous les
    parcours confondus, aucun découpage `Course.source_url` par parcours.

    Le chemin nominal passe désormais par `scrape_event_fanout` (voir #195).
    """
    root, _, event_name, event_type, event_date = _fetch_clax(url)
    segs_elem = root.find(".//Segments")
    segments = list(segs_elem) if segs_elem is not None else []
    base_url = _strip_athlete_param(url)
    par_parcours, ordre = _iter_parcours_results(
        root, base_url, event_name, event_type, event_date, segments,
    )
    results: list[ScrapedResult] = []
    for parcours in ordre:
        results.extend(par_parcours[parcours])
    return results


def scrape_event_fanout(
    url: str,
    *, cache_probe: Callable[[str], bool] | None = None,
    on_heat_start: Callable[[str, str, int, int], None] | None = None,
) -> tuple[list[ScrapedResult], FanoutTrace]:
    """Fan-out par parcours d'un événement Wiclax (issue #195).

    Le `.clax` XML est **partagé** par tous les parcours de l'événement — une
    seule requête réseau suffit. Le fan-out logique est en aval du fetch, il
    n'économise donc aucun trafic : le gain est l'**intégrité du cache TTL au
    niveau parcours**. Un parcours frais côté cache TTL n'est ni reconstruit ni
    persisté (sa `Course` en base garde son `scraped_at`, son `source_url` et
    ses participations inchangés) ; un parcours disparu d'un ré-import n'est pas
    silencieusement retiré (aucune reconstruction implicite).

    URL canonique d'un parcours : `<url sans B=>&parcours=<slug>`. Le paramètre
    `parcours=` est neuf : Wiclax emploie déjà `p=` en query sur certains flux,
    on n'y rentre pas en collision. `_sub_source_url` est la SEULE définition
    de cette URL — elle sert simultanément de clé au `cache_probe` et de
    `ScrapedResult.source_url` de tous les résultats du parcours (persistée en
    `Course.source_url`).

    `on_heat_start(slug, label, index, total)` est notifié **avant** le
    traitement d'un parcours non caché — jamais pour un parcours sauté
    (cache_probe → True). `total` = nombre de parcours à traiter, pas nombre
    énuméré, sinon la progression sauterait des indices sur un ré-import
    majoritairement caché.

    Retour : `(results, trace)`. `trace.heats_imported` reste à 0 ici — dérivé
    par `import_service` via l'invariant.
    """
    trace = FanoutTrace()
    all_results: list[ScrapedResult] = []

    root, _, event_name, event_type, event_date = _fetch_clax(url)
    segs_elem = root.find(".//Segments")
    segments = list(segs_elem) if segs_elem is not None else []
    base_url = _strip_athlete_param(url)

    par_parcours, ordre = _iter_parcours_results(
        root, base_url, event_name, event_type, event_date, segments,
    )
    _drop_orphelins(par_parcours, ordre, url)
    trace.heats_enumerated = len(ordre)

    # Pré-filtre les parcours à traiter — `heats_a_scraper` fixe le total notifié
    # à `on_heat_start`, sans quoi la progression sauterait des indices.
    heats_a_scraper: list[tuple[str, str]] = []
    for parcours in ordre:
        sub_url = _sub_source_url(url, parcours)
        if cache_probe is not None and cache_probe(sub_url):
            trace.heats_cached += 1
            trace.cached_urls.append(sub_url)
            continue
        heats_a_scraper.append((parcours, sub_url))

    total_a_scraper = len(heats_a_scraper)
    for index, (parcours, sub_url) in enumerate(heats_a_scraper, start=1):
        slug = _parcours_slug(parcours)
        label = parcours or slug
        if on_heat_start is not None:
            on_heat_start(slug, label, index, total_a_scraper)
        try:
            all_results.extend(_finalize_parcours(par_parcours, parcours, sub_url))
        except Exception as exc:
            logger.warning(
                "Parcours %s de %s en échec : %s", parcours or "(sans nom)", url, exc,
            )
            trace.failures.append({"heat_slug": slug, "reason": str(exc)})

    return all_results, trace


def _finalize_parcours(
    par_parcours: dict[str, list[ScrapedResult]], parcours: str, sub_url: str,
) -> list[ScrapedResult]:
    """Finalise les résultats d'un parcours pour le fan-out.

    Fixe leur `source_url` à l'URL canonique du parcours — c'est la clé du
    cache TTL, elle doit se retrouver en `Course.source_url` pour que le
    prochain `cache_probe` la reconnaisse.

    Isolé en helper pour rendre les échecs par parcours testables sans
    fabriquer un `.clax` corrompu (les tests monkeypatchent ce helper).
    """
    resultats = par_parcours[parcours]
    for r in resultats:
        r.source_url = sub_url
    return resultats


def _strip_athlete_param(url: str) -> str:
    """Remove the B= (athlete selector) parameter from a Wiclax G-Live URL."""
    parsed = urlparse(url)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items() if k.upper() != "B"}
    return urlunparse(parsed._replace(query=urlencode(params)))


