# Quickstart: Retrait du bouton admin de déclaration de bénévolat (#780)

## Prérequis

```bash
cd backend && uv sync
cd frontend && npm ci
```

Aucune migration — schéma inchangé.

## Scénario 1 — Le bouton a disparu

1. Se connecter avec un compte détenant `athletes:volunteer_manage` (et
   seulement ce pouvoir).
2. Ouvrir la fiche d'un athlète.

**Attendu** : aucune section ni bouton « Déclarer une action de
bénévolat ». Si l'utilisateur ne détient aucun autre pouvoir de ce
panneau, aucune trace de `SeasonValidationPanel` du tout.

## Scénario 2 — « Valider la saison » reste intact

1. Se connecter avec un compte détenant `athletes:season_validate`.
2. Ouvrir la fiche d'un athlète.

**Attendu** : indicateur de quota et bouton « Valider »/« Dévalider »
inchangés.

## Scénario 3 — Le chemin retiré répond 404

```bash
curl -i -X POST http://localhost:<port>/api/v1/admin/athletes/1/volunteer-actions \
  -H "Content-Type: application/json" -d '{"season": 2026}'
```

**Attendu** : `404` (route inexistante) — plus `403`/`201`.

## Scénario 4 — Les données historiques restent lisibles

1. Créer une ligne `VolunteerAction` sans titre ni description
   directement en base (simulateur d'une ligne créée avant le retrait).
2. Consulter la file d'attente admin (#779) ou la liste des actions
   validées d'un athlète (#781).

**Attendu** : la ligne apparaît, avec son repli d'affichage existant
(`—`) — aucune erreur, aucune ligne masquée.

## Vérifications automatisées

```bash
cd backend && uv run pytest -m "not integration"
cd backend && uv run ruff check .
cd frontend && npm test && npm run lint && npx tsc --noEmit && npm run build
```
