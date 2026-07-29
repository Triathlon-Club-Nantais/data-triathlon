# Quickstart — vérifier le scraper Sporthive

**Feature**: 004-sporthive-scraper

## Tests unitaires (sans réseau, le défaut)

```bash
cd backend
uv run pytest tests/test_sporthive.py -v          # le nouveau module
uv run pytest -m "not integration"                # la suite complète
uv run ruff check .
```

## Test d'intégration (réseau réel)

```bash
cd backend
uv run pytest -m integration -k sporthive -v
```

Il vérifie que le schéma de l'API n'a pas bougé depuis le sondage du 29/07/2026.
Il est le premier à casser si MYLAPS déplace à nouveau son API — c'est son rôle.

## Import de bout en bout

```bash
cd backend
uv run python -m app.cli rescrape-db \
  --url "https://results.sporthive.com/events/7237011278055708416/races/1/bib/426"
```

Attendu : **6 épreuves ciblées, 955 participants ajoutés**, aucune erreur.
Compter ≈ 100 requêtes HTTP, soit une trentaine de secondes.

Vérifier la détection seule, sans importer :

```bash
curl -s "http://127.0.0.1:8001/api/v1/scrape/detect?url=https://results.sporthive.com/events/7237011278055708416/races/1"
# {"provider":"sporthive","supported":true}
```

Vérifier que les membres du club sont bien reconnus :

```bash
cd backend && uv run python -m app.cli club-labels --like nantais
# « TRI CLUB NANTAIS » doit apparaître marqué TCN (29 participations)
```

## Sonder l'API à la main

```bash
API=https://eventresults-api.speedhive.com/sporthive
EV=7237011278055708416

curl -s "$API/events/$EV" | jq '{eventName, date, eventType, location}'
curl -s "$API/events/$EV/races" | jq '.[] | {activeRaceId, raceName, classificationsCount}'
curl -s "$API/races/7242234087144997120/participants?page=0&size=10" \
  | jq '{totalElements, last, premier: .content[0] | {name, bib, chipTimeOfParticipant, validity}}'
```

> `size` au-delà de 10 renvoie 400. `count`/`offset` sont ignorés
> silencieusement — ne pas s'en servir pour vérifier quoi que ce soit.

Si l'API paraît injoignable, relire d'abord la configuration servie par le site,
qui est la source de vérité de l'adresse :

```bash
curl -s https://sporthive.com/api/clientSettings | jq .eventResultApiUrl
```

## Points de contrôle manuels

1. Une course d'enfants (`activeRaceId` 3 ou 4) a bien **4 splits** dont
   `course à pied` en dernier.
2. Un participant `validity: "DNF"` a un statut `DNF`, **aucun** split, et pas
   de temps total.
3. Les deux transitions d'un triathlon apparaissent comme `transition` et
   `transition (2)`.
4. Les 6 courses de l'événement sont des épreuves distinctes, et le dossard 117
   de « Triathlon S » ne collisionne pas avec le 117 de « Triathlon M ».
