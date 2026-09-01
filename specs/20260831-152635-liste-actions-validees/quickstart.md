# Quickstart: Liste des actions de bénévolat validées sur la fiche athlète (#781)

## Prérequis

```bash
cd backend && uv sync && uv run alembic upgrade head
cd frontend && npm ci
```

Aucune migration nouvelle. Backend + frontend démarrés.

## Scénario 1 — Liste visible avec le pouvoir (US1)

1. Se connecter avec un compte portant `athletes:volunteer_validate`.
2. Ouvrir la fiche d'un athlète ayant au moins une action `"validee"`.

**Attendu** : section visible avec titre + description de chaque action
validée, triées récent → ancien.

## Scénario 2 — État vide

1. Ouvrir la fiche d'un athlète sans action validée (aucune, ou
   seulement en attente/refusées).

**Attendu** : état vide explicite, section toujours visible pour un
compte habilité.

## Scénario 3 — Invisible sans le pouvoir

```bash
curl -i http://localhost:<port>/api/v1/admin/athletes/1/volunteer-actions/validated \
  -H "Cookie: <cookie d'un compte sans athletes:volunteer_validate>"
```

**Attendu** : `403`. Côté navigateur, aucune section ni message — vérifié
en ouvrant la fiche avec un compte sans le pouvoir.

## Vérifications automatisées

```bash
cd backend && uv run pytest -m "not integration"
cd backend && uv run ruff check .
cd frontend && npm test && npm run lint && npx tsc --noEmit && npm run build
```
