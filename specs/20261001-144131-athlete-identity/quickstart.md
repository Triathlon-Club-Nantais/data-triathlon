# Quickstart : valider l'identité stable des athlètes (#1146)

Guide de validation, pas d'implémentation. Contrats : `contracts/admin-api.md`, `contracts/cli-reconcile-athletes.md` ; modèle : `data-model.md`.

## Prérequis

```bash
cd backend
uv sync
uv run alembic upgrade head          # applique les migrations de l'epic
```

PostgreSQL local jetable pour la concurrence (facultatif, la CI le couvre) :

```bash
docker run --rm -d -p 5433:5432 -e POSTGRES_PASSWORD=pg --name pg-1146 postgres:16
export TEST_POSTGRES_URL=postgresql+psycopg://postgres:pg@localhost:5433/postgres
```

## 1. Suite unitaire (toujours)

```bash
uv run pytest -m "not integration"
uv run ruff check .
cd ../frontend && npm test && npm run lint && npm run build
```

## 2. Scénarios par story

| Story | Preuve | Attendu |
| --- | --- | --- |
| US1 graphies | tests d'import : `Léo`/`Leo`, `LE GLOANIC`/`LEGLOANIC`, `L'APPARTIEN`/`L APPARTIEN`, inversion, nom concaténé | une seule fiche ; `CIC 7`/`CIC 9` restent deux |
| US2 corrections | import → `update_athlete(birth_date)` → rescrape → nouvelle épreuve ; reassign avec et sans dossard → rescrape | fiche corrigée complète, aucune fiche NULL ; résultat réattribué en place, unique |
| US3 concurrence | `TEST_POSTGRES_URL=… uv run pytest tests/test_repositories -n 0 -k concurrency` | 300 fiches pour 300 personnes, 10 essais sur 10 |
| US4 homonymes | import d'une épreuve individuelle avec deux `MARTIN Thomas` aux dossards distincts, puis rescrape | deux fiches stables, `homonyms_created` au rapport ; cas en revue seulement si club |
| US5 fusion | `POST /admin/athletes/{kept}/merge` sur deux fiches portant résultats, validation, bénévolat | tout sur la conservée, absorbée supprimée, une entrée `athlete.merge` ; nouvelle épreuve avec la graphie absorbée → conservée |
| US6 reprise | `reconcile-athletes` sur une base de démo chargée des familles de doublons, puis `--yes --by-email` | simulation sans écriture ; application identique au rapport ; relance → `operations` vide |

## 3. Bout en bout en dev

```bash
cd backend && uv run python scripts/reset_db.py && uv run python scripts/dev_server.py
cd frontend && npm run dev
```

1. Connecté avec `athletes:write`, ouvrir une fiche athlète : la commande « Fusionner avec une autre fiche » apparaît ; choisir la seconde fiche, lire l'aperçu, confirmer.
2. Renommer une fiche vers l'identité d'une autre : le message propose la fusion.
3. Ouvrir `/admin/identites` : les cas listés, le badge de navigation, « Écarter » et « Fusionner ».
4. Sans `athletes:write` : aucune de ces commandes n'apparaît, et les routes répondent 403.

## 4. Production (PR 6, après déploiement des PR 1 à 5)

Procédure de `purge-timepulse-duplicates` (`docs/ci-cd.md`) : règle de pare-feu temporaire, `DATABASE_URL` sur la base cible, depuis `backend/`.

```bash
uv run python -m app.cli reconcile-athletes --json > simulation.json      # relire
uv run python -m app.cli reconcile-athletes --yes --by-email <admin> --json > application.json
uv run python -m app.cli reconcile-athletes --json                        # attendu : operations vide
```

Contrôle SC-001 : la requête de #907 (groupes par clé désaccentuée) ne renvoie plus que les groupes laissés en revue.
