"""
Moteur RaceResult générique — issue #50.

Couvre trois façades d'un même produit, toutes alimentées par la même API JSON
publique (aucun Playwright, la page RRPublish est un SPA qui n'apporte rien de
plus) :

  - `my*.raceresult.com`      — RaceResult direct, l'eventId est dans le path ;
  - `espace-competition.com`  — front RaceResult, `new RRPublish(el, <id>, …)` ;
  - `chronoconsult.fr`        — façade WordPress au-dessus de RaceResult.

Chaînage d'appels (établi par sondage réel le 2026-07-18) :
  1. GET /{eventId}/RRPublish/data/config?page=results
  2. GET /{eventId}/RRPublish/data/list?key=…&listname=…&contest=N&r=all
     → **301** vers /{eventId}/results/list : `follow_redirects=True` obligatoire.
  3. La date d'épreuve n'est dans aucun des deux : elle vit dans le JSON-LD
     schema.org de la page /{eventId}/results.
"""
import json
import logging
import re
from datetime import date as date_t
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
}

# Racine par défaut quand l'URL d'entrée est une façade tierce : toutes les
# façades sondées pointent leurs assets vers my.raceresult.com.
_API_DEFAUT = "https://my.raceresult.com"

# `RRPublish(document.getElementById("divRRPublish"),  399938 , 'results')` — les
# espaces autour de l'argument sont fréquents et doivent être tolérés.
_RE_RRPUBLISH = re.compile(r"RRPublish\s*\([^,]+,\s*(\d+)\s*,")
# Repli : le logo de l'épreuve est servi par l'API et porte le même id.
_RE_LOGO = re.compile(r"raceresult\.com/(\d+)/api/logo")


def _api_base(url: str) -> str:
    """Racine HTTPS de l'API RaceResult à interroger pour cette URL.

    Un host `my*.raceresult.com` est déjà la bonne racine (les épreuves sont
    réparties sur plusieurs serveurs : my, my2, my3…). Toute autre façade est
    servie depuis la racine par défaut.
    """
    host = (urlparse(url).netloc or "").lower()
    if host == "raceresult.com" or host.endswith(".raceresult.com"):
        return f"https://{host}"
    return _API_DEFAUT


def _resolve_event_id(url: str, client: httpx.Client) -> str:
    """Identifiant d'épreuve RaceResult désigné par l'URL.

    Sur un host RaceResult, c'est le premier segment numérique du path — zéro
    requête. Sur une façade, une seule page est téléchargée : l'id se lit dans
    l'appel `new RRPublish(...)`, avec repli sur l'URL du logo. Le `comp_uid` des
    URLs `espace-competition.com` est délibérément ignoré : c'est un identifiant
    interne au front, pas la clé de données.
    """
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if host == "raceresult.com" or host.endswith(".raceresult.com"):
        for segment in parsed.path.strip("/").split("/"):
            if segment.isdigit():
                return segment
        raise ValueError(f"Aucun identifiant d'épreuve dans l'URL RaceResult : {url}")

    resp = client.get(url, headers=HEADERS)
    resp.raise_for_status()
    for motif in (_RE_RRPUBLISH, _RE_LOGO):
        trouve = motif.search(resp.text)
        if trouve:
            return trouve.group(1)
    raise ValueError(
        f"Identifiant d'épreuve RaceResult introuvable dans la page : {url}"
    )


def _json_ld_event(html: str) -> dict:
    """Premier bloc JSON-LD de type Event de la page, `{}` si aucun.

    Le bloc peut être un objet seul, une liste d'objets, ou un `@graph` — on
    balaie les trois formes plutôt que de parier sur une seule.
    """
    soup = BeautifulSoup(html, "lxml")
    for balise in soup.find_all("script", type="application/ld+json"):
        try:
            charge = json.loads(balise.string or "")
        except (ValueError, TypeError):
            continue
        candidats = charge if isinstance(charge, list) else [charge]
        if isinstance(charge, dict) and isinstance(charge.get("@graph"), list):
            candidats = charge["@graph"]
        for noeud in candidats:
            if isinstance(noeud, dict) and noeud.get("@type") == "Event":
                return noeud
    return {}


def _fetch_meta(
    event_id: str, base: str, client: httpx.Client
) -> tuple[str, "date_t | None", str]:
    """(nom d'épreuve, date, ville) depuis le JSON-LD de la page /results.

    C'est la **seule** source de la date : l'API `config` comme l'API `list` n'en
    portent aucune. Une page sans JSON-LD exploitable renvoie des valeurs vides
    plutôt que de lever : l'épreuve reste importable, le nom retombera sur
    `config["eventname"]` et la date sur `None`.
    """
    try:
        resp = client.get(f"{base}/{event_id}/results", headers=HEADERS)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("RaceResult %s : page /results illisible (%s)", event_id, exc)
        return "", None, ""

    noeud = _json_ld_event(resp.text)
    if not noeud:
        return "", None, ""

    jour = None
    brut = str(noeud.get("startDate") or "")
    if brut:
        try:
            jour = date_t.fromisoformat(brut[:10])
        except ValueError:
            logger.warning("RaceResult %s : startDate illisible (%r)", event_id, brut)

    adresse = (noeud.get("location") or {}).get("address") or {}
    ville = str(adresse.get("addressLocality") or "")
    return str(noeud.get("name") or ""), jour, ville


def _fetch_config(event_id: str, base: str, client: httpx.Client) -> dict:
    """Config publique de l'épreuve : `key`, `contests`, `lists`, `splits`."""
    resp = client.get(
        f"{base}/{event_id}/RRPublish/data/config",
        params={"page": "results"},
        headers=HEADERS,
    )
    resp.raise_for_status()
    return resp.json()


# Clés qui marquent une feuille dans l'arbre `lists` (une liste réelle, pas un
# groupe intermédiaire).
_CLES_FEUILLE = ("Contest", "Name", "ID")


def _iter_list_specs(config: dict) -> list[tuple[str, str]]:
    """Listes exploitables : [(listname, indice de contest), …].

    `config["lists"]` est un arbre dont le chemin, joint par `|`, forme le
    `listname` attendu par l'API. On aplatit récursivement : une feuille est un
    nœud non-dict, ou un dict portant une clé de description (`Contest`,
    `Name`, `ID`). L'indice de contest n'est qu'un **indice** — il est vérifié
    empiriquement à l'appel (cf. `_contest_candidates`).
    """
    specs: list[tuple[str, str]] = []

    def descendre(noeud, chemin: list[str]) -> None:
        if not isinstance(noeud, dict) or any(c in noeud for c in _CLES_FEUILLE):
            indice = noeud.get("Contest") if isinstance(noeud, dict) else None
            specs.append(("|".join(chemin), "" if indice is None else str(indice)))
            return
        for cle, valeur in noeud.items():
            descendre(valeur, [*chemin, str(cle)])

    for cle, valeur in (config.get("lists") or {}).items():
        descendre(valeur, [str(cle)])
    return specs


def scrape_event_all(url: str) -> list:
    """Importe tous les participants d'une épreuve RaceResult."""
    raise NotImplementedError  # complété en Task 6
