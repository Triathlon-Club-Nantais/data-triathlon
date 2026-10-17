# Quickstart : valider Comptes membres, socle

Depuis `backend/` sauf mention contraire.

## Tests automatiques

```bash
uv run pytest -m "not integration"
uv run ruff check .
cd ../frontend && npm test && npm run lint && npm run build
```

Fichiers à surveiller : `tests/test_services/test_member_emails_service.py`, `tests/test_api/test_admin_member_emails_api.py`, `tests/test_cli/test_import_member_emails.py`, `tests/test_services/test_membership.py`, `tests/test_auth/test_provisioning.py`, `tests/test_auth/test_site_access_gate.py`, `tests/test_auth/test_entra_provider.py`, `tests/test_core_http.py`, `tests/test_permissions_catalogue.py`.

## US1, liste d'adhérents (#1334)

1. `uv run alembic upgrade head`.
2. Préparer un CSV `email\njeanne@exemple.fr\nPAUL@Exemple.fr \nfaux`.
3. `uv run python -m app.cli import-member-emails --season 2026 --file membres.csv --json` → `{"season": 2026, "added": 2, "removed": 0, "unchanged": 0, "ignored": 1}`.
4. Relancer avec un fichier sans `jeanne` → `removed: 1`.
5. Back-office `/admin/adresses-adherents` (compte portant `member_emails:manage`) : la liste affiche `paul@exemple.fr` ; ajout manuel puis réimport : l'entrée manuelle reste.
6. `uv run python -m app.cli purge-retention --dry-run` : la ligne « adresses d'adhérents » apparaît.

## US2, connexion ouverte (#1322)

Avec le fournisseur de test des suites (`DoublureProvider`), vérifié par les tests :
- adresse hors `allowed_emails` → session ouverte, aucun rôle, redirection vers `/` ;
- adresse dans `member_emails` (saison qui compte) → routes gardées par le code de site accessibles sans cookie de site ; `/auth/me` rend `is_member: true` ;
- retrait de l'adresse → requête suivante en 401 `site_access_required`.

## US3, Entra External ID (#1323)

Hors production, sans réseau : `tests/test_auth/test_entra_provider.py` (découverte, JWKS, jeton signé localement).

Déploiement réel (exploitant, une fois) : suivre `infra/entra-external-id/AGENTS.md` :
1. `az provider register --namespace Microsoft.AzureActiveDirectory` (une fois), `az deployment group what-if …` puis `az deployment group create -g TCN_Data_BDD -f infra/entra-external-id/main.bicep -p infra/entra-external-id/main.bicepparam`.
2. Créer le client OAuth Google (console Google Cloud, URI de redirection listées dans `AGENTS.md`).
3. Une application par environnement, deux lancements : `APP_NAME=data-triathlon-preview REDIRECT_URI=<retour preview> GOOGLE_CLIENT_ID=… GOOGLE_CLIENT_SECRET=… ./infra/entra-external-id/configure-tenant.sh <tenantId>`, puis `APP_NAME=data-triathlon-prod REDIRECT_URI=<retour production> ./infra/entra-external-id/configure-tenant.sh <tenantId>` ; relancé, il ne crée rien de plus.
4. Poser `AUTH_ENTRA_*` sur Render (preview d'abord).
5. **FR-021** : se connecter une fois par Google et une fois par code e-mail, décoder l'`id_token` reçu (journal de debug local), constater `email` et `xms_edov: true`, consigner le résultat dans le sondage. Échec : ne pas activer en production, rouvrir #1324.
