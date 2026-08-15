# Quickstart — validation de bout en bout

## Prérequis

```bash
cd backend && uv sync && uv run alembic upgrade head
cd frontend && npm install
```

## 1. Vérifier le calcul backend

```bash
cd backend
uv run pytest -m "not integration" tests/test_services/test_stats_service.py -v
```

Le nouveau test doit couvrir une épreuve avec des participants aux trois
statuts (`DNF`, `DNS`, `DSQ`) mêlés à des finishers et un statut inconnu, et
vérifier :
- `dnf`, `dns`, `dsq` correspondent chacun au bon décompte
- `non_finishers == dnf + dns + dsq`
- `total == finishers + non_finishers + unknown` (invariant déjà existant, non
  cassé)

## 2. Vérifier le rendu frontend

```bash
cd frontend
npm test -- --run app/courses/\[id\]/page.test.tsx components/results/RaceFinishers.test.tsx
```

Scénarios attendus :
- Épreuve avec les trois statuts non nuls → trois `MetaPill` distinctes
  (« Abandons », « Non-partants », « Disqualifiés ») avec les bons chiffres.
- Épreuve sans DNS ni DSQ → seule la pastille « Abandons » apparaît si elle est
  non nulle, aucune pastille vide pour les deux autres.
- `resumeEpreuve` (`RaceFinishers.tsx`) reflète la même distinction que les
  `MetaPill`, sur la même épreuve de test.

## 3. Vérification manuelle (recommandée avant de sortir la PR du brouillon)

```bash
cd backend && uv run python scripts/dev_server.py &
cd frontend && npm run dev
```

Ouvrir une épreuve de la base de dev connue pour avoir des non-finishers
(`uv run python -m app.cli` peut lister les épreuves importées), constater à
l'œil les pastilles séparées sur `/courses/[id]` et la cohérence avec le
résumé affiché dans la liste de résultats en dessous.

## 4. Suite complète avant PR

```bash
cd backend  && uv run pytest -m "not integration" && uv run ruff check .
cd frontend && npm test && npm run lint && npm run build
```
