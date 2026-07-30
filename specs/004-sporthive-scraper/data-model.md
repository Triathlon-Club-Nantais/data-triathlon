# Phase 1 — Data model : scraper MYLAPS Sporthive

**Feature**: 004-sporthive-scraper | **Date**: 2026-07-29

**Aucune migration Alembic.** Cette feature n'ajoute ni table ni colonne : elle
alimente le modèle existant (`Athlete`, `Course`, `Participation`) via
`ScrapedResult`, comme tout autre fournisseur.

## Entités de la source (non persistées telles quelles)

```
Event  1 ── n  Race  1 ── n  Participant  1 ── n  Leg  1 ── n  ParticipantSplit
                                                        (non lu, cf. D7)
```

| Entité source | Devient | Clé de lecture |
| --- | --- | --- |
| `Event` | rien — se décompose en `Course` | `eventId` du chemin d'URL |
| `Race` | une `Course` | `id` (snowflake), **jamais** `activeRaceId` |
| `Participant` | une `Participation` + un `Athlete` | `bib` dans sa course |
| `Leg` | une entrée de `ScrapedResult.segments` | position dans `legs` |

## Correspondance champ à champ

### Métadonnées d'épreuve — `GET /events/{eventId}` et `/events/{eventId}/races`

| `ScrapedResult` | Source | Transformation |
| --- | --- | --- |
| `event_name` | `event.eventName` + `race.raceName` | `qualify_event_name(eventName, raceName)` — sans quoi les 6 courses d'un même événement fusionnent en une `Course` et leurs dossards entrent en collision (#21) |
| `event_date` | `event.date` | `datetime.fromisoformat(...).date()` — ISO `2024-09-22T00:00:00`, aucun parsing FR |
| `event_type` | `race.raceName`, `event.eventName`, `event.eventType` | `classify_event_type(raceName, contexte=f"{eventName} {eventType}")` — cf. D9 |
| `distance_km` | `race.distanceInMeter` | `/ 1000`, `0` → `None` |
| `provider` | — | `"sporthive"` |
| `source_url` | — | l'URL **demandée**, jamais reconstruite : c'est la clé de cache TTL |
| `is_relay` | `race.raceName` | motif d'intitulé, cf. D10 |

### Participation — `GET /races/{raceId}/participants`

| `ScrapedResult` | Source | Transformation |
| --- | --- | --- |
| `athlete_name` / `athlete_firstname` | `name` | `split_athlete_name`, **sauf** course de relais → nom entier, prénom vide (D11) |
| `bib_number` | `bib` | `str(...).strip()` |
| `club` | `teamName` | tel quel, `None` → `""` (absent sur 56 % des lignes) |
| `category` | `raceCategory` | tel quel |
| `gender` | `gender` | `M`/`F` retenus, `U` → `""` (D12) |
| `total_time` | `chipTimeOfParticipant`, repli `gunTimeOfParticipant` | `_time()` : fraction tronquée, `00:00:00` → `""` (D6) |
| `rank_overall` | `overallPosition` | `_rank()` : `0` → `None` (D12) |
| `rank_category` | `categoryPosition` | `_rank()` |
| `rank_gender` | `genderPosition` | `_rank()` |
| `status` | `validity` | `derive_status_from_label` — `DNF`/`DNS`/`DQ`. Absent **et** sans temps : tranché sur le rang, `finisher` si classé, `DNF` sinon (D5) |
| `segments` | `legs[].type` + `legs[].legDuration` | table fermée de libellés, segments vides écartés (D7, D8) |
| `raw_data` | la charge du participant + contexte de course | diagnostic sans re-scrape |
| `raw_data["city"]` | `event.location` | verbatim (`L'Aiguillon sur Mer (85)`), même clé que runnerbreizh — non branché sur le géocodage (D15) |
| `raw_data["country"]` | `event.countryCode` | tel quel, codes non homogènes assumés (D15) |

**Champs de la source volontairement non lus** : `dns` et `dsq` (toujours
`false`, D5), `tags` (index de recherche, D11), `participantSplits` (D7),
`activeLocation` (toujours à 0.0/0.0), `pk`, `apid`, `vid`, `teamContribute`,
`numberOfParticipantsInCategory`, `genderPositionCount`, `personalSplitSpeed` et
les vitesses. Tous restent accessibles dans `raw_data`.

## Règles de validation

| Règle | Portée | Effet si violée |
| --- | --- | --- |
| L'URL livre un identifiant d'événement | avant toute requête | `ValueError` nommant la forme attendue (FR-003) |
| L'événement existe | `GET /events/{id}` → 404 | `ValueError` « événement introuvable » (FR-003) |
| Le classement est complet | `lus >= race.classificationsCount` | **cette course seule** est écartée et journalisée (`logger.warning` : intitulé, `activeRaceId`, les deux décomptes) ; les autres courses de l'événement sont importées (FR-008, FR-008a) |
| La course a des classés | `race.classificationsCount` non nul | course ignorée **sans requête de participants**, `logger.info` ; aucune `Course` vide créée (FR-008b) |
| Au moins une course importée | `results` non vide en fin de `scrape_event_all` | `ValueError` en français : un import à zéro course n'est jamais un succès (FR-008c) |
| La pagination termine | `page < _MAX_PAGES` | `ValueError` — portée **événement**, l'invariant d'arrêt étant faux (FR-009) |
| Une durée nulle vaut absence | `_time()` | `""`, jamais `"00:00:00"` (FR-013) |
| Un rang nul vaut absence | `_rank()` | `None`, jamais `0` (FR-015) |

**Deux portées d'échec, pas une** : l'écart d'une course (`_IncompleteRanking`,
type privé du module, rattrapé par la boucle) et le refus de l'événement
(`ValueError`, propagée jusqu'à `import_service`). Le tri se fait sur le **type**
d'exception, jamais sur son message — cf. D4.

## Ce que produit un import

Pour l'URL du Sheet
(`results.sporthive.com/events/7237011278055708416/races/1/bib/426`) :

| `Course` créée | `event_type` | `distance_km` | Participations |
| --- | --- | --- | ---: |
| Triathlon Sud Vendee Dimanche - Triathlon S | `triathlon-s` | 25.75 | 366 |
| Triathlon Sud Vendee Dimanche - Relais Triathlon S | `triathlon-s` | 25.75 | 29 |
| Triathlon Sud Vendee Dimanche - 6-9 Ans | `triathlon` | 3.1 | 47 |
| Triathlon Sud Vendee Dimanche - 10-13 Ans | `triathlon` | 6.2 | 103 |
| Triathlon Sud Vendee Dimanche - Triathlon M | `triathlon-m` | 42.7 | 382 |
| Triathlon Sud Vendee Dimanche - Relais Triathlon M | `triathlon-m` | 42.7 | 28 |

Valeurs vérifiées en exécutant `classify_event_type` et la conversion de
distance sur les métadonnées réelles des 6 courses. `distanceInMeter` est
renseigné sur toutes : le repli de `mapping.get_or_create_course` sur
l'extraction depuis le nom n'a jamais à s'appliquer.

Dont **29 participations « TRI CLUB NANTAIS »**, reconnues par `core.club.is_tcn`
sans ajout de libellé.

Splits d'un participant de « Triathlon S » :

```json
{ "natation": "00:09:46", "transition": "00:01:32", "vélo": "00:27:43",
  "transition (2)": "00:01:14", "course à pied": "00:17:21" }
```

Splits d'un participant de « 6-9 Ans » (4 legs, une seule transition) :

```json
{ "natation": "00:03:12", "transition": "00:00:48", "vélo": "00:07:05",
  "course à pied": "00:04:33" }
```
