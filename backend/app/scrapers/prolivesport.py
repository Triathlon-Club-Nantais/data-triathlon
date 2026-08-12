"""
Scraper prolivesport.fr — fan-out par course (#269).

Formes d'URL acceptées :
  https://www.prolivesport.fr/index.php?chap=event&sub=liveV3&eventId=979&race=Triathlon%20M
  https://www.prolivesport.fr/V2/result/1060           (nue)
  https://www.prolivesport.fr/result/1082/4            (index positionnel)

API base : https://api.prolivesport.fr/apiws
Token    : AUTH_PLSWS_V2  (codé en dur dans le bundle Angular)

Flux nominal (`scrape_event_fanout`) :
  1. `_parse_url`        → eventId (le jeton `race` est ignoré : le fan-out énumère)
  2. `event/detail`      → nom + date, partagés par toutes les courses
  3. `result/raceList`   → la liste des courses = les sous-unités
  4. `result/indiv`      → les lignes, **regroupées par leur champ `race`**
  5. `result/splitDetail`→ un seul appel pour l'événement, filtré par course

**Le piège central de ce fournisseur** (mesuré, cf.
`docs/superpowers/specs/2026-08-11-prolivesport-fanout-sondage.md`) :
`GET /result/indiv/{eventId}/{race}/` **ignore silencieusement** le segment
`race` sur une partie des événements et renvoie l'**événement entier**. La
corrélation observée — filtre ignoré dès que le code de course porte un espace
ou un tiret bas — est parfaite sur le panel, mais on ne s'y fie pas : la seule
vérité est le champ `race` porté par chaque ligne de la réponse, et le
regroupement se fait toujours côté client. S'en fier coûtait ~4 000
participations mal attribuées (rangs, temps et type d'épreuve faux) et
l'événement stocké autant de fois qu'il avait de lignes dans le Sheet.
"""
import logging
import re
from collections.abc import Callable
from datetime import date
from typing import NamedTuple
from urllib.parse import parse_qs, quote, urlparse

import httpx

from app.core import http

from .base import (
    STATUS_DNF,
    STATUS_DNS,
    STATUS_DSQ,
    STATUS_FINISHER,
    FanoutTrace,
    ScrapedResult,
)
from .classify import classify_event_type
from .utils import (
    DEFAULT_HEADERS,
    normalize_rank,
    normalize_time,
    qualify_event_name,
)

logger = logging.getLogger(__name__)

API_BASE = "https://api.prolivesport.fr/apiws"
TOKEN = "AUTH_PLSWS_V2"
HEADERS = {
    **DEFAULT_HEADERS,
    "access-token": TOKEN,
    "Accept": "application/json",
}

#: Essais d'un `result/indiv` avant abandon. Les réponses « événement entier »
#: pèsent jusqu'à 14,7 Mo et la source rend des **500 à corps vide
#: intermittents** dessus : mesuré 3 échecs d'affilée sur une course, 4 sur une
#: autre, puis succès. Sans reprise, les plus gros événements échoueraient
#: régulièrement en entier. Pas de temporisation entre les essais : les 500
#: arrivent immédiatement, ils ne signalent pas une surcharge à laisser passer.
_ESSAIS_INDIV = 5

#: Délai d'un `result/indiv` — large, à la mesure des charges de 14,7 Mo.
_TIMEOUT_INDIV = 60

# Labels → split field mapping
_SWIM_LABELS = {"swim", "nat", "cat/nat", "natation"}
_T1_LABELS   = {"#1", "t1", "trans1", "transition1"}
_BIKE_LABELS  = {"bike", "velo", "vélo", "cycle", "bikestart"}
_T2_LABELS   = {"#2", "t2", "trans2", "transition2"}
_RUN_LABELS  = {"run", "cap", "course", "courseapied", "c.a.p"}


class _SplitPlan(NamedTuple):
    """Résolution des rôles de split pour une course (#280).

    `resolved` ne porte que les rôles à candidat **unique** : un rôle à
    ≥ 2 candidats (mesuré sur l'événement 979 : bike ← Bike/BikeStart/BikeEnd)
    ne peut pas être tranché sans deviner lequel des champs est la vraie durée
    de section — il est donc exclu, et `ambigu` le signale à l'appelant.
    `tous_les_champs` porte l'intégralité des champs de la course, triés par
    suffixe numérique (`T3` → 3) : nécessaire pour reconstruire `segments`
    sans rien perdre quand `ambigu` est vrai (cf. design, "tout ou rien").
    """

    resolved: dict[str, str]
    ambigu: bool
    tous_les_champs: list[tuple[str, str]]


def _numero_champ(field: str) -> int:
    """Suffixe numérique d'un champ (`"T3"` → `3`), 0 si illisible."""
    m = re.search(r"\d+", field)
    return int(m.group()) if m else 0


def _build_split_map(splits: list, race: str) -> _SplitPlan:
    """Construit la résolution des rôles de split pour une course (#280).

    Un rôle avec un seul champ candidat est résolu ; à partir de deux, aucun
    des deux n'est retenu (cf. sondage/design : rien ne permet de trancher
    lequel est la durée de section plutôt qu'un point cumulé redondant).
    """
    candidats: dict[str, list[str]] = {}
    champs_de_la_course: list[tuple[str, str]] = []
    for s in splits:
        if s.get("race", "").lower() != race.lower():
            continue
        field = s.get("field", "")
        label_brut = s.get("label") or s.get("displayTitle") or ""
        champs_de_la_course.append((field, label_brut))
        label = re.sub(r"\s+", "", label_brut).lower()
        if any(lbl in label for lbl in _SWIM_LABELS):
            candidats.setdefault("swim", []).append(field)
        elif any(lbl == label for lbl in _T1_LABELS):
            candidats.setdefault("t1", []).append(field)
        elif any(lbl in label for lbl in _BIKE_LABELS):
            candidats.setdefault("bike", []).append(field)
        elif any(lbl == label for lbl in _T2_LABELS):
            candidats.setdefault("t2", []).append(field)
        elif any(lbl in label for lbl in _RUN_LABELS):
            candidats.setdefault("run", []).append(field)

    resolved = {role: fields[0] for role, fields in candidats.items() if len(fields) == 1}
    ambigu = any(len(fields) > 1 for fields in candidats.values())
    champs_de_la_course.sort(key=lambda fc: _numero_champ(fc[0]))
    return _SplitPlan(resolved=resolved, ambigu=ambigu, tous_les_champs=champs_de_la_course)


def _is_relay(athlete: dict) -> bool:
    """Vrai si la participation est un relais d'équipe.

    Sur ProliveSport, une équipe de relais porte `category="Relay"` /
    `categoryRef="R"`, là où une participation solo porte une catégorie d'âge
    (Senior/SE, Master/MA, Cadet/CA…). Le nom du relais arrive dans `lastname`.
    """
    return (
        (athlete.get("categoryRef") or "").strip().upper() == "R"
        or (athlete.get("category") or "").strip().lower() == "relay"
    )


def _parse_athlete(athlete: dict, plan: _SplitPlan, url: str, event_name: str, event_type: str, event_date) -> ScrapedResult:
    result = ScrapedResult(source_url=url, provider="prolivesport")
    result.event_name = event_name
    result.event_type = event_type
    result.event_date = event_date

    result.athlete_name = athlete.get("lastname", "").strip().upper()
    result.athlete_firstname = athlete.get("firstname", "").strip()
    result.bib_number = athlete.get("number", "")
    result.club = athlete.get("club", "")
    result.category = athlete.get("categoryRef", athlete.get("category", ""))
    result.gender = athlete.get("sex", "")
    result.is_relay = _is_relay(athlete)
    result.status = _derive_status(athlete)
    if result.status == STATUS_FINISHER:
        result.rank_overall = normalize_rank(athlete.get("rank"))
        result.rank_gender = normalize_rank(athlete.get("rankSex"))
        result.rank_category = normalize_rank(athlete.get("rankCat"))
        result.total_time = normalize_time(athlete.get("time", ""))
    # Non-finisher : on laisse total_time="" et les rangs à None (défauts de la
    # dataclass) — l'API renvoie des sentinelles (99991/99992) pour les non-classés.

    if plan.ambigu:
        # Au moins un rôle a ≥ 2 candidats (#280) : impossible de trancher lequel
        # est la durée de section plutôt qu'un point cumulé redondant. Toute la
        # course part dans `segments` — y compris les rôles non ambigus, car
        # `mapping.build_splits` fait primer `segments` en entier sur les 5 slots
        # positionnels (aucune fusion) : les laisser dans les slots les ferait
        # disparaître silencieusement de `Participation.splits`.
        result.segments = [
            (label, t)
            for field, label in plan.tous_les_champs
            if (t := normalize_time(athlete.get(f"time{field}", ""))) and t != "00:00:00"
        ]
    else:
        for role, field in plan.resolved.items():
            t = normalize_time(athlete.get(f"time{field}", ""))
            if not t or t == "00:00:00":
                continue
            setattr(result, f"{role}_time", t)

    result.raw_data = {k: v for k, v in athlete.items() if not k.isdigit()}
    return result


def _fetch_indiv(event_id: str, race: str, client: httpx.Client) -> list[dict]:
    """Lignes de `result/indiv`, avec reprise sur les 500 intermittents.

    Attention : la réponse peut couvrir **tout l'événement** et non la seule
    course demandée (cf. le docstring du module). Ce qu'elle contient se lit
    ligne par ligne dans le champ `race`, jamais dans le paramètre demandé.

    Seuls les 5xx sont rejoués : un 4xx ou un `success: false` disent quelque
    chose de la requête, les rejouer ne ferait que répéter l'erreur.
    """
    statut = 0
    for essai in range(1, _ESSAIS_INDIV + 1):
        r = client.get(
            f"{API_BASE}/result/indiv/{event_id}/{race}/", timeout=_TIMEOUT_INDIV
        )
        if r.status_code >= 500:
            statut = r.status_code
            logger.warning(
                "Prolivesport indiv %s/%s : HTTP %s à l'essai %s/%s",
                event_id, race, statut, essai, _ESSAIS_INDIV,
            )
            continue
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            raise ValueError(
                f"Prolivesport API erreur pour event {event_id} / race {race}: "
                f"{data.get('message')}"
            )
        return data.get("result", [])

    raise httpx.HTTPError(
        f"Prolivesport indiv {event_id}/{race} : {_ESSAIS_INDIV} essais, "
        f"dernier statut HTTP {statut}."
    )


def _fetch_splits(event_id: str, client: httpx.Client) -> list[dict]:
    """Points de passage publiés, pour l'événement **entier**.

    Un seul appel suffit : la réponse porte toutes les courses, `_build_split_map`
    en extrait celle qui l'intéresse. Construire la carte pour une course et
    l'appliquer aux autres était le défaut n° 5 du sondage — sur l'événement 1060,
    la carte de « CHTRI 6-7 ans » (aucun split publié) était appliquée aux
    3 120 lignes, effaçant les splits de `CHTRIMAN 113` et `CHTRIMAN 226`.
    """
    r = client.get(f"{API_BASE}/result/splitDetail/{event_id}/", timeout=15)
    r.raise_for_status()
    return r.json().get("result", [])


def _fetch_event_meta(event_id: str, client: httpx.Client) -> tuple[str, date | None]:
    """Return (event_name, event_date)."""
    r = client.get(f"{API_BASE}/event/detail/{event_id}/", timeout=15)
    r.raise_for_status()
    result = r.json().get("result", [{}])
    ev = result[0] if result else {}
    name = ev.get("eventName", "")
    raw_date = ev.get("eventDateStart", "")
    event_date = None
    if raw_date and raw_date[:4] != "0000":
        try:
            event_date = date.fromisoformat(raw_date[:10])
        except ValueError:
            # Date illisible : `event_date` reste `None`, l'épreuve s'importe sans.
            pass
    return name, event_date



def _parse_url(url: str) -> tuple[str, str]:
    """
    Extrait (event_id, race) d'une URL prolivesport. Deux formes gérées :
      - query : `?eventId=1082&race=S`
      - front : `/result/{eventId}/{race}` où race est un index positionnel
        (ex. `6`) ou un code (ex. `S`).
    `race` peut être vide → 1ʳᵉ course par défaut (résolu plus tard).
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    event_id = params.get("eventId", [""])[0]
    race = params.get("race", [""])[0].strip()

    if not event_id:
        # Forme front /result/{eventId}/{race}
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if "result" in parts:
            rest = parts[parts.index("result") + 1:]
            event_id = rest[0] if rest else ""
            race = rest[1] if len(rest) >= 2 else race
        elif parts and not parts[-1].endswith(".php"):
            # Forme `/fftri/grand-prix-duathlon` : une page de **série**, pas une
            # épreuve — même nature que le cas Competitor / ironman.com. Coquille
            # SPA Angular sans aucun `eventId`, et le repli navigateur a été
            # supprimé avec sa dépendance (#102) : rien à en tirer par scraping.
            # L'API de série existe mais est derrière un JWT codé en dur dans le
            # bundle, expiré depuis le 2025-04-07. Le message doit dire ce qu'est
            # l'URL, sinon `import_service` la traduit en « fournisseur non
            # supporté » — trompeur, ProLiveSport *est* supporté.
            raise ValueError(
                f"L'URL prolivesport.fr « {parsed.path} » désigne une page de "
                "série (un Grand Prix et ses étapes), pas une épreuve : son "
                "contenu est rendu par le navigateur et ne porte aucun "
                "identifiant d'événement. Ouvrir l'étape voulue et copier son "
                "lien, de la forme index.php?chap=event&sub=liveV3&eventId=…"
            )

    if not event_id:
        raise ValueError("URL prolivesport.fr sans identifiant d'événement.")
    return event_id, race


def _sub_source_url(event_id: str, race: str) -> str:
    """URL canonique d'une course — clé de cache TTL et `source_url` persistée.

    La forme doit être **identique caractère pour caractère** à celle des liens
    du Sheet : `Course` est retrouvée par égalité exacte de `source_url`
    (`course_repository.get_latest_by_source_url`), donc un `+` au lieu de `%20`
    créerait un doublon au lieu de réécrire la `Course` existante. `quote`
    encode bien l'espace en `%20` et laisse `_` et `-` intacts (`M_relay`,
    `PO-PU`).
    """
    return (
        "https://www.prolivesport.fr/index.php?chap=event&sub=liveV3"
        f"&eventId={event_id}&race={quote(race)}"
    )


def _resolve_race(race: str, races: list[dict]) -> str:
    """
    Résout le token `race` en code de course :
      - vide → 1ʳᵉ course de la liste
      - numérique → index positionnel (0-based) dans `races`
      - sinon → code course tel quel
    """
    if not race:
        if not races:
            raise ValueError("Aucune course disponible pour cet événement.")
        return races[0].get("race", "")
    if race.isdigit():
        idx = int(race)
        if not 0 <= idx < len(races):
            raise ValueError(
                f"Index de course {idx} hors limites ({len(races)} courses)."
            )
        return races[idx].get("race", "")
    return race


def _derive_status(athlete: dict) -> str:
    """Statut sportif d'un athlète prolivesport, lu des champs distincts de l'API.

    Le champ `dns` est ignoré car non fiable (`dns="O"` est posé sur des
    finishers) ; on déduit DNS de l'absence de temps réel.
    """
    if (athlete.get("dsq") or "").strip().upper() == "O":
        return STATUS_DSQ
    if (athlete.get("dnf") or "").strip().upper() == "O":
        return STATUS_DNF
    t = (athlete.get("time") or "").strip()
    if t and t != "00:00:00":
        return STATUS_FINISHER
    return STATUS_DNS


def _fetch_races(event_id: str, client: httpx.Client) -> list[str]:
    """Codes de course de l'événement, dans l'ordre du `raceList`."""
    r = client.get(f"{API_BASE}/result/raceList/{event_id}/", timeout=15)
    r.raise_for_status()
    return [
        code
        for entree in r.json().get("result", [])
        if (code := (entree.get("race") or "").strip())
    ]


def _lignes_par_course(
    event_id: str,
    a_scraper: list[tuple[str, str]],
    courses: list[str],
    client: httpx.Client,
    trace: FanoutTrace,
    on_heat_start: Callable[[str, str, int, int], None] | None,
) -> dict[str, list[dict]]:
    """Lignes de chaque course à scraper, regroupées sur leur champ `race`.

    Deux règles, tirées du sondage :

    - **Le regroupement est côté client, toujours.** Une ligne appartient à la
      course que son champ `race` désigne, jamais à celle qu'on a demandée.
    - **Une réponse qui déborde de la course demandée est l'événement entier**
      (comportement mesuré de la source) : elle est réutilisée pour toutes les
      autres courses, plutôt que de redemander N fois 14,7 Mo.

    `on_heat_start` est notifié pour **chaque** course à scraper, y compris celles
    servies par une réponse déjà en main : la progression compte les courses
    importées, pas les requêtes émises. Un échec est isolé sur sa course.
    """
    attendues = {race for race, _ in a_scraper}
    lignes: dict[str, list[dict]] = {}
    couvertes: set[str] = set()
    total = len(a_scraper)

    for index, (race, _sub_url) in enumerate(a_scraper, start=1):
        if on_heat_start is not None:
            on_heat_start(race, race, index, total)
        if race in couvertes:
            continue
        try:
            reponse = _fetch_indiv(event_id, race, client)
        except Exception as exc:
            logger.warning(
                "Course prolivesport %s de l'événement %s en échec : %s",
                race, event_id, exc,
            )
            trace.failures.append({"heat_slug": race, "reason": str(exc)})
            continue

        vues: set[str] = set()
        for ligne in reponse:
            code = (ligne.get("race") or "").strip()
            vues.add(code)
            if code in attendues:
                lignes.setdefault(code, []).append(ligne)
        couvertes.update(courses if vues - {race} else {race})

    # Une course peut avoir échoué puis avoir été rattrapée par une réponse
    # « événement entier » plus tardive : la laisser dans `failures` alors que ses
    # participations sont importées casserait l'invariant
    # `enumerated = imported + cached + len(failures)` dont `import_service`
    # déduit `heats_imported`.
    trace.failures = [
        echec for echec in trace.failures if echec["heat_slug"] not in lignes
    ]
    return lignes


def scrape_event_fanout(
    url: str,
    *,
    cache_probe: Callable[[str], bool] | None = None,
    on_heat_start: Callable[[str, str, int, int], None] | None = None,
) -> tuple[list[ScrapedResult], FanoutTrace]:
    """Fan-out par **course** de l'événement ProLiveSport — une `Course` par course.

    Le jeton `race` de l'URL est ignoré : le fan-out énumère `raceList`. L'URL
    nue et l'index positionnel (`/result/1082/4`, la 5ᵉ entrée du `raceList` — qui
    change dès que la source réordonne) deviennent donc sans objet.

    Contrat identique au fan-out Klikego (#156) :

    - `cache_probe(sub_url)` — invoqué avant chaque course ; True → course sautée,
      `trace.heats_cached++`, `trace.cached_urls.append(sub_url)`, `on_heat_start`
      **non-notifié**.
    - `on_heat_start(slug, label, index, total)` — `total` est le nombre de
      courses **à scraper**, pas le nombre énuméré, sans quoi la progression
      sauterait des indices sur un ré-import majoritairement caché.
    - échec par course isolé, journalisé et ajouté à `trace.failures` sans
      stopper les autres — indispensable ici, la source rend des 500
      intermittents sur ses gros événements.

    `trace.heats_imported` reste à 0 : dérivé par `import_service`.
    """
    trace = FanoutTrace()
    event_id, _race_token = _parse_url(url)

    with http.client(timeout=_TIMEOUT_INDIV, headers=HEADERS) as client:
        event_name, event_date = _fetch_event_meta(event_id, client)
        courses = _fetch_races(event_id, client)
        trace.heats_enumerated = len(courses)
        if not courses:
            return [], trace

        a_scraper: list[tuple[str, str]] = []
        for race in courses:
            sub_url = _sub_source_url(event_id, race)
            if cache_probe is not None and cache_probe(sub_url):
                trace.heats_cached += 1
                trace.cached_urls.append(sub_url)
                continue
            a_scraper.append((race, sub_url))

        if not a_scraper:
            return [], trace

        lignes = _lignes_par_course(
            event_id, a_scraper, courses, client, trace, on_heat_start
        )
        splits = _fetch_splits(event_id, client)

    resultats: list[ScrapedResult] = []
    for race, sub_url in a_scraper:
        plan = _build_split_map(splits, race)
        event_type = classify_event_type(race)
        nom = qualify_event_name(event_name, race)
        resultats.extend(
            _parse_athlete(ligne, plan, sub_url, nom, event_type, event_date)
            for ligne in lignes.get(race, [])
        )
    return resultats, trace


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Une seule course, celle que l'URL désigne — échappatoire `--single-heat`.

    Filtre les lignes sur leur champ `race` comme le fan-out : sans ce filtre,
    l'échappatoire reconstruirait le fourre-tout que #269 corrige (815 lignes
    dans un « Triathlon M » qui n'en compte que 336).
    """
    event_id, race_token = _parse_url(url)

    with http.client(timeout=_TIMEOUT_INDIV, headers=HEADERS) as client:
        event_name, event_date = _fetch_event_meta(event_id, client)
        r = client.get(f"{API_BASE}/result/raceList/{event_id}/", timeout=15)
        races = r.json().get("result", [])
        race = _resolve_race(race_token, races)
        if not race:
            raise ValueError(
                f"Aucune épreuve trouvée pour l'événement prolivesport {event_id}."
            )

        athletes = _fetch_indiv(event_id, race, client)
        plan = _build_split_map(_fetch_splits(event_id, client), race)

    event_type = classify_event_type(race)
    nom = qualify_event_name(event_name, race)
    return [
        _parse_athlete(a, plan, url, nom, event_type, event_date)
        for a in athletes
        if (a.get("race") or "").strip() == race
    ]
