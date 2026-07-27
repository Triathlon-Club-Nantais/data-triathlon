# Quickstart — vérifier le provider runnerbreizh

Toutes les commandes se lancent depuis `backend/`.

## 1. Tests unitaires (sans réseau)

```bash
uv run pytest tests/test_runnerbreizh.py tests/test_registry.py -q
uv run pytest -m "not integration"        # la suite complète doit rester verte
uv run ruff check .
```

## 2. Test réseau réel

```bash
uv run pytest -m integration -k runnerbreizh -q
```

## 3. Scrape à sec, sans base

```bash
uv run python -c "
from app.scrapers import registry
url = 'https://www.runnerbreizh.fr/requetetriathlons.php?CourseFichierGpsNom=2025-09-0749quiberon&page=2&tricourse=&Sexe='
rs = registry.scrape_event_all(url)
print(len(rs), 'participants')
print(rs[0].event_name, '|', rs[0].event_date, '|', rs[0].event_type, '|', rs[0].distance_km)
print(rs[0].athlete_name, rs[0].athlete_firstname, '|', rs[0].total_time, '|', rs[0].rank_overall, rs[0].category, rs[0].gender)
print('source_url :', rs[0].source_url)
print('sans dossard :', all(not r.bib_number for r in rs), '| sans club :', all(not r.club for r in rs))
"
```

Attendu (Triathlon de Quiberon M 2025) :

- **322** participants — l'URL pointe la page 2, l'import couvre les 7 pages ;
- `Triathlon de Quiberon M` (sans `(1.5/38/10)`), `2025-09-07`, `triathlon-m`,
  `49.5` ;
- 1er : `ABDELMOULA Jawad`, `01:45:35`, rang 1, `SEM`, `M` ;
- `source_url` = `https://www.runnerbreizh.fr/requetetriathlons.php?CourseFichierGpsNom=2025-09-0749quiberon`
  (canonique, sans `page`/`tricourse`/`Sexe`) ;
- `sans dossard : True`, `sans club : True`.

## 4. Import réel en base de dev

```bash
uv run python scripts/reset_db.py --no-seed --yes
uv run python -m app.cli rescrape-db \
  --url 'https://www.runnerbreizh.fr/requetetriathlons.php?CourseFichierGpsNom=2025-09-0749quiberon' \
  --url 'https://www.runnerbreizh.fr/requetetriathlons.php?CourseFichierGpsNom=2025-04-1323nozay&page=2&tricourse=&Sexe='
```

Attendu : « Épreuves ciblées : 2 », « Épreuves en erreur : 0 »,
**322 + 135 = 457** participants ajoutés, code de sortie 0.

Relancer la même commande : 0 ajouté, 457 déjà en base ou mis à jour — c'est la
preuve d'idempotence sans dossard.

## 5. Vérifier les deux refus attendus

```bash
uv run python -m app.cli rescrape-db \
  --url 'https://www.runnerbreizh.fr/triathlons.php?CoureurNom=KUENTZ&CoureurPrenom=Olivier' \
  --url 'https://www.runnerbreizh.fr/requetetriathlons.php?CourseFichierGpsNom=2099-01-01xx-inexistant'
```

Attendu : « Épreuves en erreur : 2 », chacune listée sous « Épreuves en erreur
(détail) : » avec sa cause — forme d'URL attendue pour la fiche coureur, épreuve
introuvable pour l'identifiant inconnu. Code de sortie **1** (échec total : aucune
épreuve n'aboutit).

## 6. Vérifier le périmètre club (limite assumée)

```bash
uv run python -m app.cli club-labels
```

Attendu : aucun libellé nouveau. Les participations runnerbreizh n'ont pas de
club, elles ne figurent donc dans aucun compteur club — c'est le comportement
arbitré, pas un défaut.

## 7. Bout en bout par l'interface

```bash
uv run python scripts/dev_server.py     # dans un terminal
cd ../frontend && npm run dev           # dans un autre
```

Coller sur `/ajouter` l'URL d'une épreuve runnerbreizh : le détecteur de provider
doit afficher `runnerbreizh`, la progression SSE dérouler les phases, et la fiche
d'épreuve montrer les segments sous les libellés de la discipline. Sur `/carte`,
l'épreuve doit apparaître si son nom porte un toponyme reconnaissable
(cf. SC-008 : 4 des 7 épreuves du panel).
