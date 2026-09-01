# Quickstart: Ouvrir le formulaire de crédit d'un athlète au mot de passe du site (#809)

## Prérequis

```bash
cd backend && uv sync
cd frontend && npm ci
```

Migration requise avant test manuel :

```bash
cd backend && uv run alembic upgrade head
```

## Scénario 1 — Soumission sans session SSO

1. Ouvrir un navigateur en navigation privée.
2. Se rendre sur `/acces`, saisir le mot de passe partagé du site (jamais se
   connecter via SSO).
3. Ouvrir `/benevolat`.

**Attendu** : la section « Créditer un athlète pour le quota de saison »
s'affiche directement — aucune invite « Se connecter ». La section
d'auto-déclaration (#751), elle, affiche toujours l'invite.

4. Rechercher un athlète, le sélectionner, saisir titre et description,
   valider.

**Attendu** : confirmation affichée, la ligne apparaît en base avec
`status="en_attente"` et `declared_by_user_id=NULL`.

## Scénario 2 — Appel direct sans aucun cookie de session

```bash
curl -i -X POST http://localhost:<port>/api/v1/volunteer-actions \
  -H "Content-Type: application/json" \
  --cookie "<cookie du mot de passe du site uniquement>" \
  -d '{"athlete_id": 1, "title": "Ravitaillement", "description": "Poste eau km 15."}'
```

**Attendu** : `201`, pas `401`. `declared_by_user_id` vaut `null` dans la
réponse.

## Scénario 3 — Un visiteur connecté via SSO reste tracé

1. Se connecter via SSO, ouvrir `/benevolat`, soumettre une déclaration de
   crédit d'athlète.

**Attendu** : la ligne créée porte `declared_by_user_id` égal à l'id de
l'utilisateur connecté — comportement inchangé.

## Scénario 4 — La validation admin reste réservée à SSO + pouvoir

```bash
curl -i http://localhost:<port>/api/v1/admin/volunteer-actions/pending \
  --cookie "<cookie du mot de passe du site uniquement, sans session SSO>"
```

**Attendu** : `401` — inchangé, cette route n'est pas concernée par #809.

## Vérifications automatisées

```bash
cd backend && uv run pytest -m "not integration"
cd backend && uv run ruff check .
cd frontend && npm test && npm run lint && npx tsc --noEmit && npm run build
```
