# Quickstart: Appel de présence jeunes

Prérequis : `backend/.env` configuré (`DATABASE_URL`), `uv sync` fait, une
séance avec au moins un jeune inscrit déjà en base (`quickstart.md` de
`specs/20260915-140000-calendrier-jeunes/` §2).

## 1. Appliquer la migration

```bash
cd backend
uv run alembic upgrade head
```

Vérifie que `entrainement_participants` porte `present` et
`entrainements_jeunes` porte `note`
(`sqlite3 dev.db ".schema entrainement_participants"` en dev SQLite, ou `psql`
en preview). Vérifier aussi le reflux :

```bash
uv run alembic downgrade -1
uv run alembic upgrade head
```

## 2. Vérifier le contrat backend

Avec une session RBAC porteuse de `jeunes:write` (cf.
`docs/api/AGENTS.md` §Protéger une ressource) et un entraînement `12` portant
déjà le jeune `3` inscrit :

```bash
curl -s -X PATCH http://localhost:8000/api/v1/admin/jeunes/entrainements/12/participants/3/presence \
  -H 'Content-Type: application/json' \
  --cookie <cookie-de-session> \
  -d '{"present": true}'
# -> 200, participants: [{"jeune_id": 3, "present": true, ...}]

curl -s -X POST http://localhost:8000/api/v1/admin/jeunes/entrainements/12/participants \
  -H 'Content-Type: application/json' \
  --cookie <cookie-de-session> \
  -d '{"jeune_id": 7, "present": true}'
# -> 201, un nouveau participant inscrit ET pointé présent en un seul appel

curl -s -X PATCH http://localhost:8000/api/v1/admin/jeunes/entrainements/12 \
  -H 'Content-Type: application/json' \
  --cookie <cookie-de-session> \
  -d '{"note": "Groupe réduit, bassin partagé avec le club voisin."}'
# -> 200, "note" mise à jour

curl -s -X POST http://localhost:8000/api/v1/admin/profiles/3/log-entries \
  -H 'Content-Type: application/json' \
  --cookie <cookie-de-session> \
  -d '{"text": "A progressé sur le crawl aujourd'\''hui."}'
# -> 201, entrée versée au journal du jeune 3 (route existante, #867)
```

Sans session, ou avec une session sans `jeunes:read`/`jeunes:write` :
`401`/`403` respectivement — voir `contracts/api.md`.

## 3. Vérifier l'écran frontend

```bash
cd frontend
npm run dev
```

Se connecter avec un compte porteur de `jeunes:write`, ouvrir la nouvelle
entrée de navigation unique « Jeunes » :

- elle propose trois destinations : Profils, Calendrier, Appel ;
- ouvrir « Appel » sans séance créée pour aujourd'hui propose de la créer, puis
  ouvre son appel de début, vide ;
- pointer un jeune inscrit présent/absent met à jour son statut immédiatement,
  visible après rechargement de la page ;
- ajouter un jeune non inscrit et le pointer présent l'inscrit et le pointe en
  un seul geste (aucun état intermédiaire visible) ;
- basculer sur « Appel de fin » ne montre que les jeunes marqués présents ;
  cocher/décocher n'écrit rien (vérifiable : aucune requête réseau
  d'écriture dans l'onglet réseau du navigateur) et repart vierge à la
  réouverture de l'onglet ;
- ajouter une note de séance et une note à un jeune les enregistre ; la note
  du jeune apparaît sur son profil (`/admin/jeunes/{id}`), atteignable en un
  clic depuis l'appel ;
- sans `jeunes:write` (session `jeunes:read` seule), les statuts et notes
  existants s'affichent mais aucun contrôle d'écriture n'est proposé.

Tester à largeur 375px (outils dev navigateur, mode responsive) : aucune
barre de défilement horizontale sur l'écran d'appel.

## 4. Suites de tests

```bash
cd backend && uv run pytest -m "not integration"
cd frontend && npm test
cd frontend && npx vitest run components/layout/nav.config.test.ts
```
