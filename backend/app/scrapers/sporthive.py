"""
Scraper MYLAPS Sporthive — API JSON publique (issue #53).

L'API vit sur `eventresults-api.speedhive.com/sporthive` : MYLAPS a fondu
Sporthive dans Speedhive, l'ancien host `eventresults-api.sporthive.com` ne
répond plus (certificat TLS qui ne couvre plus le nom). Aucune clé, aucun
cookie : chemin nominal en `GET`, pas de Playwright.

Cinq pièges structurants de la source, à ne jamais réintroduire (cf.
docs/superpowers/specs/2026-07-29-sporthive-sondage.md, source de vérité — elle
prime sur le design et sur le plan) :

  1. `races/{n}` dans l'URL du Sheet est un **ordinal local**
     (`activeRaceId`), pas le `raceId`. `GET /races/1` répond **200** et rend
     une épreuve de 2015 sans rapport : le vrai `raceId` est le champ `id`
     (snowflake 19 chiffres) de `/events/{eventId}/races`.
  2. `size` est plafonné à 10 côté serveur (`size=50` → 400). `count` et
     `offset` sont acceptés mais silencieusement ignorés : on croirait paginer
     par 50 en relisant toujours les 10 mêmes lignes.
  3. Le statut vit dans `validity` (`DNF` / `DNS` / `DQ`) ; les booléens `dns`
     et `dsq` valent `false` sur 10 360 lignes mesurées / 10 360.
  4. `legs[].sportName` n'est pas normalisé et vaut `null` sur 23 % des legs :
     `legs[].type` est le seul discriminant fiable (`Swimming`, `Cycling`,
     `Running`, `Transition`).
  5. `tags` est un index de recherche, pas un découpage nom / prénom.

Endpoints consommés (cf. specs/004-sporthive-scraper/contracts/provider-contract.md) :

    GET /events/{eventId}
    GET /events/{eventId}/races
    GET /races/{raceId}/participants?page=N&size=10

Ce module ne pose ici que son squelette (T001, Phase 1 de
specs/004-sporthive-scraper/tasks.md) : `scrape_event_all` lève
`NotImplementedError`. Les lots suivants l'implémentent une brique à la fois —
lecture d'URL, détection au registre, client paginé, garde de complétude,
mapping des scalaires, segments, métadonnées, puis assemblage.
"""
import logging

from .base import ScrapedResult

logger = logging.getLogger(__name__)

_API_BASE = "https://eventresults-api.speedhive.com/sporthive"
# size=50 reçoit un 400 (« The size value cannot be greater than 10 ») côté serveur.
_PAGE_SIZE = 10
# Plafond dur : le pire cas mesuré au panel demande 269 requêtes pour une course.
_MAX_PAGES = 1000


def scrape_event_all(url: str) -> list[ScrapedResult]:
    raise NotImplementedError
