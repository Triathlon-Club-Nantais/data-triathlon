"""
Scraper ok-time.fr — API JSON WordPress publique (issue #52).

`classement.ok-time.fr` est une SPA React, mais toutes ses données transitent par
une route WordPress publique. **Un seul appel** rend l'événement entier, toutes
épreuves comprises :

    GET https://ok-time.fr/wp-json/gmcap/v1/evenements/{eventId}/results

Ni Playwright ni parsing HTML sur le chemin nominal : le seul GET HTML sert à
lire l'id d'événement quand l'URL est de la forme éditoriale `/evenement/<slug>/`.

Flux (cf. docs/superpowers/specs/2026-07-26-oktime-scraper-design.md) :
  1. `_parse_url`         → id direct, ou slug à résoudre
  2. `_resolve_event_id`  → 1 GET HTML, id lu dans le lien de classement
  3. `_fetch_results`     → l'appel API, erreurs de la source traduites
  4. `_course_results`    → une épreuve de la charge → participants
  5. toutes les épreuves de l'événement sont importées (comme les heats
     Breizh Chrono et les onglets chronoplace)

L'API n'expose aucune route par épreuve : une URL pointant une épreuve rapporte
toujours l'événement entier.
"""
import logging
import re
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://ok-time.fr"
API_PATH = "/wp-json/gmcap/v1/evenements/{event_id}/results"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# `classement.ok-time.fr/<id>` ou `.../<id>/race/<raceId>`. Le segment `race`
# est **ignoré** : l'API ne sait pas filtrer par épreuve, elle rend l'événement.
_ID_PATH_RE = re.compile(r"^/(?P<id>\d+)(?:/race/\d+)?/?$")
# Forme éditoriale actuelle du site.
_SLUG_PATH_RE = re.compile(r"^/evenement/(?P<slug>[^/]+)/?$")
# Formes retirées du site : les 3 URLs mortes du Sheet (§2.1 du design).
_PREFIXES_OBSOLETES = ("/course/", "/competition/")


def _parse_url(url: str) -> tuple[str, str]:
    """(id d'événement, slug) — exactement l'un des deux est non vide.

    Un slug devra être résolu par une requête HTML ; un id part directement à
    l'API. L'id de l'URL de classement **est** le post-id WordPress attendu par
    l'API (vérifié sur les 21 événements du panel) : aucune table de
    correspondance à maintenir.
    """
    path = urlparse(url).path or "/"
    m = _ID_PATH_RE.match(path)
    if m:
        return m.group("id"), ""
    m = _SLUG_PATH_RE.match(path)
    if m:
        return "", m.group("slug")
    if any(path.startswith(prefixe) for prefixe in _PREFIXES_OBSOLETES):
        raise ValueError(
            f"URL ok-time.fr obsolète : {url} — les préfixes /course/ et "
            "/competition/ ont été retirés du site, qui publie sous "
            "/evenement/<slug>/. Lien à corriger à la source."
        )
    raise ValueError(f"URL ok-time.fr non reconnue : {url}")


# Le lien de classement d'une page `/evenement/<slug>/`. Cherché à la regex sur
# le HTML brut plutôt qu'au parseur : le lien peut vivre dans un attribut, un
# bloc de script ou une iframe selon le thème, et un seul motif les couvre tous.
_CLASSEMENT_ID_RE = re.compile(r"classement\.ok-time\.fr/(\d+)")


def _resolve_event_id(client: httpx.Client, slug: str) -> str:
    """Id d'événement lu sur la page éditoriale. 1 GET HTML, aucun autre usage.

    Une page servie mais dépourvue de lien de classement est le cas des slugs
    redirigés vers le listing générique (§2.1 du design) : il n'y a rien à en
    tirer, l'erreur doit le dire.
    """
    url = f"{BASE_URL}/evenement/{slug}/"
    response = client.get(url)
    response.raise_for_status()
    m = _CLASSEMENT_ID_RE.search(response.text)
    if not m:
        raise ValueError(
            f"Page ok-time.fr « {slug} » sans aucun lien de classement : "
            "événement sans résultats publiés, ou slug redirigé vers le listing."
        )
    return m.group(1)


def _fetch_results(client: httpx.Client, event_id: str) -> dict:
    """La charge JSON de l'événement entier. Erreurs de la source traduites.

    L'API distingue ses deux échecs métier (§1.3 du design), on les garde
    distincts : un 404 dit « cet id n'existe pas », un 400 dit « cet événement
    existe mais n'a rien publié ». Toute autre erreur HTTP (5xx…) remonte telle
    quelle : ce n'est pas un problème de lien, et la traduire en ValueError la
    ferait passer pour tel dans le bilan CLI.
    """
    url = f"{BASE_URL}{API_PATH.format(event_id=event_id)}"
    response = client.get(url)
    if response.status_code == 404:
        raise ValueError(
            f"Événement ok-time introuvable (id {event_id}) : seul un id "
            "d'événement est accepté, pas un id d'épreuve."
        )
    if response.status_code == 400:
        raise ValueError(
            f"Événement ok-time {event_id} : aucun résultat publié à ce jour."
        )
    response.raise_for_status()
    charge = response.json()
    if not isinstance(charge, dict) or "data" not in charge:
        raise ValueError(
            f"Charge ok-time inattendue pour l'événement {event_id} : "
            "clé « data » absente."
        )
    return charge
