# Quickstart: Calendrier des entraînements jeunes

Prérequis : `backend/.env` configuré (`DATABASE_URL`), `uv sync` fait.

## 1. Appliquer la migration

```bash
cd backend
uv run alembic upgrade head
```

Vérifie que les tables `entrainements_jeunes` et `entrainement_participants`
existent (`sqlite3 dev.db ".schema entrainements_jeunes"` en dev SQLite, ou
`psql` en preview).

## 2. Vérifier le contrat backend

Avec une session RBAC porteuse de `jeunes:write` (cf. `docs/api/AGENTS.md`
§Protéger une ressource pour poser un rôle de test) :

```bash
curl -s -X POST http://localhost:8000/api/v1/admin/jeunes/entrainements \
  -H 'Content-Type: application/json' \
  --cookie <cookie-de-session> \
  -d '{"date": "2026-09-20", "lieu": "Base nautique"}'
# -> 201, EntrainementDetailRead avec participants: []

curl -s http://localhost:8000/api/v1/admin/jeunes/entrainements \
  --cookie <cookie-de-session>
# -> 200, liste avec cet entraînement, participant_count: 0

curl -s -X POST http://localhost:8000/api/v1/admin/jeunes/entrainements/1/participants \
  -H 'Content-Type: application/json' \
  --cookie <cookie-de-session> \
  -d '{"jeune_id": 42}'
# -> 201, participants: [{"jeune_id": 42, ...}], participant_count: 1
```

Sans session, ou avec une session sans `jeunes:read`/`jeunes:write` : `401`/`403`
respectivement — voir `contracts/api.md`.

## 3. Vérifier l'écran frontend

```bash
cd frontend
npm run dev
```

Se connecter avec un compte porteur de `jeunes:read` (voir
`/admin/droits` pour composer un rôle de test), ouvrir
`/admin/jeunes/calendrier` :

- la liste des entraînements créés à l'étape 2 s'affiche, triée par date ;
- sans `jeunes:write`, aucun bouton de création n'est proposé ;
- avec `jeunes:write`, un formulaire de création est visible et fonctionnel,
  et chaque séance ouvre sa liste de participants avec inscription/désinscription.

Tester à largeur 375px (outils dev navigateur, mode responsive) : aucune
barre de défilement horizontale.

## 4. Suites de tests

```bash
cd backend && uv run pytest -m "not integration"
cd frontend && npm test
```
