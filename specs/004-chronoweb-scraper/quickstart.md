# Quickstart — vérifier le scraper chronoweb

Toutes les commandes se lancent depuis `backend/`.

## Tests

```bash
uv run pytest tests/test_chronoweb.py -q          # unitaires, sans réseau
uv run pytest -m "not integration" -q             # non-régression complète
uv run pytest -m integration -k chronoweb -q      # réseau réel (Oléron 2024)
uv run ruff check .
```

## Détection du fournisseur

```bash
uv run python -c "
from app.scrapers.registry import detect_provider, is_supported
u='https://chronoweb.com/resultats_evenement.php?event=323&epreuve=1147'
print(detect_provider(u), is_supported(u))"
# → chronoweb True
```

## Scrape réel, sans écrire en base

```bash
uv run python -c "
from app.scrapers import chronoweb
r = chronoweb.scrape_event_all('https://chronoweb.com/resultats_evenement.php?event=323&epreuve=1147')
print(len(r), 'participations')
print(sorted({x.event_name for x in r}))
x = next(i for i in r if i.bib_number == '360')
print(x.athlete_name, x.athlete_firstname, x.total_time, x.rank_overall, x.rank_category)
print(x.swim_time, x.t1_time, x.bike_time, x.t2_time, x.run_time)
print(x.raw_data.get('city'))"
```

Attendu (valeurs publiées par le site, relevées au sondage) :

```
854 participations
["Triathlon d'Oléron 2024 - Triathlon M", "… - Triathlon S", "… - Triathlon XS"]
MARIN Thomas 02:13:26 1 1
00:24:24 00:07:01 01:00:09 00:02:26 00:39:26
St Georges d'Oléron
```

## Import complet en base de dev

```bash
uv run python -m app.cli rescrape-db \
  --url 'https://chronoweb.com/resultats_evenement.php?event=323&epreuve=1147'
```

Contrôles attendus dans le bilan : 1 épreuve ciblée, 0 en erreur, 854
participants ajoutés au premier passage, 0 ajouté et 854 déjà en base au second.

## Formes d'URL à vérifier à la main

| URL | Attendu |
| --- | --- |
| `resultats_evenement.php?event=323&epreuve=1148&cat=all&point=10` | import identique à celui de `epreuve=1147` |
| `resultats_participant.php?event=347&epreuve=1234&bib=599` | importe l'événement 347 en entier (4 épreuves) |
| `files/pdf/Resultats_Triathlon_dOlron_2025.zip` | erreur nommant la forme attendue |
| `resultats_evenement.php?event=99999` | erreur « événement introuvable » |
| `resultats_evenement.php?event=146` | 0 participant, sans erreur |
