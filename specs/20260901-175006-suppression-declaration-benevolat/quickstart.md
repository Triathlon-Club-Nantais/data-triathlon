# Quickstart: Suppression d'une déclaration de crédit de bénévolat

## Prérequis

- `backend/.env` configuré (`DATABASE_URL`), migrations à jour :
  `uv run alembic upgrade head` (aucune nouvelle migration attendue pour
  cette feature).
- Un compte admin portant `athletes:volunteer_validate`.
- Au moins une `VolunteerAction` en base pour tester chaque statut
  (`en_attente`, `validee`) — via le formulaire public `/benevolat` puis
  acceptation depuis `/admin/benevolat`, ou directement en base de dev.

## Vérification automatisée

```bash
cd backend
uv run pytest tests/test_repositories/test_volunteer_action_repository.py -k delete
uv run pytest tests/test_services/test_volunteer_action_service.py -k delete
uv run pytest tests/test_api/ -k volunteer_action_delete   # nom exact du fichier posé en tasks.md
uv run pytest -m "not integration"   # suite complète, sans régression

cd ../frontend
npm test -- AdminVolunteerActionsTable
npm test -- VolunteerActionsList
npm test   # suite complète
```

## Vérification manuelle — file d'attente (US1)

1. Démarrer `uv run python scripts/dev_server.py` (backend) et `npm run dev`
   (frontend), se connecter en admin.
2. Depuis `/benevolat`, créditer un athlète (`title`/`description`
   quelconques) → la déclaration apparaît sur `/admin/benevolat`.
3. Sur `/admin/benevolat`, déclencher la suppression de cette ligne : le
   dialog `DangerConfirm` s'ouvre, titre nommant la déclaration.
4. Annuler → la ligne reste dans la file d'attente (**Acceptance Scenario
   1.2**).
5. Recommencer, confirmer → la ligne disparaît de la file d'attente sans
   rechargement manuel (**1.1**, **SC-002**).

## Vérification manuelle — fiche athlète (US2)

1. Accepter une déclaration depuis `/admin/benevolat` pour qu'elle devienne
   `validee`.
2. Ouvrir la fiche de l'athlète concerné (`/athletes/{id}`), section
   « Actions de bénévolat validées ».
3. Noter le quota de saison affiché (`/admin/athletes/{id}` ou l'indicateur
   de la page club), déclencher la suppression de la ligne.
4. Annuler → rien ne change (**2.2**).
5. Confirmer → la ligne disparaît de la liste **et** le quota de saison se
   recalcule sans elle, sans rechargement manuel (**2.1**, **SC-002**).

## Vérification manuelle — refus de pouvoir (edge case, SC-004)

1. Avec une session sans `athletes:volunteer_validate` (ou via un appel API
   direct, `curl -X DELETE .../admin/volunteer-actions/{id}` sans session
   valide), confirmer un `401`/`403` — jamais un geste silencieusement
   accepté.

## Vérification manuelle — double suppression (edge case)

1. Ouvrir deux onglets sur la même file d'attente, supprimer la même
   déclaration depuis le premier.
2. Depuis le second (état pas encore rafraîchi), tenter la suppression de la
   même ligne → message d'erreur explicite (« Déclaration introuvable. »),
   pas d'écran cassé.
