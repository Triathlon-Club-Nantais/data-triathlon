# Quickstart: Bouton de signalement (bug / feedback)

Validation de bout en bout, une fois l'implémentation posée. Suppose un
environnement de dev déjà installé (`AGENTS.md` § Commandes).

## Prérequis

```bash
cd backend
uv run alembic upgrade head          # applique la migration user_feedback
uv run python scripts/dev_server.py  # API sur le premier port libre à partir de 8001
```

```bash
cd frontend
npm run dev                          # branché sur le backend du worktree
```

Un compte avec le pouvoir `feedback:read` et `feedback:manage` doit exister
(`uv run python -m app.cli grant-role --email <adresse> --role admin`, ou un
rôle dédié composé via `/admin/droits`).

## Scénario 1 — soumission publique (US1)

1. Ouvrir n'importe quelle page publique (`/`, `/resultats`, `/club`…) sans
   être connecté.
2. Cliquer sur le bouton de signalement flottant.
3. Remplir titre + description, choisir « bug », valider.
4. **Attendu** : confirmation visible côté client ;
   `GET /api/v1/admin/feedback` (avec un compte habilité) fait apparaître le
   nouveau signalement, statut `nouveau`, `page_url` renseignée, aucun email.

## Scénario 2 — soumission connectée (US1, variante)

1. Se connecter via le SSO.
2. Soumettre un signalement de type « feedback ».
3. **Attendu** : le signalement porte l'email du compte connecté dans sa vue
   détail.

## Scénario 3 — liste et tri (US2)

1. Avec plusieurs signalements en base (répéter le scénario 1 avec des types
   et statuts variés, ou via `PATCH` direct en base de test).
2. Ouvrir `/admin/retours-utilisateurs`.
3. Trier par date, puis par type, puis par statut.
4. **Attendu** : l'ordre change en conséquence à chaque tri.

## Scénario 4 — traitement (US3)

1. Ouvrir le détail d'un signalement `nouveau`.
2. Le faire passer à `traité`.
3. **Attendu** : la vue détail et la liste reflètent immédiatement le nouveau
   statut (revalidation TanStack Query).

## Scénario 5 — promotion GitHub (US4)

1. Depuis la vue détail d'un signalement de type « bug », cliquer sur
   « Promouvoir en issue GitHub ».
2. **Attendu** : un nouvel onglet s'ouvre vers
   `github.com/Triathlon-Club-Nantais/data-triathlon/issues/new` avec le titre
   et la description pré-remplis, sans qu'aucune requête réseau ne parte du
   backend vers GitHub (vérifiable : aucun appel sortant dans les logs
   backend au clic).
3. Coller une URL d'issue (fictive en test) dans le champ prévu, enregistrer.
4. **Attendu** : l'URL réapparaît dans la vue détail à la prochaine ouverture.

## Scénario 6 — anti-spam (FR-010, FR-011)

1. Soumettre le formulaire avec le champ honeypot renseigné (via un appel
   direct à `POST /api/v1/admin/feedback` plutôt que le formulaire, qui ne
   l'expose pas visuellement) : **attendu** un `201` apparent, mais rien
   n'apparaît dans `GET /admin/feedback`.
2. Soumettre plusieurs signalements légitimes depuis la même IP en rafale, au
   -delà du seuil configuré : **attendu** un `429` avec message français
   explicite à partir du signalement en trop.

## Vérifications automatisées

```bash
cd backend && uv run pytest -m "not integration" tests/test_api/test_admin_feedback_api.py tests/test_services/test_feedback_service.py tests/test_repositories/test_feedback_repository.py
cd frontend && npm test -- FeedbackButton FeedbackTable FeedbackDetailDialog
```
