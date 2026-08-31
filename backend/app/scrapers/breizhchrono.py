"""
Scraper for resultats.breizhchrono.com

Breizh Chrono uses the same underlying platform as Klikego (/v8/evenement/ API,
identical HTML structure). Only the front-end URL format differs:

  Klikego:       https://www.klikego.com/resultats/{slug}/{event-id}
                   ?heat={heat}&search={name}
  Breizh Chrono: https://resultats.breizhchrono.com/resultats-courses/{slug}-{event-id}/{heat}
                   ?search={name}

live.breizhchrono.com sert la MÊME plateforme Klikego (course-result.jsp, bloc
base64+XOR), seule change la façade : les heats se découvrent via
`/external/live5/classements.jsp?reference=...` et la `reference` de l'URL est
directement la clé `ref` de course-result.jsp. Le nom d'épreuve et la date de
chaque heat, eux, ne vivent que sur `/external/live5/index.jsp?reference=...`.
Voir `scrape_live_event_all`.

Une Course du modèle = un heat : son nom porte donc le libellé du heat
(`klikego_platform.course_name`, partagée avec Klikego — #308), faute de quoi
les heats d'une même épreuve fusionnent sur l'identité (nom, date, type, relais).

The detail page HTML (p.text-sm meta line, ranking divs, result-row splits table)
is byte-for-byte identical, so _parse_detail is shared from klikego.
"""
import logging
import re
from collections.abc import Callable
from datetime import date
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core import http
from app.core.exceptions import DomainError

from .base import FanoutTrace, ScrapedResult
from .classify import classify_event_type
from .klikego_platform import course_name, heat_is_relay
from .utils import DEFAULT_HEADERS

logger = logging.getLogger(__name__)

BASE = "https://resultats.breizhchrono.com"
HEADERS = {
    **DEFAULT_HEADERS,
    "Referer": "https://resultats.breizhchrono.com/",
    "Accept": "text/html,*/*",
}

#: Préfixes de slugs de heats non-sportifs publiés par Breizh Chrono sur
#: certaines épreuves : le même peloton re-classé selon un autre critère
#: (empreinte carbone, toutes épreuves confondues, par équipe/club), jamais un
#: heat sportif distinct. Non filtrés, ils s'importaient comme une épreuve à
#: part entière avec des « finishers » fantômes — double comptage des mêmes
#: athlètes (#703, mesuré à Trégastel 2026 : heat `classement-durable---
#: triathlon`, 352 finishers fantômes, épreuve id 840).
_NON_SPORT_HEAT_PREFIXES = (
    "classement-durable",
    "classement-general",
    "challenge-",
    "general-",
)


def _is_non_sport_heat(heat_slug: str) -> bool:
    return heat_slug.startswith(_NON_SPORT_HEAT_PREFIXES)


def _parse_bc_date(html: str) -> date | None:
    """Extract event date from BC page HTML.

    resultats.breizhchrono.com embeds an ISO date (YYYY-MM-DD) ; le front live
    (live.breizhchrono.com) affiche la date au format FR (DD/MM/YYYY). On tente
    l'ISO d'abord (plus spécifique), puis le format FR en repli.
    """
    m = re.search(r'(\d{4}-\d{2}-\d{2})', html)
    if m:
        try:
            return date.fromisoformat(m.group(1))
        except ValueError:
            pass
    m = re.search(r'(\d{2})/(\d{2})/(\d{4})', html)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None


def _parse_bc_url(url: str) -> tuple[str, str, str]:
    """
    Parse a Breizh Chrono results URL into (event_id, heat, slug).

    Supported formats:
      1. /resultats-courses/{slug}-{event-id}/{heat}      (standard)
      2. /bc/resultats/coureur.jsp?ref={event-id}&heat={heat}&dossard={bib}  (direct-bib)
    """
    parsed = urlparse(url)
    path = parsed.path
    params = parse_qs(parsed.query)

    # Format 2: coureur.jsp — event_id in ?ref=, heat in ?heat=
    if "coureur.jsp" in path:
        event_id = params.get("ref", [""])[0].strip()
        heat = params.get("heat", [""])[0].strip()
        return event_id, heat, ""

    # Format 1: /resultats-courses/{slug}-{event-id}/{heat}
    path_parts = [p for p in path.strip("/").split("/") if p]
    slug_with_id = path_parts[1] if len(path_parts) >= 2 else ""
    heat = path_parts[2] if len(path_parts) >= 3 else ""

    m = re.search(r"(\d{10,}-\d+)$", slug_with_id)
    event_id = m.group(1) if m else ""
    slug = slug_with_id[: m.start()].rstrip("-") if m else slug_with_id

    return event_id, heat, slug


def _fetch_all_heats(slug_id: str, client: httpx.Client) -> list[tuple[str, str]]:
    """
    Scrape the event root page and return all (heat_slug, heat_label) pairs.
    heat_label is used to detect relays ("Relais" in the display name).

    Les heats non-sportifs (`_is_non_sport_heat`) sont exclus : sur les
    épreuves éco-labellisées, Breizh Chrono publie un heat `classement-durable`
    qui re-classe le MÊME peloton par empreinte carbone plutôt que par temps —
    pas un heat sportif distinct. Non filtré, il s'importait comme une épreuve
    à part entière avec des « finishers » fantômes (#703).

    La racine (`/resultats-courses/{slug_id}`) ne porte jamais elle-même la
    liste : elle répond systématiquement **302** vers un heat particulier
    (mesuré sur Mesquer 2026, `swim-run-m-duo`), corps vide. On ne suit donc
    pas cette redirection en silence (le défaut `follow_redirects=True` de
    `http.client()` l'aurait fait) : on la lit explicitement et on refait un
    appel vers sa cible — qui, elle, passe par le garde SSRF comme tout appel
    (#49, #101), exactement comme l'aurait fait un suivi automatique, mais de
    façon délibérée plutôt qu'implicite. La page du heat cible embarque la
    même nav inter-heats (liens `<a href="/resultats-courses/{slug_id}/…">`)
    que la racine aurait portée si elle avait répondu 200 : le parsing
    ci-dessous, inchangé, s'applique donc aussi bien à son corps.
    """
    root_url = f"{BASE}/resultats-courses/{slug_id}"
    try:
        r = client.get(root_url, follow_redirects=False)
        if r.is_redirect and r.headers.get("location"):
            target = str(httpx.URL(root_url).join(r.headers["location"]))
            r = client.get(target)
        if r.status_code != 200:
            return []
    # Une destination refusée par le garde SSRF (#101) doit ressortir : la
    # dégrader en heat unique sans nom convertirait un refus de sécurité en
    # perte silencieuse de données. Les autres pannes gardent leur repli.
    except DomainError:
        raise
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "lxml")
    prefix = f"/resultats-courses/{slug_id}/"
    heats: list[tuple[str, str]] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not href.startswith(prefix):
            continue
        rest = href[len(prefix):]
        if not rest or "/" in rest:  # skip empty or nested paths like /export
            continue
        if _is_non_sport_heat(rest):
            continue
        if rest in seen:
            continue
        seen.add(rest)
        heats.append((rest, link.get_text(strip=True)))

    return heats


def _detect_relay(heat_label: str, heat_slug: str) -> bool:
    """Indique si un heat est une épreuve d'équipe (relais, duo).

    Le libellé et le slug portent tous deux le format, et l'un des deux manque
    selon le chemin d'import : la reconnaissance des mots d'équipe est celle du
    moteur partagé (`klikego_platform.heat_is_relay`) — une seule définition
    pour les deux fronts et pour Klikego.

    S'y ajoute un signal propre à Breizh Chrono : à défaut de libellé, le slug
    d'un heat relais s'y termine par « --- », sans qu'aucun mot ne le dise.
    """
    return heat_is_relay(heat_label, heat_slug) or heat_slug.endswith("---")


def _import_one_heat(
    event_id: str, heat_slug: str, heat_label: str,
    event_name: str, slug: str, event_date, client: httpx.Client,
    *, base: str = BASE, source_url: str | None = None,
    event_type: str | None = None,
) -> list[ScrapedResult]:
    """Liste complète d'un heat (finishers + DNF/DNS/DSQ) via le moteur partagé.

    `base` / `source_url` / `event_type` sont paramétrables pour couvrir aussi le
    front live.breizhchrono.com (même plateforme Klikego, hôte et routes d'URL
    différents). Par défaut : comportement resultats.breizhchrono.com.
    """
    from app.scrapers import klikego_platform as plat
    is_relay = _detect_relay(heat_label, heat_slug)
    if source_url is None:
        source_url = f"{base}/resultats-courses/{slug}-{event_id}/{heat_slug}"
    heat_page = client.get(source_url)
    heat_page_html = heat_page.text if heat_page.status_code == 200 else ""
    if event_type is None:
        event_type = classify_event_type(heat_slug, contexte=slug)

    results = plat.build_heat_results(
        base=base,
        provider="breizhchrono",
        event_id=event_id,
        heat=heat_slug,
        heat_page_html=heat_page_html,
        event_name=event_name,
        slug=slug,
        event_type=event_type,
        source_url=source_url,
        event_date=event_date,
        client=client,
        client_factory=lambda: http.client(timeout=30, headers=HEADERS),
    )
    # Composé APRÈS build_heat_results, jamais avant (#701) : le <title> d'une
    # page de heat BC porte souvent déjà le libellé du heat, et
    # `build_heat_results` en tire le nom nu via `parse_event_name` — s'il
    # recevait un nom déjà composé, il lui retirerait le libellé qu'on vient d'y
    # ajouter (régression réintroduisant #308 par un chemin différent). Même
    # patron que Klikego (`klikego._scrape_single_heat`).
    for r in results:
        r.event_name = course_name(r.event_name, heat_label)
        r.is_relay = is_relay
    return results


def _fetch_event_date(client: httpx.Client, slug_id: str, heat: str) -> date | None:
    """Date d'épreuve, lue sur la page du heat donné (ou de la racine si `heat` vide).

    Un refus du garde SSRF (#101) remonte en erreur d'épreuve ; toute autre panne
    dégrade — l'épreuve s'importe sans date — mais laisse une trace : `None`
    change la clé d'identité de `Course` (`UNIQUE(name, event_date, event_type)`),
    et sans ce warning une épreuve importée sans date serait indiscernable d'une
    épreuve qui n'en publie pas.
    """
    date_page_url = (
        f"{BASE}/resultats-courses/{slug_id}/{heat}" if heat
        else f"{BASE}/resultats-courses/{slug_id}"
    )
    try:
        page_resp = client.get(date_page_url)
        if page_resp.status_code == 200:
            return _parse_bc_date(page_resp.text)
    except DomainError:
        raise
    except Exception as exc:
        logger.warning(
            "breizhchrono: event date unreachable at %s (%s), importing without it",
            date_page_url, exc,
        )
    return None


def scrape_event_all(
    event_id: str, heat: str, event_name: str, slug: str
) -> list[ScrapedResult]:
    """
    Fetch all participants for a Breizh Chrono event.
    If no specific heat is given, auto-discovers all heats from the event root page
    and imports each one with the correct event_type and is_relay per discipline.
    Les splits complets ne sont récupérés que pour les athlètes du club.

    Contrat historique, préservé pour les appelants directs (tests, `--single-heat`) :
    le fan-out **instrumenté** (`cache_probe`, `on_heat_start`, `FanoutTrace`) vit
    dans `scrape_event_fanout` (#707), utilisée par `BreizhChronoProvider` quand
    aucun heat n'est fixé par l'URL.
    """
    slug_id = f"{slug}-{event_id}"
    results: list[ScrapedResult] = []

    with http.client(timeout=30, headers=HEADERS) as client:
        event_date = _fetch_event_date(client, slug_id, heat)

        # Discover heats
        if heat:
            # Specific heat requested — import only that one
            heats_to_import = [(heat, "")]
        else:
            heats_to_import = _fetch_all_heats(slug_id, client)
            if not heats_to_import:
                heats_to_import = [(heat, "")]

        for heat_slug, heat_label in heats_to_import:
            heat_results = _import_one_heat(
                event_id, heat_slug, heat_label, event_name, slug, event_date, client
            )
            results.extend(heat_results)

        _fetch_tcn_fine_splits(BASE, event_id, heat, results, client)

    return results


def scrape_event_fanout(
    event_id: str, event_name: str, slug: str,
    *,
    cache_probe: Callable[[str], bool] | None = None,
    on_heat_start: Callable[[str, str, int, int], None] | None = None,
) -> tuple[list[ScrapedResult], FanoutTrace]:
    """Fan-out instrumenté sur tous les heats publiés d'un événement (issue #707).

    Même patron que `klikego.scrape_event_fanout` : `cache_probe(heat_url)`
    permet de sauter un heat déjà frais côté TTL, `on_heat_start(heat_slug,
    heat_label, index, total)` notifie la progression avant chaque heat
    effectivement scrapé (jamais un heat sauté). `heat_url` est construite
    comme la `source_url` par défaut de `_import_one_heat`, pour matcher
    exactement la `Course.source_url` déjà en base.

    Repli identique à `scrape_event_all` : si `_fetch_all_heats` ne trouve rien
    (racine injoignable, garde SSRF mis à part), on tente quand même le heat
    vide en sous-unité unique plutôt que de rendre une épreuve totalement vide.

    Les splits fins TCN (`_fetch_tcn_fine_splits`) restent appliqués une seule
    fois, après la boucle, sur l'ensemble des heats scrapés — comme
    `scrape_event_all`.

    Retour : `(results, trace)`. `trace.heats_imported` reste à 0, dérivé par
    `import_service` via l'invariant `enumerated = imported + cached + len(failures)`.
    """
    trace = FanoutTrace()
    all_results: list[ScrapedResult] = []
    slug_id = f"{slug}-{event_id}"

    with http.client(timeout=30, headers=HEADERS) as client:
        event_date = _fetch_event_date(client, slug_id, "")
        heats = _fetch_all_heats(slug_id, client) or [("", "")]
        trace.heats_enumerated = len(heats)

        heats_a_scraper: list[tuple[str, str]] = []
        for heat_slug, heat_label in heats:
            heat_url = f"{BASE}/resultats-courses/{slug_id}/{heat_slug}"
            if cache_probe is not None and cache_probe(heat_url):
                trace.heats_cached += 1
                trace.cached_urls.append(heat_url)
                continue
            heats_a_scraper.append((heat_slug, heat_label))

        total_a_scraper = len(heats_a_scraper)
        for index, (heat_slug, heat_label) in enumerate(heats_a_scraper, start=1):
            if on_heat_start is not None:
                on_heat_start(heat_slug, heat_label, index, total_a_scraper)
            try:
                all_results.extend(_import_one_heat(
                    event_id, heat_slug, heat_label, event_name, slug, event_date, client,
                ))
            except Exception as exc:
                logger.warning("Heat %s de %s en échec : %s", heat_slug, event_id, exc)
                trace.failures.append({"heat_slug": heat_slug, "reason": str(exc)})

        _fetch_tcn_fine_splits(BASE, event_id, "", all_results, client)

    return all_results, trace


# --------------------------------------------------------------------------- #
# Front live.breizhchrono.com — même plateforme Klikego, façade différente.
# --------------------------------------------------------------------------- #

#: Host de la façade live — comparé à l'**égalité** (`registry._url_host`), jamais
#: cherché en sous-chaîne : `live.breizhchrono.com.attaquant.tld` satisfait un `in`
#: et routerait le moteur live vers un hôte tiers (CodeQL
#: `py/incomplete-url-substring-sanitization`, #432).
LIVE_HOST = "live.breizhchrono.com"
LIVE_BASE = f"https://{LIVE_HOST}"


def _fetch_tcn_fine_splits(
    base: str, event_id: str, default_heat: str,
    results: list[ScrapedResult], client: httpx.Client,
) -> None:
    """Repeuple les splits fins des athlètes TCN via resultat-participant.jsp.

    Les splits fins TCN priment sur les splits inter pré-remplis : on remet à
    zéro les slots avant de reparser le détail. Muté en place sur `results`.
    """
    from app.core.club import is_tcn
    from app.scrapers.klikego import _parse_detail
    for r in results:
        if is_tcn(r.club):
            h = r.raw_data.get("heat_slug", default_heat)
            dr = client.get(
                f"{base}/v8/evenement/resultat-participant.jsp"
                f"?embedded=1&e={event_id}&heat={h}&dossard={r.bib_number}"
            )
            if dr.status_code == 200:
                r.swim_time = r.t1_time = r.bike_time = r.t2_time = r.run_time = ""
                _parse_detail(dr.text, r, {})


def _parse_live_url(url: str) -> tuple[str, str]:
    """Parse une URL live.breizhchrono.com en (reference, heat).

    `reference` (ex. `1488071608761-688`) EST la clé `ref` de course-result.jsp.
    `heat` (optionnel) restreint l'import à un seul heat. Formats couverts :
      - /external/live5/index.jsp?reference=...
      - /external/live5/classements.jsp?version=new&reference=...&heat=...
    """
    params = parse_qs(urlparse(url).query)
    reference = params.get("reference", [""])[0].strip()
    heat = params.get("heat", [""])[0].strip()
    return reference, heat


def _parse_live_heats(html: str) -> list[tuple[str, str]]:
    """Extrait les (heat_slug, heat_label) de la page live5/classements.jsp.

    Les heats sont les liens `classements.jsp?...&heat={slug}` (le libellé
    affiché sert à détecter les relais). Dédoublonné, ordre préservé.
    """
    soup = BeautifulSoup(html, "lxml")
    heats: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        heat = parse_qs(urlparse(link["href"]).query).get("heat", [""])[0].strip()
        if not heat or heat in seen:
            continue
        seen.add(heat)
        heats.append((heat, link.get_text(strip=True)))
    return heats


def _parse_live_slug(html: str) -> str:
    """Extrait le slug d'épreuve de la page live5/classements.jsp.

    Il se lit dans le lien d'export « Résultats »
    (`/resultats-courses/{slug}-{reference}/...`). Sert de repli au nom
    d'épreuve : la date, elle, n'existe pas sur cette page (cf. _parse_live_index).
    """
    m = re.search(r"/resultats-courses/([a-z0-9-]+?)-\d{10,}-\d+/", html)
    return m.group(1) if m else ""


def _norm_label(label: str) -> str:
    """Clé de jointure entre les libellés de heats des deux pages live.

    `classements.jsp` (slug + libellé) et `index.jsp` (libellé + date) exposent
    des libellés identiques au détail près de la casse et des espaces multiples.
    """
    return " ".join(label.lower().split())


def _parse_live_index(html: str) -> tuple[str, dict[str, date]]:
    """Extrait (nom d'épreuve, {libellé de heat normalisé: date}) de live5/index.jsp.

    C'est la SEULE page live qui porte les dates (`classements.jsp` n'en a
    aucune, d'où les courses sans date jusqu'ici). Chaque heat est une carte
    `<a href="?...&heat-id=…">` : libellé dans `div.h6`, date au format FR dans
    `div.small`. Les heats d'une même épreuve tombent parfois des jours
    différents (Dinard 2025 : trail le 12/09, triathlons les 13 et 14/09), d'où
    une date par heat plutôt qu'une date d'événement.

    Le `<title>` porte le vrai nom accentué (« Triathlon SwimRun Dinard Côte
    d'Emeraude »), là où le slug l'aplatit en « Cote Demeraude ».
    """
    soup = BeautifulSoup(html, "lxml")

    event_name = ""
    if soup.title and soup.title.string:
        title = " ".join(soup.title.string.split())
        m = re.match(r"(?i)^live\s*-\s*(.+?)\s*avec\s+breizhchrono$", title)
        event_name = m.group(1) if m else title

    dates: dict[str, date] = {}
    for link in soup.find_all("a", href=True):
        if "heat-id=" not in link["href"]:
            continue
        label_el = link.select_one("div.h6")
        meta_el = link.select_one("div.small")
        if not label_el or not meta_el:
            continue
        heat_date = _parse_bc_date(meta_el.get_text(" ", strip=True))
        if heat_date:
            dates[_norm_label(label_el.get_text(strip=True))] = heat_date

    return event_name, dates


def _fetch_live_meta(
    client: httpx.Client, reference: str,
) -> tuple[str, str, dict[str, date], date | None, list[tuple[str, str]]]:
    """(slug, event_name, dates_by_heat, default_date, all_heats) des deux pages live.

    `classements.jsp` liste les heats (slug + libellé) mais ne porte aucune
    date ; `index.jsp` porte le nom d'épreuve accentué et la date de chaque
    heat. On les joint par libellé (`_norm_label`). Partagé par
    `scrape_live_event_all` et `scrape_live_event_fanout` (#707).
    """
    root = client.get(f"{LIVE_BASE}/external/live5/classements.jsp?reference={reference}")
    root_html = root.text if root.status_code == 200 else ""
    slug = _parse_live_slug(root_html)

    index = client.get(f"{LIVE_BASE}/external/live5/index.jsp?reference={reference}")
    index_html = index.text if index.status_code == 200 else ""
    event_name, dates_by_heat = _parse_live_index(index_html)
    if not event_name:
        event_name = slug.replace("-", " ").title() if slug else ""
    # Repli pour un heat absent de l'index : le premier jour de l'épreuve.
    default_date = min(dates_by_heat.values()) if dates_by_heat else None

    return slug, event_name, dates_by_heat, default_date, _parse_live_heats(root_html)


def _import_one_live_heat(
    reference: str, heat_slug: str, heat_label: str, event_name: str, slug: str,
    dates_by_heat: dict[str, date], default_date: date | None, client: httpx.Client,
) -> list[ScrapedResult]:
    """Import d'un heat live, `source_url` et classification (heat seul) inclus."""
    source_url = (
        f"{LIVE_BASE}/external/live5/classements.jsp"
        f"?version=new&reference={reference}&heat={heat_slug}"
    )
    return _import_one_heat(
        reference, heat_slug, heat_label, event_name, slug,
        dates_by_heat.get(_norm_label(heat_label), default_date), client,
        base=LIVE_BASE, source_url=source_url,
        event_type=classify_event_type(heat_slug),
    )


def scrape_live_event_all(reference: str, heat: str = "") -> list[ScrapedResult]:
    """Import complet d'une épreuve live.breizhchrono.com via le moteur Klikego.

    Contrat historique, préservé pour les appelants directs (tests,
    `--single-heat`) : le fan-out **instrumenté** (`cache_probe`,
    `on_heat_start`, `FanoutTrace`) vit dans `scrape_live_event_fanout` (#707),
    utilisée par `BreizhChronoProvider` quand aucun heat n'est fixé par l'URL.
    """
    results: list[ScrapedResult] = []
    with http.client(timeout=30, headers=HEADERS) as client:
        slug, event_name, dates_by_heat, default_date, all_heats = _fetch_live_meta(
            client, reference,
        )

        if heat:
            # Mode heat unique : on récupère le libellé depuis la liste des heats
            # pour préserver la détection de relais (un slug live « ...---relais »
            # ne se détecte que via son libellé, cf. _detect_relay).
            heats_to_import = [(heat, dict(all_heats).get(heat, ""))]
        else:
            heats_to_import = all_heats or [(heat, "")]

        for heat_slug, heat_label in heats_to_import:
            results.extend(_import_one_live_heat(
                reference, heat_slug, heat_label, event_name, slug,
                dates_by_heat, default_date, client,
            ))

        _fetch_tcn_fine_splits(LIVE_BASE, reference, heat, results, client)

    return results


def scrape_live_event_fanout(
    reference: str,
    *,
    cache_probe: Callable[[str], bool] | None = None,
    on_heat_start: Callable[[str, str, int, int], None] | None = None,
) -> tuple[list[ScrapedResult], FanoutTrace]:
    """Fan-out instrumenté sur tous les heats live d'une épreuve (issue #707).

    Pendant de `scrape_event_fanout` pour la façade `live.breizhchrono.com` :
    même patron `cache_probe`/`on_heat_start`/`FanoutTrace` que Klikego,
    `heat_url` construite comme la `source_url` de `_import_one_live_heat` pour
    matcher exactement la `Course.source_url` déjà en base.
    """
    trace = FanoutTrace()
    all_results: list[ScrapedResult] = []

    with http.client(timeout=30, headers=HEADERS) as client:
        slug, event_name, dates_by_heat, default_date, all_heats = _fetch_live_meta(
            client, reference,
        )
        heats = all_heats or [("", "")]
        trace.heats_enumerated = len(heats)

        heats_a_scraper: list[tuple[str, str]] = []
        for heat_slug, heat_label in heats:
            heat_url = (
                f"{LIVE_BASE}/external/live5/classements.jsp"
                f"?version=new&reference={reference}&heat={heat_slug}"
            )
            if cache_probe is not None and cache_probe(heat_url):
                trace.heats_cached += 1
                trace.cached_urls.append(heat_url)
                continue
            heats_a_scraper.append((heat_slug, heat_label))

        total_a_scraper = len(heats_a_scraper)
        for index, (heat_slug, heat_label) in enumerate(heats_a_scraper, start=1):
            if on_heat_start is not None:
                on_heat_start(heat_slug, heat_label, index, total_a_scraper)
            try:
                all_results.extend(_import_one_live_heat(
                    reference, heat_slug, heat_label, event_name, slug,
                    dates_by_heat, default_date, client,
                ))
            except Exception as exc:
                logger.warning("Heat live %s de %s en échec : %s", heat_slug, reference, exc)
                trace.failures.append({"heat_slug": heat_slug, "reason": str(exc)})

        _fetch_tcn_fine_splits(LIVE_BASE, reference, "", all_results, client)

    return all_results, trace
