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
import logging
import re
from urllib.parse import urlparse

import httpx

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


def scrape_event_all(url: str) -> list:
    """Importe tous les participants d'une épreuve RaceResult."""
    raise NotImplementedError  # complété en Task 6
