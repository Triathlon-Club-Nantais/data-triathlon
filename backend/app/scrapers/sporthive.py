"""
Scraper MYLAPS Sporthive — API JSON publique (issue #53).

`sporthive.com` est une SPA Vue au HTML vide, mais toutes ses données transitent
par une API publique, sans authentification ni clé, CORS ouvert :

    GET https://eventresults-api.speedhive.com/sporthive/events/{eventId}
    GET https://eventresults-api.speedhive.com/sporthive/events/{eventId}/races
    GET https://eventresults-api.speedhive.com/sporthive/races/{raceId}/participants

Aucun Playwright sur le chemin nominal — il n'a servi qu'à découvrir ces routes.
L'URL annoncée par l'issue #53 (`eventresults-api.sporthive.com/…/classifications/
search?count=50&offset=0`) n'existe plus : le host est en NXDOMAIN.

Flux (cf. docs/superpowers/specs/2026-07-30-sporthive-api-sondage.md) :
  1. `_parse_url`      → identifiant d'événement (snowflake **ou** GUID)
  2. `/events/{id}`    → nom, date, lieu, `eventType` (contexte de classification)
  3. `/events/{id}/races` → les courses de l'événement
  4. `/races/{id}/participants` → le classement, **par pages de 10 au plus**

Comme chez ok-time et Chronoplace, une URL rapporte **l'événement entier** :
l'API n'a pas de route qui rendrait « la course pointée » seule sans redemander
la liste des courses, et les segments `/race/…`, `/bib/…`, `/team/…` de l'URL
sont donc ignorés.
"""
import logging
import re
from datetime import date, datetime
from urllib.parse import urlparse

import httpx

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, STATUS_FINISHER, ScrapedResult
from .classify import classify_event_type
from .utils import normalize_rank, normalize_time, qualify_event_name, split_athlete_name

logger = logging.getLogger(__name__)

BASE_URL = "https://eventresults-api.speedhive.com/sporthive"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

#: Plafond **imposé par l'API** : `size=11` est refusé en 400 (« The size value
#: cannot be greater than 10 »). Aucun export en masse n'existe (csv, export,
#: classifications → 404), donc une requête par tranche de 10 participants.
PAGE_SIZE = 10

#: Garde-fou : au-delà, l'invariant d'arrêt (`last`, `totalPages`) est faux et
#: on préfère lever plutôt que boucler. 2000 pages = 20 000 participants, soit
#: davantage que la plus grosse course du panel (17 088 au marathon de Rotterdam).
_MAX_PAGES = 2000

# `/events/s/{id}` : la forme canonique de l'endurance. L'identifiant est pris
# tel quel — snowflake (`7191895923677191680`) **et** GUID
# (`bdea2f10-1510-481c-b5ef-ef7f1926a06f`) sont vivants et servis par les mêmes
# routes. Exiger `\d+` refuserait tout le fonds récent.
_PATH_SPORTHIVE_RE = re.compile(r"^/events/s/(?P<id>[^/]+)(?:/.*)?$")
# `/events/{id}` : la façade `results.sporthive.com` (307 vers la forme ci-dessus)
# — mais aussi, sur `sporthive.com`, une épreuve **motorisée** Speedhive.
_PATH_NU_RE = re.compile(r"^/events/(?P<id>[^/]+)(?:/.*)?$")

#: Les 5 slots positionnels de `ScrapedResult`, dans l'ordre de course. Le
#: nommage est conventionnel : `services/mapping.build_splits` les ré-étiquette
#: ensuite selon `event_type` (duathlon → `course1`/`course2`).
_SLOT_FIELDS = ("swim_time", "t1_time", "bike_time", "t2_time", "run_time")

#: `validity` de la source → constante de statut. `DQ`, et non `DSQ` : c'est le
#: libellé publié. Un libellé absent de cette table rend "" (l'infra applique
#: son heuristique) plutôt qu'un statut inventé.
_VALIDITY = {"DQ": STATUS_DSQ, "DNF": STATUS_DNF, "DNS": STATUS_DNS}

_RELAY_TOKENS = ("relais", "relay", "estafette")


def _parse_url(url: str) -> str:
    """Identifiant de l'événement désigné par `url`.

    Les segments plus profonds (`/race/…`, `/bib/…`, `/team/…`, et l'index
    `/races/3` de l'ancienne façade) sont **ignorés** : l'import porte sur
    l'événement entier. L'index de course de `results.sporthive.com` n'est de
    toute façon pas un identifiant d'API.
    """
    parsed = urlparse(url)
    path = (parsed.path or "/").rstrip("/") or "/"
    host = (parsed.hostname or "").lower()

    m = _PATH_SPORTHIVE_RE.match(path)
    if m:
        return m.group("id")

    m = _PATH_NU_RE.match(path)
    if m:
        # Sans le `s`, seule l'ancienne façade endurance est légitime : sur
        # `sporthive.com`, `/events/{id}` désigne une épreuve **motorisée**
        # (Speedhive), servie par une autre API. La requêter ici rendrait un 400
        # opaque plutôt qu'un refus lisible.
        if host.startswith("results."):
            return m.group("id")
        raise ValueError(
            f"URL Speedhive (épreuves motorisées), pas Sporthive : {url} — les "
            "résultats d'endurance sont sous /events/s/<id>."
        )

    raise ValueError(f"URL sporthive.com non reconnue : {url}")


def _time(raw: str | None) -> str:
    """Temps normalisé en `HH:MM:SS`, fraction de seconde **tronquée**.

    La source publie trois graphies pour le même champ (`02:04:45`,
    `00:31:34.000`, `00:40:58.7230000`). `normalize_time` ne reconnaît que la
    première et renvoie les autres telles quelles : sans cette troncature
    préalable, `00:40:58.7230000` partirait en base et casserait toute
    comparaison de temps côté front.
    """
    if not raw:
        return ""
    return normalize_time(str(raw).split(".")[0].strip())


def _status(participant: dict) -> str:
    """Statut sportif, lu sur `validity`.

    **Jamais** sur `dns` / `dsq` : ces booléens sont présents sur chaque
    participant et à `false` sur les 1 746 participants sondés, y compris les
    disqualifiés. S'y fier classait finisher la totalité des non-finishers.
    """
    validity = (participant.get("validity") or "").strip().upper()
    if not validity:
        return STATUS_FINISHER
    return _VALIDITY.get(validity, "")


def _named_legs(participant: dict) -> list[dict]:
    """Les legs portant un nom de discipline — donc un segment de multisport.

    Un leg **sans** `sportName` n'est pas une discipline : c'est le conteneur
    unique d'une course mono-sport, dont seul `participantSplits` a du sens.
    """
    return [
        leg for leg in (participant.get("legs") or [])
        if (leg.get("sportName") or "").strip()
    ]


def _slots(participant: dict) -> dict[str, str]:
    """Les segments multisports, rangés **par position** dans les 5 slots.

    Router par libellé serait un piège ici : la casse varie d'une épreuve à
    l'autre (`SWIM`/`Swim`/`swim`), les deux transitions portent parfois le
    **même** libellé (`TRANSITION`), et `type` vaut `Other` jusque sur une
    natation. L'ordre, lui, est constant — natation, T1, vélo, T2, course —
    tronqué à droite quand l'épreuve est plus courte (« Après Natation »).
    """
    # `strict=False` est le fond du sujet, pas une concession au linter : les
    # longueurs diffèrent par construction — une épreuve tronquée a moins de
    # 5 legs, et un multisport exotique pourrait en avoir davantage (au-delà du
    # 5ᵉ, les slots positionnels ne peuvent de toute façon rien porter).
    return {
        field: temps
        for field, leg in zip(_SLOT_FIELDS, _named_legs(participant), strict=False)
        if (temps := _time(leg.get("legDuration")))
    }


def _segments(participant: dict) -> list[tuple[str, str]] | None:
    """Les points de passage d'une course mono-sport, ou `None`.

    Sur une course à pied il n'y a qu'un leg, et son `legDuration` est faux
    (`00:06:33` pour un marathon couru en `02:04:45`) : l'information est dans
    `participantSplits`, dont les `splitName` (`5k`, `21.1k`) sont signifiants
    et uniques — le cas où le chemin générique `segments` a du sens, à l'inverse
    du multisport.
    """
    legs = participant.get("legs") or []
    if len(legs) != 1 or _named_legs(participant):
        return None
    segments = [
        (nom, temps)
        for split in (legs[0].get("participantSplits") or [])
        if (nom := (split.get("splitName") or "").strip())
        and (temps := _time(split.get("splitDuration")))
    ]
    return segments or None


def _event_date(race: dict, event: dict) -> date | None:
    """Date de la course, à défaut celle de l'événement.

    Les deux sont des ISO-8601 sans fuseau (`2024-05-05T00:00:00`).
    """
    for brut in (race.get("date"), event.get("date")):
        if not brut:
            continue
        try:
            return datetime.fromisoformat(str(brut)).date()
        except ValueError:
            logger.warning("Date sporthive illisible : %r", brut)
    return None


def _get(client: httpx.Client, path: str):
    reponse = client.get(f"{BASE_URL}{path}")
    reponse.raise_for_status()
    return reponse.json()


def _iter_pages(client: httpx.Client, race_id: str):
    """Les pages de classement d'une course, jusqu'à la dernière."""
    page = 0
    while page < _MAX_PAGES:
        charge = _get(
            client,
            f"/races/{race_id}/participants"
            f"?size={PAGE_SIZE}&page={page}&useContinuationToken=false",
        )
        contenu = (charge or {}).get("content") or []
        yield contenu
        if not contenu or charge.get("last") or page + 1 >= (charge.get("totalPages") or 0):
            return
        page += 1
    raise ValueError(
        f"Pagination sporthive interrompue après {_MAX_PAGES} pages (course "
        f"{race_id}) : l'invariant d'arrêt est faux, résultats probablement dupliqués."
    )


def _participant_to_result(
    participant: dict, *, race: dict, event: dict, url: str
) -> ScrapedResult:
    race_name = (race.get("raceName") or "").strip()
    event_name = (event.get("eventName") or "").strip()
    nom, prenom = split_athlete_name(participant.get("name") or "")
    est_relais = any(jeton in race_name.lower() for jeton in _RELAY_TOKENS)

    return ScrapedResult(
        source_url=url,
        provider="sporthive",
        athlete_name=nom,
        athlete_firstname=prenom,
        # `teamName` est le club en France, la sélection nationale sur une
        # épreuve internationale : la source ne distingue pas les deux. En
        # relais il est nul, le nom d'équipe étant dans `name`.
        club=(participant.get("teamName") or "").strip(),
        category=(participant.get("raceCategory") or "").strip(),
        gender=(participant.get("gender") or "").strip(),
        bib_number=str(participant.get("bib") or "").strip(),
        event_name=qualify_event_name(event_name, race_name),
        event_date=_event_date(race, event),
        # Le `raceName` classe ; `eventName`/`eventType` ne sont qu'un appoint
        # pour les libellés qui ne nomment aucun sport (« ARRIVEE »). Ne **pas**
        # concaténer les deux : le « Duathlon Jeunes » d'un « Triathlon de X »
        # sortirait en triathlon (piège ok-time).
        event_type=classify_event_type(
            race_name, contexte=f"{event_name} {event.get('eventType') or ''}"
        ),
        # `overallPosition` vaut 0 — et non `null` — chez les non-finishers.
        rank_overall=normalize_rank(participant.get("overallPosition")) or None,
        rank_category=normalize_rank(participant.get("categoryPosition")) or None,
        rank_gender=normalize_rank(participant.get("genderPosition")) or None,
        total_time=_time(
            participant.get("gunTimeOfParticipant")
            or participant.get("chipTimeOfParticipant")
        ),
        distance_km=(race.get("distanceInMeter") or 0) / 1000 or None,
        is_relay=est_relais,
        status=_status(participant),
        segments=_segments(participant),
        raw_data={
            "eventId": str(event.get("id") or ""),
            "raceId": str(race.get("id") or ""),
            "raceName": race_name,
            "validity": participant.get("validity"),
            "chipTime": participant.get("chipTimeOfParticipant"),
            "country": participant.get("country"),
        },
        **_slots(participant),
    )


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Tous les participants de **toutes** les courses de l'événement."""
    event_id = _parse_url(url)
    resultats: list[ScrapedResult] = []

    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        event = _get(client, f"/events/{event_id}")
        races = _get(client, f"/events/{event_id}/races") or []

        # Une course sans classement (course technique, épreuve à venir) n'est
        # pas une anomalie : elle est ignorée sans requête. Mais un événement
        # dont *toutes* les courses sont vides doit se solder par une erreur
        # parlante, pas par un import silencieux à 0 participant.
        classees = [race for race in races if race.get("classificationsCount")]
        if not classees:
            raise ValueError(
                f"Épreuve sporthive sans aucun classement publié : {url} "
                f"({len(races)} course(s) annoncée(s), toutes à 0 participant)."
            )

        for race in classees:
            for page in _iter_pages(client, str(race.get("id"))):
                resultats.extend(
                    _participant_to_result(
                        participant, race=race, event=event, url=url
                    )
                    for participant in page
                )

    logger.info(
        "sporthive : %d participants sur %d course(s) — %s",
        len(resultats), len(classees), event.get("eventName"),
    )
    return resultats
