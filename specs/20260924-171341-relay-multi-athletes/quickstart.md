# Quickstart : valider les relais multi-athlètes

## Prérequis

- `backend/.env` présent dans le worktree (à copier depuis la racine du dépôt).
- `uv run alembic upgrade head` depuis `backend/`.
- Un compte admin avec `participations:reassign`.

## Tests automatisés

```bash
cd backend && uv run pytest -m "not integration"
cd frontend && npm test && npm run lint
```

Scénarios couverts, à retrouver dans les tests :

1. Attribuer un relais à deux athlètes existants : la fiche de chacun liste le
   résultat, la fiche d'équipe est purgée (spec US1).
2. Attribuer à un athlète existant et à un nom saisi : la fiche est créée, ou
   réutilisée si le nom existe déjà (US2).
3. Refus : équipier déjà classé sur l'épreuve (409), doublon, moins de 2,
   plus de 8, résultat non relais (422). Aucun état partiel.
4. Rescrape d'une épreuve attribuée, avec et sans dossard : la composition
   tient, aucune ligne en double, aucune fiche d'équipe ne subsiste (research R3).
5. Compteurs : un relais 2e attribué à deux adhérents n'entre dans les podiums
   individuels d'aucun des deux, et compte une fois dans les podiums du club.
6. Un résultat non attribué rend `teammates: []`.

## Contrôle manuel

1. `uv run python scripts/dev_server.py`, puis `npm run dev`.
2. Ouvrir la fiche d'un athlète au nom d'équipe (relais importé).
3. « Attribuer aux équipiers », choisir deux athlètes, valider.
4. Vérifier les deux fiches, le classement de l'épreuve et le journal d'administration.
5. Chronométrer le geste de l'étape 3 : moins d'une minute (SC-002).
