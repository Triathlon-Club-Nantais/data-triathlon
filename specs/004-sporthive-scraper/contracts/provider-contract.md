# Contrat du provider `sporthive`

Le module n'expose aucune interface HTTP ni CLI nouvelle. Son seul contrat est
`registry.ScraperProtocol`, et les invariants que les tests verrouillent.

## Interface

```python
class SporthiveProvider(HostMatchedProvider):
    name = "sporthive"
    _HOSTS = ("sporthive.com",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]: ...
```

`matches()` est **hérité** : la condition se réduit à une liste de hosts, donc
`HostMatchedProvider` suffit et la règle « host exact ou vrai sous-domaine »
reste définie une seule fois dans `registry._host_match` (garde SSRF de #49).
L'entrée unique `sporthive.com` couvre `results.sporthive.com` par sous-domaine.

Position dans `PROVIDERS` : indifférente — aucun autre provider ne revendique
`sporthive.com`. On l'ajoute avant `T2AreaProvider` pour garder le fallback
Playwright en dernier.

## Endpoints consommés

Base : `https://eventresults-api.speedhive.com/sporthive`

| Appel | Fréquence par import | Rôle |
| --- | --- | --- |
| `GET /events/{eventId}` | 1 | nom, date, type, lieu |
| `GET /events/{eventId}/races` | 1 | liste des courses + `classificationsCount` |
| `GET /races/{raceId}/participants?page=N&size=10` | ⌈classés / 10⌉ par course | le classement |

Coût mesuré : ≈ 100 requêtes pour l'épreuve du Sheet (955 classés, 6 courses).

## Invariants vérifiés par les tests

### Détection

| Entrée | Attendu |
| --- | --- |
| `https://results.sporthive.com/events/7237011278055708416/races/1/bib/426` | détecté `sporthive` |
| `https://sporthive.com/events/s/7237011278055708416/races/1` | détecté `sporthive` |
| `https://evil-sporthive.com/events/1` | **non** détecté (non-régression SSRF #49) |
| `https://exemple.fr/?x=sporthive.com` | **non** détecté (jeton en query) |
| `https://timepulse.fr@results.sporthive.com/events/1` | détecté sur le host réel, jamais sur les credentials |
| `https://[oops/x` | non-match, **sans exception** |
| `https://eventresults-api.speedhive.com/sporthive/events/1` | **non** détecté (l'hôte d'API n'est pas un hôte de détection) |

### Lecture d'URL

| Entrée | `event_id` extrait |
| --- | --- |
| `/events/7237011278055708416` | `7237011278055708416` |
| `/events/7237011278055708416/races/1` | `7237011278055708416` |
| `/events/7237011278055708416/races/1/bib/426` | `7237011278055708416` |
| `/events/7237011278055708416/races/1/bib/426/split` | `7237011278055708416` |
| `/events/s/7237011278055708416/races/1` | `7237011278055708416` |
| `/en/events/7237011278055708416/races/1` | `7237011278055708416` |
| `/events/abc` | `ValueError` nommant la forme attendue |
| `/` ou `/profile` | `ValueError` nommant la forme attendue |

**Invariant structurant** : le segment `races/{n}` n'est **jamais** transmis à
l'API comme identifiant de course. Un test de non-régression le verrouille — sur
la source réelle, `GET /races/1` répond 200 et rend une épreuve de 2015 sans
rapport.

### Scraping

| Cas | Attendu |
| --- | --- |
| Événement à 6 courses | 6 `Course` distinctes, chacune qualifiée par son intitulé |
| Course de 366 classés | 366 `ScrapedResult`, en 37 requêtes |
| Dernière page partielle (`last: true`) | aucune requête au-delà |
| Page intermédiaire servie vide alors que `classificationsCount` n'est pas atteint | `ValueError` — l'épreuve n'est pas importée tronquée |
| `classificationsCount` dépassé (course en cours) | import accepté, surplus journalisé |
| `_MAX_PAGES` atteint | `ValueError` |
| Événement inconnu (404) | `ValueError` « événement introuvable » |
| Erreur 5xx de la source | remonte telle quelle (ce n'est pas un problème de lien) |

### Mapping des participations

| Cas | Attendu |
| --- | --- |
| `validity: "DNF"` / `"DNS"` / `"DQ"` | `status` = `DNF` / `DNS` / `DSQ` |
| `validity` absent, temps présent | `status` = `""` → `finisher` par l'heuristique |
| `dns: false, dsq: false` avec `validity: "DNS"` | `status` = `DNS` — les booléens ne sont jamais lus |
| `chipTimeOfParticipant: "00:57:33.2510000"` | `total_time` = `"00:57:33"` |
| `chipTimeOfParticipant: "00:00:00"` | `total_time` = `""` |
| `chipTime` absent, `gunTime` présent | `total_time` = le gun normalisé |
| Ni chip ni gun | `total_time` = `""` |
| `overallPosition: 0` | `rank_overall` = `None` |
| `gender: "U"` | `gender` = `""` |
| 5 legs (triathlon) | 5 segments, deux `transition` désambiguïsées |
| 4 legs (course d'enfants) | 4 segments, `course à pied` en dernier — jamais en `t2` |
| 1 leg `Running`, `sportName: null` | 1 segment `course à pied` |
| Leg fantôme (`00:00:00`, split `Start`) | aucun segment |
| Course « Relais Triathlon S » | `is_relay=True`, nom d'équipe entier en `athlete_name`, prénom vide |
| `teamName: "TRI CLUB NANTAIS"` | `club` renseigné, reconnu par `core.club.is_tcn` |
| `teamName: null` | `club` = `""` |

### Classification

| `raceName` | `eventName` | `eventType` | `event_type` attendu |
| --- | --- | --- | --- |
| `Triathlon S` | `Triathlon Sud Vendee Dimanche` | `Triathlon` | `triathlon-s` |
| `Triathlon M` | idem | `Triathlon` | `triathlon-m` |
| `6-9 Ans` | idem | `Triathlon` | `triathlon` |
| `Senior Men` | `UK CAU Inter Counties Cross Country Championships` | `Running` | `course-a-pied` — **jamais** `triathlon` |
| `Trail 10K` | `Oeiras Trail` | `Running` | `trail` |

### Intégration

| Cas | Attendu |
| --- | --- |
| `registry.detect_provider(url)` | `"sporthive"` |
| `registry.is_supported(url)` | `True` |
| `registry.provider_names()` | contient `"sporthive"` |
| `GET /api/v1/scrape/detect?url=…` | `{"provider": "sporthive", "supported": true}` |
| `sheet_source` | le lien n'est plus compté dans `ignored_by_host` |
