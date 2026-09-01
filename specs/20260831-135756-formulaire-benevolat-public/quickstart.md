# Quickstart: Formulaire public de déclaration de bénévolat (#778)

## Prérequis

```bash
cd backend && uv sync && uv run alembic upgrade head
cd frontend && npm ci
```

Backend et frontend démarrés (`uv run python scripts/dev_server.py`,
`npm run dev` — ports découverts automatiquement, cf.
`docs/dev-multi-worktree.md`).

## Scénario 1 — Un adhérent connecté déclare pour un athlète (US1)

1. Se connecter (SSO) puis ouvrir `/benevolat`.
2. Dans la nouvelle section, saisir 2+ caractères d'un nom d'athlète connu de
   la base de dev.
3. Sélectionner l'athlète dans les résultats.
4. Saisir un titre et une description, valider.

**Attendu** : confirmation affichée ; `GET /admin/athletes/{id}/... `
(ou requête SQL directe sur `volunteer_actions`) montre une nouvelle ligne
`status="en_attente"`, `title`/`description` renseignés, `season` égal à la
saison en cours.

## Scénario 2 — Validation refusée sur formulaire incomplet (US1, edge case)

1. Sélectionner un athlète, laisser le titre ou la description vide, tenter
   de valider.

**Attendu** : erreur affichée côté client, aucune requête réseau (ou 422 si
la validation client est contournée) — aucune ligne créée.

## Scénario 3 — Recherche d'athlète sans champ réservé (US2)

1. Ouvrir les outils réseau du navigateur, effectuer une recherche.

**Attendu** : la réponse de `GET /athletes?name=...` ne contient jamais
`birth_date` (schéma `AthleteBrief`).

## Scénario 4 — Accès refusé sans session (US1, edge case)

```bash
curl -i -X POST http://localhost:<port>/api/v1/volunteer-actions \
  -H "Content-Type: application/json" \
  -d '{"athlete_id": 1, "title": "x", "description": "y"}'
```

**Attendu** : `401` (pas de cookie de session).

## Vérifications automatisées

```bash
cd backend && uv run pytest -m "not integration"
cd frontend && npm test && npm run lint && npx tsc --noEmit
```
