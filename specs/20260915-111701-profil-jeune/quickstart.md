# Quickstart: Profil individuel jeune (#867)

## Prérequis

- `backend/.env` configuré (`DATABASE_URL`), migrations à jour.
- Un compte de session porteur d'un rôle avec `jeunes:read` et `jeunes:write`
  (voir `app/cli grant-role` ou l'écran `/admin/droits`).

## Vérifier la migration

```bash
cd backend
uv run alembic upgrade head
uv run python -c "from app.core.database import engine; from sqlalchemy import inspect; print(inspect(engine).get_table_names())"
# personal_profiles et profile_log_entries doivent apparaître
```

## Vérifier l'API (backend seul)

```bash
cd backend
uv run python scripts/dev_server.py &
# avec une session valide (cookie) :
curl -s http://localhost:<port>/api/v1/admin/profiles -H "Cookie: ..."
# → []  (aucun profil au départ)

curl -s -X POST http://localhost:<port>/api/v1/admin/profiles \
  -H "Content-Type: application/json" -H "Cookie: ..." \
  -d '{"first_name": "Alix", "last_name": "Martin"}'
# → 201, ProfileDetailRead avec log_entries: []

curl -s -X POST http://localhost:<port>/api/v1/admin/profiles/1/log-entries \
  -H "Content-Type: application/json" -H "Cookie: ..." \
  -d '{"text": "Première séance, bon niveau natation."}'
# → 201, log_entries contient la nouvelle entrée
```

## Vérifier l'écran (frontend + backend)

```bash
cd frontend && npm run dev
```

1. Ouvrir `/admin/jeunes` — la liste des profils créés s'affiche.
2. Ouvrir un profil — informations personnelles + journal de bord, plus
   récent en premier.
3. Sans le pouvoir `jeunes:write` : aucun formulaire de création/édition
   n'est proposé. Avec : créer/modifier un profil, ajouter une entrée de
   journal, vérifier la mise à jour immédiate de l'écran.

## Tests automatisés

```bash
cd backend && uv run pytest -m "not integration" tests/test_repositories/test_profile_repository.py tests/test_services/test_profile_service.py tests/test_api/test_admin_profiles.py tests/test_permissions_catalogue.py
cd frontend && npm test
```

## Preuve de garde (SC-002 de spec.md)

`tests/test_api/test_admin_profiles.py` doit couvrir : 401 sans session,
403 avec session mais sans le pouvoir requis, sur chacune des cinq routes.
