# Quickstart — validation de bout en bout

Prérequis : backend et frontend du worktree lancés (`uv run python
scripts/dev_server.py` depuis `backend/`, `npm run dev` depuis `frontend/`,
base de dev seedée via `uv run python scripts/reset_db.py`).

## 1. Endpoint backend seul

```bash
cd backend
uv run python -c "
from app.core.database import SessionLocal
from app.repositories import athlete_repository
from app.core.season import current_season

db = SessionLocal()
rows = athlete_repository.list_with_season_participation_count(
    db, seasons=[current_season()], club_only=True
)
for athlete, count in rows:
    print(athlete.nom, athlete.prenom, count)
"
```

Attendu : une ligne par athlète club ayant ≥1 participation sur la saison en
cours, aucune ligne à 0.

Ou via l'API démarrée :

```bash
curl "http://localhost:8001/api/v1/athletes/season-activity?scope=club&seasons=$(date +%Y)"
```

(ajuster l'année de début de saison si on est avant le 1er septembre).

## 2. Page frontend

1. Ouvrir `http://localhost:3000/club/athletes`.
2. **US1** : la liste affiche les athlètes actifs de la saison en cours, avec
   leur nombre d'épreuves. Aucun athlète à 0 participation.
3. **US2** : changer la saison via le sélecteur → la liste et les compteurs se
   mettent à jour sans rechargement complet ; sélectionner une saison sans
   activité → état vide explicite.
4. **US3** : basculer le tri « nombre d'épreuves » ↔ « nom de famille » →
   l'ordre change instantanément (pas de nouvel appel réseau visible dans
   l'onglet Network — cf. research.md, tri client).

## 3. Tests automatisés

```bash
cd backend && uv run pytest -m "not integration" -k athlete
cd frontend && npm test -- athletes
```

Les deux doivent être verts avant `/speckit-tasks` → implémentation → revue.
