"""
Scraper for klikego.com results.
URL example:
  https://www.klikego.com/resultats/triathlon-dangers-entre-loire-et-maine-2026/1700025627600-3
    ?heat=triathlon-m-individuel&search=CADEAU&city=&category=&sexe=

Klikego API returns HTML (not JSON):
  Search: GET /v8/evenement/resultats-search.jsp?event={id}&heat={heat}&search={name}
  Detail: GET /v8/evenement/resultat-participant.jsp?embedded=1&e={id}&heat={heat}&dossard={bib}
"""
import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from bs4 import BeautifulSoup

from app.core import http

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, FanoutTrace, ScrapedResult
from .classify import classify_event_type, refine_from_splits
from .klikego_platform import heat_is_relay
from .utils import (
    DEFAULT_HEADERS,
    derive_status_from_label,
    normalize_time,
    parse_fr_date,
    to_seconds,
)

logger = logging.getLogger(__name__)



BASE = "https://www.klikego.com"
HEADERS = {
    **DEFAULT_HEADERS,
    "Referer": "https://www.klikego.com/",
    "Accept": "text/html,*/*",
}

#: Phase C (#583) — concurrence des requêtes de détail par participant. 10,
#: prudent envers une JSP dynamique (contre 20 pour `sportinnovation`, sur une
#: API JSON stable).
_DETAIL_MAX_WORKERS = 10
#: Cadence des notifications `on_detail_progress` — tous les N participants
#: traités, plus la dernière. Sans lot, la barre SSE resterait figée jusqu'à
#: la fin du heat (#583).
_DETAIL_PROGRESS_INTERVAL = 10


def _fetch_event_meta(event_id: str, slug: str, client: httpx.Client) -> tuple[str, object]:
    """Fetch the event page and return (heat, event_date)."""
    try:
        r = client.get(f"{BASE}/resultats/{slug}/{event_id}" if slug else f"{BASE}/resultats/{event_id}")
        heats = re.findall(r'heat=([^&<>\s"\']+)', r.text)
        heat = heats[0] if heats else ""
        soup = BeautifulSoup(r.text, "lxml")
        date_el = soup.select_one("span.tag.tag-brand.tag-ghost")
        event_date = parse_fr_date(date_el.get_text(strip=True)) if date_el else None
        return heat, event_date
    except httpx.HTTPError:
        return "", None


def _detect_heat(event_id: str, client: httpx.Client) -> str:
    heat, _ = _fetch_event_meta(event_id, "", client)
    return heat


#: Pointage kilométrique intermédiaire ("Vélo km 85", "CAP km 14", "KM42") — à
#: distinguer de la ligne récapitulative de section ("Vélo", "Cap"). Le
#: split_map de `_parse_detail` route par sous-chaîne ("vélo" ⊂ "vélo km 85"),
#: donc sans cette garde un pointage matche le même champ que la vraie section
#: et peut s'y substituer si la ligne récap n'est pas encore postée (#678).
_RE_KM_CHECKPOINT = re.compile(r"\bkm\.?\s*\d+")


def _parse_detail(html: str, result: ScrapedResult, raw: dict):
    soup = BeautifulSoup(html, "lxml")
    raw["detail_html"] = html[:500]

    # #675 — un statut DNS/DNF/DSQ déjà posé en phase B (`klikego_platform.
    # build_heat_results`/`parse_data_row`, sur le data block de
    # `course-result.jsp` — `_parse_search_row` ci-dessous n'est plus le
    # chemin de production) ne doit jamais être contredit par la page
    # détail : on ignore ses rang/temps/splits plutôt que de reclasser le
    # statut sur une page individuelle qui peut elle-même être incohérente
    # (cf. issue). Garde étendue à toutes les écritures de cette fonction —
    # elle n'existait jusqu'ici que pour le bloc « temps réel » ci-dessous.
    status_already_set = result.status in (STATUS_DNS, STATUS_DNF, STATUS_DSQ)

    # Name + metadata line: "M - Dossard N°2141 - V1 - LE MANS TRIATHLON"
    meta_p = soup.select_one("p.text-sm")
    if meta_p:
        meta = meta_p.get_text(strip=True)
        raw["meta"] = meta
        parts = [p.strip() for p in meta.split("-")]
        for p in parts:
            p_low = p.lower()
            # Collapse internal spaces for gender/category matching ("BE F" → "BEF")
            p_compact = re.sub(r"\s+", "", p)
            if p_compact.upper() in ("M", "F", "H"):
                # "H" is an alias for "M" used by some timing systems
                result.gender = "M" if p_compact.upper() == "H" else p_compact.upper()
            elif "dossard" in p_low:
                result.bib_number = re.sub(r"[^\d]", "", p)
            elif re.match(
                r"^(SE[HF]?|SEN[HF]?|S[1-9]\d*[HF]?|MA[1-9]\d*[HF]?|M[1-9]\d*[HF]?|"
                r"V[1-5][HF]?|VET[HF]?\d*|JU[HF]?|ES[HF]?|ESP[HF]?|CA[HF]?|BE[HF]?|"
                r"MI[HF]?|PO[HF]?|PU[HF]?)$",
                p_compact, re.I
            ):
                result.category = p_compact
            elif not any(x in p_low for x in ("dossard", "n°")) and p_compact.upper() not in ("M", "F", "H"):
                if result.club == "":
                    result.club = p

    # Rankings — find label divs by exact text, then read sibling. « Temps
    # Officiel » n'est qu'un repli pour total_time : sur une épreuve à vagues de
    # départ, il porte le temps canon (décalé par la vague de l'athlète), quand
    # les splits — et « temps réel » plus bas — sont calculés sur le chrono net.
    # Poser les deux référentiels sur une même ligne les rendait incohérents
    # entre eux sans que rien ne le signale (#676). « temps réel », rencontré
    # plus loin dans le document, prime donc dessus quand il existe.
    rank_map = {
        "classement général": "overall",
        "classement catégorie": "category",
        "classement sexe": "gender",
        "classement genre": "gender",
    }
    for div in soup.find_all("div"):
        text = div.get_text(strip=True)
        text_low = text.lower()

        if text == "Temps Officiel":
            val_div = div.find_next_sibling("div")
            if val_div:
                t = normalize_time(val_div.get_text(strip=True))
                if t and t != "00:00:00" and not status_already_set:
                    result.total_time = t  # repli, écrasé plus bas par « temps réel » s'il existe

        for label, field in rank_map.items():
            if text_low == label:
                val_div = div.find_next_sibling("div")
                if val_div:
                    rank_text = val_div.get_text(strip=True)
                    m = re.match(r"(\d+)", rank_text)
                    if m and int(m.group(1)) > 0 and not status_already_set:
                        rank = int(m.group(1))
                        if field == "overall":
                            result.rank_overall = rank
                        elif field == "category":
                            result.rank_category = rank
                        else:
                            result.rank_gender = rank

    # Split times — table rows: [stage_name, time, pos_gen, pos_cat]
    # Order: most specific (longest) patterns first to avoid "natation" matching
    # "transition natation - vélo" before the transition key does.
    split_map = [
        # Transitions — specific before generic
        ("transition natation", "t1"),
        ("transition nat", "t1"),
        ("chg nat", "t1"),          # "Chg Nat." (changement natation)
        ("transition vélo", "t2"),
        ("transition velo", "t2"),
        ("chg vé", "t2"),           # "Chg Vélo"
        ("chg ve", "t2"),           # "Chg Velo" (ASCII fallback)
        ("transition 1", "t1"),     # "Transition 1" (variante numérotée)
        ("transition 2", "t2"),     # "Transition 2"
        ("transition", "t1"),       # "Transition" générique (aquathlon, etc.)
        ("t1", "t1"),
        ("t2", "t2"),
        # Swim
        ("natation", "swim"),
        ("swim", "swim"),
        ("nat", "swim"),            # "NAT" (forme abrégée utilisée sur certains events jeunes)
        # Bike
        ("vélo", "bike"),
        ("velo", "bike"),
        ("bike", "bike"),
        ("cyclisme", "bike"),
        # Run — duathlon: "CAP 1" / "Course à pied 1" (run1) → swim slot, "CAP 2" / "Course à pied 2" → run slot
        ("course à pied 1", "swim"),
        ("course a pied 1", "swim"),
        ("course à pied 2", "run"),
        ("course a pied 2", "run"),
        ("cap 1", "swim"),
        ("cap 2", "run"),
        ("course", "run"),
        ("cap", "run"),
        ("run", "run"),
        ("à pied", "run"),
        ("a pied", "run"),
    ]

    # --- Collect split rows ---
    splits_raw: list[tuple[str, str, str | None]] = []  # (stage, time_norm, field|None)
    for row in soup.select("tr.result-row[data-dossard]"):
        tds = row.find_all("td")
        if len(tds) < 2:
            continue
        stage = tds[0].get_text(strip=True).lower()
        time_norm = normalize_time(tds[1].get_text(strip=True))

        # "temps réel" row = total time reported by timing system, not a split.
        # Chrono net, cohérent avec la somme des splits ci-dessous — il prime sur
        # « Temps Officiel » (#676), posé plus haut comme simple repli. Un
        # 00:00:00 (non-finisher DNS) ne doit en revanche pas écraser un
        # total_time valide déjà posé, ni ressusciter un total_time vidé en amont
        # par le statut : `status_already_set` couvre aussi le cas où la page
        # détail publie ici une valeur non nulle malgré un DNS/DNF/DSQ déjà posé
        # (#675).
        if "temps" in stage and "réel" in stage:
            if not status_already_set and time_norm and time_norm != "00:00:00":
                result.total_time = time_norm
            continue

        field: str | None = None
        if not _RE_KM_CHECKPOINT.search(stage):
            for key, f in split_map:
                if key in stage:
                    field = f
                    break
        splits_raw.append((stage, time_norm, field))

    # --- Detect cumulative times ---
    # If times for mapped stages are strictly increasing → they are cumulative
    # (checkpoints like KM42 are skipped for this check)
    mapped_secs = [to_seconds(t) for _, t, f in splits_raw if f and t]
    is_cumulative = (
        len(mapped_secs) >= 2
        and all(mapped_secs[i] < mapped_secs[i + 1] for i in range(len(mapped_secs) - 1))
    )
    raw["cumulative"] = is_cumulative

    # --- Assign split times (computing deltas if cumulative) ---
    prev_secs = 0
    last_mapped_secs = 0
    for stage, time_norm, field in splits_raw:
        # #675 — statut DNS/DNF/DSQ déjà posé en phase B : la page détail ne
        # doit pas lui attribuer de splits, même non nuls.
        if status_already_set:
            continue

        secs = to_seconds(time_norm)

        if is_cumulative and secs > 0:
            if field is not None:
                # Duration = cumulative_now - cumulative_after_previous_mapped_stage
                dur = secs - prev_secs
                prev_secs = secs
                last_mapped_secs = secs
                h, rem = divmod(dur, 3600)
                m, s = divmod(rem, 60)
                time_val = f"{h:02d}:{m:02d}:{s:02d}"
            else:
                # Intermediate checkpoint (e.g. KM42) — store as-is, don't shift prev
                time_val = time_norm
        else:
            time_val = time_norm

        # In non-cumulative mode: "first set wins" — intermediate checkpoints
        # (e.g. "Vélo km 85", "CAP km 14") share the same field key as the
        # main segment but must not overwrite it.  In cumulative mode we always
        # overwrite because each value is a freshly-computed delta.
        def _set(attr: str, val: str) -> None:
            if is_cumulative or not getattr(result, attr):
                setattr(result, attr, val)
            else:
                # _set est appelé immédiatement dans l'itération courante : la capture
                # de `stage` est correcte ici (pas de closure différée). → B023 faux positif.
                raw[f"split_{stage}"] = val  # noqa: B023

        if field == "swim":
            _set("swim_time", time_val)
        elif field == "t1":
            _set("t1_time", time_val)
        elif field == "bike":
            _set("bike_time", time_val)
        elif field == "t2":
            _set("t2_time", time_val)
        elif field == "run":
            _set("run_time", time_val)
        else:
            raw[f"split_{stage}"] = time_val

    # If cumulative and run is absent, derive from total − last mapped stage end
    if is_cumulative and not result.run_time and result.total_time:
        total_s = to_seconds(result.total_time)
        if total_s > last_mapped_secs > 0:
            run_s = total_s - last_mapped_secs
            h, rem = divmod(run_s, 3600)
            m, s = divmod(rem, 60)
            result.run_time = f"{h:02d}:{m:02d}:{s:02d}"


def _parse_search_row(
    row, event_id: str, heat: str, event_name: str, slug: str, rank: int
) -> "ScrapedResult":
    """Extract a ScrapedResult from a search-list <tr> row (no detail call)."""
    result = ScrapedResult(
        source_url=(
            f"{BASE}/resultats/{slug}/{event_id}?heat={heat}"
        ),
        provider="klikego",
    )
    result.event_name = event_name
    result.event_type = classify_event_type(heat, contexte=slug)
    result.rank_overall = rank
    # Un heat Klikego est mono-discipline → drapeau relais uniforme sur ses résultats.
    result.is_relay = heat_is_relay(heat)

    dossard = row.get("data-dossard", "")
    result.bib_number = dossard

    name_cell = row.select_one("td.truncate")
    if name_cell:
        full = name_cell.get_text(strip=True)
        parts = full.split()
        i = 0
        while i < len(parts) and parts[i].isupper():
            i += 1
        result.athlete_name = " ".join(parts[:i])
        result.athlete_firstname = " ".join(parts[i:])

    time_cell = row.select_one("td.font-mono")
    if time_cell:
        raw_time = time_cell.get_text(strip=True)
        status = derive_status_from_label(raw_time)
        if status:
            # La colonne temps porte un label de statut (Abandon/DNF…) au lieu
            # d'un temps : on pose le statut et on purge temps/rang positionnel.
            result.status = status
            result.rank_overall = None
        else:
            result.total_time = normalize_time(raw_time)

    # Club column — present in some events as a td with class "truncate" after the name
    # The search row may contain multiple truncate cells: [name, club]
    truncate_cells = row.select("td.truncate")
    if len(truncate_cells) >= 2:
        result.club = truncate_cells[1].get_text(strip=True)

    return result


def _heat_source_url(event_id: str, slug: str, heat: str) -> str:
    """URL canonique d'un heat Klikego — clé de cache TTL et de dédup source_url."""
    return (
        f"{BASE}/resultats/{slug}/{event_id}?heat={heat}" if slug
        else f"{BASE}/resultats/{event_id}?heat={heat}"
    )


def _fetch_and_apply_detail(event_id: str, heat: str, bib: str, r: "ScrapedResult") -> None:
    """Récupère la page détail d'un participant et lui applique ses splits fins.

    Client httpx propre à cet appel (thread-safe, précédent
    `sportinnovation._fetch_athlete_splits`) : les workers de la phase C
    n'ont rien en commun qui ne soit déjà thread-safe (chaque `r` est unique
    à son bib), donc pas de verrou nécessaire au-delà du client par appel.

    Un échec réseau est journalisé et avalé, comme
    `sportinnovation._fetch_athlete_splits` : sur une JSP dynamique, un flake
    sur un participant ne doit ni faire échouer tout le heat, ni — pire —
    laisser `ThreadPoolExecutor.__exit__` (sans `cancel_futures`) épuiser les
    ~250 requêtes déjà soumises avant de laisser remonter l'exception. Le
    participant garde alors ses splits de phase B (inter), déjà en place.
    """
    try:
        with http.client(timeout=30, headers=HEADERS) as c:
            dr = c.get(
                f"{BASE}/v8/evenement/resultat-participant.jsp"
                f"?embedded=1&e={event_id}&heat={heat}&dossard={bib}"
            )
    except httpx.HTTPError:
        logger.warning("Détail illisible pour le dossard %s (heat %s) : réseau", bib, heat, exc_info=True)
        return
    if dr.status_code != 200:
        return
    # Reset des slots pour que les splits fins priment sur les inter pré-remplis.
    inter_backup = {s: getattr(r, f"{s}_time") for s in _SPLIT_SLOTS}
    for s in _SPLIT_SLOTS:
        setattr(r, f"{s}_time", "")
    _parse_detail(dr.text, r, {})
    # Page détail sans splits (ex. non-partant) : on restaure les inter.
    if not any(getattr(r, f"{s}_time") for s in _SPLIT_SLOTS):
        for s, t in inter_backup.items():
            setattr(r, f"{s}_time", t)


def _scrape_single_heat(
    event_id: str, heat: str, heat_label: str, event_name: str, slug: str,
    event_date: object, client: httpx.Client,
    *, on_detail_progress: Callable[[int, int], None] | None = None,
) -> list["ScrapedResult"]:
    """Scrape un heat Klikego (finishers + DNF/DNS/DSQ) — extraction du corps original.

    Phase A' — HTML de la page heat (options inter).
    Phase B — liste complète + splits inter pour tous (moteur partagé).
    Phase C — splits fins via page détail, réservée aux membres du TCN (#699),
    priment sur les splits grossiers de la phase B.

    `heat_label` (libellé publié, ex. « Triathlon Pupilles (10-11 ans) ») suffixe
    `event_name` via `klikego_platform.course_name` — la même fonction que Breizh
    Chrono (#308). Composé **après** `build_heat_results` et non transmis en
    paramètre `event_name` : le `<title>` d'une page de heat Klikego ne porte
    jamais le libellé du heat (contrairement à Breizh Chrono), donc
    `build_heat_results` y lit toujours un nom nu et **écraserait** silencieusement
    toute composition faite en amont (`parse_event_name(...) or event_name`).
    Sans ce suffixe, deux heats de même `event_type`/`is_relay` (poussins et
    pupilles à Mesquer 2026, tous deux `triathlon` non-relais) partagent la même
    identité de `Course` et fusionnent — un dossard réutilisé d'un heat à l'autre
    réattribue silencieusement un résultat à un autre athlète.
    """
    from app.scrapers import klikego_platform as plat

    heat_page = client.get(_heat_source_url(event_id, slug, heat))
    heat_page_html = heat_page.text if heat_page.status_code == 200 else ""
    source_url = _heat_source_url(event_id, slug, heat)

    results = plat.build_heat_results(
        base=BASE,
        provider="klikego",
        event_id=event_id,
        heat=heat,
        heat_page_html=heat_page_html,
        event_name=event_name,
        slug=slug,
        event_type=classify_event_type(heat, contexte=slug),
        source_url=source_url,
        event_date=event_date,
        client=client,
        client_factory=lambda: http.client(timeout=30, headers=HEADERS),
    )
    for r in results:
        r.event_name = plat.course_name(r.event_name, heat_label)
    bib_to_result = {r.bib_number: r for r in results}

    # Phase C — splits fins via la page détail, réservée aux membres du TCN
    # (#699) : sans ce filtre, un événement multi-heats déclenche une requête
    # de détail par participant de tous clubs, jusqu'à un millier sur un gros
    # événement multi-courses — même patron que Breizh Chrono
    # (`breizhchrono._fetch_tcn_fine_splits`). Les autres participants gardent
    # les splits grossiers de la phase B.
    # La page détail (natation/T1/vélo/T2/course) est la source fine ; elle
    # prime sur les splits inter grossiers de la phase B quand elle en fournit.
    # Parallélisée (#583) : 94 % des requêtes d'un import Klikego étaient une
    # requête séquentielle par participant, jusqu'à ~4 min sur 250 inscrits.
    # Chaque `r` n'est touché que par le worker de son propre bib — aucun état
    # partagé entre tâches, donc aucun verrou requis au-delà du client HTTP.
    from app.core.club import is_tcn
    tcn_bib_to_result = {bib: r for bib, r in bib_to_result.items() if is_tcn(r.club)}
    total = len(tcn_bib_to_result)
    done = 0
    with ThreadPoolExecutor(max_workers=_DETAIL_MAX_WORKERS) as pool:
        futures = {
            pool.submit(_fetch_and_apply_detail, event_id, heat, bib, r): bib
            for bib, r in tcn_bib_to_result.items()
        }
        for future in as_completed(futures):
            future.result()
            done += 1
            if on_detail_progress is not None and (
                done % _DETAIL_PROGRESS_INTERVAL == 0 or done == total
            ):
                on_detail_progress(done, total)

    # Les splits fins de la phase C priment sur le libellé du heat (#679) :
    # une course à pied ne publie jamais natation ET vélo, un heat mal nommé
    # (« Diaoul Foulées Open ») est reclassé triathlon une fois ces deux
    # splits confirmés sur un participant.
    for r in results:
        r.event_type = refine_from_splits(
            r.event_type, has_swim=bool(r.swim_time), has_bike=bool(r.bike_time),
        )

    return results


def scrape_event_all(
    event_id: str, heat: str, event_name: str, slug: str,
    *, on_detail_progress: Callable[[int, int], None] | None = None,
) -> list["ScrapedResult"]:
    """Scrape un seul heat Klikego — contrat historique.

    Le fan-out sur tous les heats vit **au niveau du provider**
    (`KlikegoProvider.scrape_event_all`) : il boucle sur cette fonction
    heat par heat. Ici on préserve la signature originale pour tous les
    appelants directs (tests, batch, `--single-heat`) : sans libellé de heat
    connu à cet appel, `event_name` reste nu (pas de suffixe vide).

    `on_detail_progress(done, total)` (mot-clé, défaut `None` — les appelants
    historiques ne le passent pas) relaie la progression de la phase C à
    `_scrape_single_heat`, qui la rapporte déjà au fan-out. Sans lui, le flux
    SSE d'un import mono-heat restait **muet** de bout en bout, alors même que
    la phase C est la partie lente (jusqu'à ~250 finishers dans un seul heat,
    #583) — revue finale de #698.
    """
    with http.client(timeout=30, headers=HEADERS) as client:
        _, event_date = _fetch_event_meta(event_id, slug, client)
        return _scrape_single_heat(
            event_id, heat, "", event_name, slug, event_date, client,
            on_detail_progress=on_detail_progress,
        )


def scrape_event_fanout(
    event_id: str, event_name: str, slug: str,
    *, cache_probe: Callable[[str], bool] | None = None,
    on_heat_start: Callable[[str, str, int, int], None] | None = None,
    on_detail_progress: Callable[[str, str, int, int, int, int], None] | None = None,
) -> tuple[list["ScrapedResult"], FanoutTrace]:
    """Scrape tous les heats publiés d'un événement Klikego (issue #156).

    GET la page événement, énumère les heats via `_enumerate_heats`, boucle sur
    chacun. Pour chaque heat, `cache_probe(heat_url)` (si fourni) permet de
    sauter les heats déjà en cache TTL. Les exceptions par heat sont capturées
    dans `trace.failures` et ne remontent pas — un heat en échec n'annule pas
    les autres (FR-004).

    `on_heat_start(heat_slug, heat_label, index, total)` est notifié **avant** le
    scrape d'un heat non caché — jamais pour un heat sauté (cache_probe → True) :
    l'appelant compte sa propre progression sur les seuls heats effectivement
    scrapés, sinon un événement à 6 heats sur 8 cachés paraîtrait progresser
    de 1 à 8 en 4 secondes. `heat_label` est le libellé publié par Klikego
    (« Triathlon S individuel », « SwimRun M duo »…), à afficher tel quel.

    `on_detail_progress(heat_slug, heat_label, heat_index, heats_total, done,
    total)` (#583) rapporte l'avancement de la phase C **dans** le heat en
    cours — sans lui, un heat de 250 participants resterait figé plusieurs
    minutes entre deux `on_heat_start`.

    Retour : `(results, trace)`. `trace.heats_imported` reste à 0 ici —
    dérivé par `import_service` via l'invariant
    `enumerated = imported + cached + len(failures)`.
    """
    trace = FanoutTrace()
    all_results: list[ScrapedResult] = []

    with http.client(timeout=30, headers=HEADERS) as client:
        _, event_date = _fetch_event_meta(event_id, slug, client)

        event_page = client.get(
            f"{BASE}/resultats/{slug}/{event_id}" if slug
            else f"{BASE}/resultats/{event_id}"
        )
        event_html = event_page.text if event_page.status_code == 200 else ""
        heats = _enumerate_heats(event_html)
        trace.heats_enumerated = len(heats)

        # Pré-filtre les heats à scraper : `heats_a_scraper` fixe le total notifié
        # à `on_heat_start`, sans quoi la progression sauterait des indices.
        heats_a_scraper: list[tuple[str, str]] = []
        for heat_slug, heat_label in heats:
            heat_url = _heat_source_url(event_id, slug, heat_slug)
            if cache_probe is not None and cache_probe(heat_url):
                trace.heats_cached += 1
                trace.cached_urls.append(heat_url)
                continue
            heats_a_scraper.append((heat_slug, heat_label))

        total_a_scraper = len(heats_a_scraper)
        for index, (heat_slug, heat_label) in enumerate(heats_a_scraper, start=1):
            if on_heat_start is not None:
                on_heat_start(heat_slug, heat_label, index, total_a_scraper)
            detail_progress = None
            if on_detail_progress is not None:
                def detail_progress(
                    done, total,
                    _slug=heat_slug, _label=heat_label, _index=index,
                ) -> None:
                    on_detail_progress(_slug, _label, _index, total_a_scraper, done, total)
            try:
                all_results.extend(_scrape_single_heat(
                    event_id, heat_slug, heat_label, event_name, slug, event_date, client,
                    on_detail_progress=detail_progress,
                ))
            except Exception as exc:
                logger.warning("Heat %s de %s en échec : %s", heat_slug, event_id, exc)
                trace.failures.append({"heat_slug": heat_slug, "reason": str(exc)})

    return all_results, trace


_SPLIT_SLOTS = ("swim", "t1", "bike", "t2", "run")



# Énumération des heats d'un événement (issue #156).
# Klikego rend la liste dans un <el-select name="heat">/<el-option value="..."><span>...</span></el-option>.
# Une option value="" (placeholder « choisir un heat ») peut coexister avec les vrais heats — on la filtre.
_RE_SELECT_HEAT = re.compile(
    r'<el-select[^>]*name="heat"[^>]*>(.*?)</el-select>', re.DOTALL
)
_RE_HEAT_OPTION = re.compile(
    r'<el-option\s+value="([^"]+)"[^>]*>\s*<span>([^<]*)</span>'
)


def _enumerate_heats(html: str) -> list[tuple[str, str]]:
    """Extrait la liste (slug, label) de tous les heats publiés à la source.

    Ordre du DOM préservé. Filtre les options `value=""` (placeholder Klikego).
    Retourne [] si `<el-select name="heat">` est absent ou vide.
    """
    m = _RE_SELECT_HEAT.search(html)
    if not m:
        return []
    return [
        (slug, label.strip())
        for slug, label in _RE_HEAT_OPTION.findall(m.group(1))
        if slug
    ]
