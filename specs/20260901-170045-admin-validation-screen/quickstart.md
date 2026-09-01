# Quickstart: Écran de validation admin des déclarations de crédit d'athlète (#817)

## Prérequis

```bash
cd backend && uv sync
cd frontend && npm ci
```

Aucune migration — schéma inchangé.

## Scénario 1 — Instruire une déclaration en attente

1. Depuis `/benevolat`, soumettre une déclaration de crédit pour un athlète
   (formulaire du bas, #778/#809).
2. Se connecter avec un compte titulaire de `athletes:volunteer_validate`.
3. Ouvrir `/admin/benevolat`.

**Attendu** : la déclaration soumise à l'étape 1 apparaît, avec le nom de
l'athlète, le titre, la description et la date.

4. Cliquer « Accepter ».

**Attendu** : la déclaration disparaît de la liste ; elle apparaît
désormais sur la fiche de l'athlète concerné (#781, liste des actions
validées).

## Scénario 2 — État vide

1. S'assurer qu'aucune déclaration n'est en attente (toutes acceptées ou
   refusées).
2. Ouvrir `/admin/benevolat`.

**Attendu** : un état vide explicite, pas une page blanche.

## Scénario 3 — Refus d'accès

1. Se connecter avec un compte sans `athletes:volunteer_validate`.
2. Appeler directement `GET /api/v1/admin/volunteer-actions/pending`.

**Attendu** : `403` — inchangé, comportement déjà couvert par #779.

## Vérifications automatisées

```bash
cd backend && uv run pytest -m "not integration"
cd backend && uv run ruff check .
cd frontend && npm test && npm run lint && npx tsc --noEmit && npm run build
```
