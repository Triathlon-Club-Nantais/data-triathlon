# Quickstart : validation de bout en bout

**Préalable** : suppose la branche d'#271 déjà en place (cette feature en
dépend) et un administrateur disposant du pouvoir `benevole_access:manage`.

```bash
cd backend
uv run alembic upgrade head
```

## Scénario 1 — remplacement manuel (US1)

1. `GET /api/v1/admin/benevoles/access` → `{"configured": false, ...}` avant
   tout réglage.
2. `PUT /api/v1/admin/benevoles/access` avec `{"password": "un-secret-assez-long"}`
   → 200.
3. `POST /api/v1/benevoles/session` avec ce mot de passe → 204 + cookie.
4. `GET /api/v1/admin/benevoles/access` → `configured: true`, `updated_by`
   nomme l'administrateur.

## Scénario 2 — rotation invalide les sessions en cours (US1, AC2)

1. Ouvrir une session bénévole avec le mot de passe du scénario 1.
2. `PUT /api/v1/admin/benevoles/access` avec un **autre** mot de passe.
3. `GET /api/v1/benevoles/queue` avec le cookie ouvert à l'étape 1 → 401.
4. `POST /api/v1/benevoles/session` avec l'**ancien** mot de passe → 401.

## Scénario 3 — génération sécurisée (US2)

1. `POST /api/v1/admin/benevoles/access/generate` → 200,
   `{"password": "<24 caractères>", ...}`.
2. `POST /api/v1/benevoles/session` avec ce mot de passe → 204.
3. Aucune route ne permet de retrouver ce mot de passe une seconde fois
   (vérifier que `GET /api/v1/admin/benevoles/access` ne le rend jamais).

## Scénario 4 — garde du pouvoir dédié

1. Un utilisateur du back-office **sans** `benevole_access:manage` appelle
   les trois routes ci-dessus → 403 sur chacune (401 s'il n'a pas de
   session du tout).

## Vérification automatisée

```bash
cd backend && uv run pytest -m "not integration" && uv run ruff check .
cd frontend && npm test && npm run lint && npm run build
```
