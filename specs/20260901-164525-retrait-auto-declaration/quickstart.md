# Quickstart: Retrait de l'auto-déclaration de bénévolat (#816)

## Prérequis

```bash
cd backend && uv sync && uv run alembic upgrade head
cd frontend && npm ci
```

## Scénario 1 — Une seule section sur /benevolat

1. Ouvrir `/benevolat`, sans session SSO puis avec.

**Attendu** : dans les deux cas, seule la section « Créditer un athlète
pour le quota de saison » s'affiche — aucune trace de l'auto-déclaration,
aucune invite « Se connecter ».

## Scénario 2 — Les anciennes routes répondent 404

```bash
curl -i -X POST http://localhost:<port>/api/v1/volunteer-declarations \
  -H "Content-Type: application/json" -d '{"title": "x", "description": "y"}'
curl -i http://localhost:<port>/api/v1/admin/volunteer-declarations
```

**Attendu** : `404` sur les deux — routes inexistantes, plus `401`/`403`.

## Scénario 3 — /admin/benevolat reste fonctionnelle

1. Se connecter avec un compte titulaire du pouvoir de validation des
   déclarations de crédit d'athlète.
2. Ouvrir `/admin/benevolat`.

**Attendu** : l'écran de validation livré par #817 s'affiche — jamais de
page vide ni de 404 (research.md D3).

## Vérifications automatisées

```bash
cd backend && uv run pytest -m "not integration"
cd backend && uv run ruff check .
cd frontend && npm test && npm run lint && npx tsc --noEmit && npm run build
```
