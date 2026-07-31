# Quickstart — Fan-out Klikego

**Feature** : 005-klikego-fanout — [plan.md](./plan.md)

Ce quickstart montre les 5 vérifications concrètes à faire après implémentation pour confirmer que la feature marche. Il est destiné au porteur (revue humaine) et à `/speckit-implement` (sanity check final).

## Prérequis

- Branche `feat/156-klikego-fanout-event` checkoutée.
- `uv sync` dans `backend/`, `npm install` dans `frontend/`.
- Fixtures HTML committées dans `backend/tests/fixtures/klikego/`.

## Vérif 1 — Suite de tests offline verte

```bash
cd backend
uv run pytest -m "not integration" -q
```

Attendu : 1675+ tests passent (les tests existants) + les tests nouveaux de `_enumerate_heats`, du fan-out et du single-heat. Aucun réseau utilisé.

## Vérif 2 — Import UI d'un événement multi-heats

Lancer les services :

```bash
cd backend && uv run python scripts/dev_server.py &
cd frontend && npm run dev
```

Naviguer sur http://127.0.0.1:3000/ajouter, coller l'URL nue de Mesquer 2026 :

```
https://www.klikego.com/resultats/triathlon-et-swimrun-mesquer-quimiac-2026/1677015306084-12
```

Attendu :
- Phase `scraping` puis `saving` progressent au fil des 8 heats.
- Phase `done` : le récap liste **8 courses** avec un lien vers chacune.
- La base contient 8 `Course` avec `source_url` distincte (`…?heat=triathlon-s-indiv`, `…?heat=swim-run-m-duo`, etc.), chacune avec ses participations.

## Vérif 3 — Import UI avec URL portant `?heat=X`

Toujours dans `/ajouter`, coller cette fois l'URL copiée depuis Klikego avec `?heat=triathlon-s-indiv` :

```
https://www.klikego.com/resultats/triathlon-et-swimrun-mesquer-quimiac-2026/1677015306084-12?heat=triathlon-s-indiv&search=&city=&category=&sexe=
```

Attendu :
- Même résultat que Vérif 2 : 8 courses créées (ou signalées en cache si déjà en base). `?heat=` **ignoré**.
- Le récap final est identique.

## Vérif 4 — Échappatoire `--single-heat`

Depuis `backend/` :

```bash
uv run python -m app.cli rescrape-db --url "https://www.klikego.com/resultats/triathlon-et-swimrun-mesquer-quimiac-2026/1677015306084-12?heat=triathlon-s-indiv" --single-heat
```

Attendu :
- Bilan : « Épreuves ciblées : 1 · Épreuves traitées : 1 · Épreuves en erreur : 0 ».
- Une seule `Course` re-scrapée (`triathlon-s`), pas de fan-out sur les 7 autres.
- Code de sortie 0.

Erreurs d'usage à vérifier (code 2) :

```bash
uv run python -m app.cli rescrape-db --single-heat                       # sans --url
uv run python -m app.cli rescrape-db --url "https://…?heat=X" --provider klikego --single-heat  # avec --provider
uv run python -m app.cli rescrape-db --url "https://…" --single-heat     # URL nue
```

Attendu pour chacune : message d'erreur qui nomme la contrainte, code 2, aucun scraping lancé.

## Vérif 5 — CLI `import-sheet` (chemin nominal, fan-out)

Depuis `backend/` :

```bash
uv run python -m app.cli import-sheet --dry-run --limit 3
```

Attendu :
- Pour une URL Klikego du Sheet (nue ou `?heat=`), le bilan de simulation annonce **N heats** à traiter, pas 1.
- Le rapport texte va sur stdout, la progression sur stderr (contrat CLI stable).

## Vérif 6 — Non-régression Breizh Chrono

```bash
uv run python -m app.cli rescrape-db --provider breizhchrono --limit 3 --dry-run
```

Attendu : bilan identique à la baseline main (Breizh Chrono fan-outait déjà, aucun changement de comportement attendu).

## Vérif 7 — Constitution : aucune migration Alembic

```bash
git diff main..HEAD -- backend/alembic/versions/
```

Attendu : aucune ligne. La feature n'introduit **aucune** révision Alembic (cf. `data-model.md`).
