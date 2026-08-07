# Quickstart — valider la liste d'autorisation de bout en bout

Guide de validation, pas d'implémentation. Les détails de contrat sont dans
`contracts/`, le schéma dans `data-model.md`.

## Prérequis

- `backend/.env` avec `DATABASE_URL` et les réglages `AUTH_*` (le tableau vit
  dans `backend/README.md` — **sept** réglages après cette feature, la liste
  d'autorisation n'en fait plus partie).
- **Le piège multi-worktree de #114 vaut ici aussi** : une application OAuth
  GitHub n'accepte qu'une seule URL de retour, port compris. Le parcours de
  connexion n'est utilisable que depuis l'espace de travail principal. Les
  scénarios 3 à 6 ci-dessous, eux, ne demandent aucune connexion réelle.

## 1. Schéma et amorçage

```bash
cd backend
uv run alembic upgrade head            # crée allowed_emails, reprend AUTH_ALLOWED_EMAILS si elle est posée
uv run python -m app.cli allow-email --email vous@exemple.fr
uv run python -m app.cli allow-email --email vous@exemple.fr    # doit dire « rien à faire »
```

Attendu : la première commande sort en `0` avec « autorisée », la seconde en `0`
avec « rien à faire ». Aucun doublon en base.

> En développement, `AUTH_ALLOWED_EMAILS` vit dans `backend/.env`, que
> `pydantic-settings` lit mais qui ne peuple pas `os.environ` : la reprise
> automatique de la migration ne s'y déclenche donc pas. C'est `allow-email` qui
> tient lieu d'amorçage local, et c'est sans conséquence — la reprise vise la
> production, où la variable est posée dans l'environnement du processus.

## 2. Se connecter, puis s'habiliter

```bash
uv run python scripts/dev_server.py     # port libre publié
# dans frontend/ : npm run dev, puis se connecter via l'écran /login
uv run python -m app.cli grant-role --email vous@exemple.fr --role admin
```

Attendu : la connexion aboutit et redirige vers `/admin`. Avant `grant-role`,
`GET /api/v1/auth/me` rend deux listes vides — état légitime. Après, il rend le
rôle `admin` et **tout le catalogue** dans `permissions`, `allowed_emails:manage`
compris : un superutilisateur porte le catalogue, ni plus ni moins
(`effective_permissions`). C'est la vérification la plus rapide que le pouvoir
nouveau est bien enregistré dans `permissions.ALL`.

## 3. L'écran (US1, US2)

La destination est `/admin/acces`, sous la section « Gestion des utilisateurs »
du rail. **Elle n'apparaît dans la navigation qu'à qui porte
`allowed_emails:manage`** — c'est un confort d'affichage, l'URL directe reste
atteignable et c'est l'API qui refuse. L'écran doit :

| Geste | Attendu |
| --- | --- |
| Charger | la liste, triée par adresse ; « Aucune adresse autorisée » si elle est vide — et **pas** ce message sur un `403` |
| Ajouter `Nouveau@Exemple.FR ` | la ligne apparaît en `nouveau@exemple.fr` |
| Ajouter la même une seconde fois | succès, toujours une seule ligne |
| Ajouter `pas-une-adresse` | refus lisible en français, liste inchangée |
| Retirer une ligne | elle disparaît |
| Retirer sa propre ligne, seul administrateur actif | refus `409`, message qui nomme le dernier administrateur |

## 4. Le retrait ferme vraiment (US2, FR-016)

Sans navigateur, en deux appels :

```bash
# avec le cookie de session d'un compte autorisé « cible »
curl -i -b "tcn_session=<jeton>" localhost:<port>/api/v1/auth/me     # 200
# depuis un compte administrateur, retirer l'adresse de « cible »
curl -i -b "tcn_session=<jeton>" localhost:<port>/api/v1/auth/me     # 401, sans déconnexion ni redémarrage
```

Puis réinscrire l'adresse et vérifier qu'une **nouvelle** connexion aboutit : la
réactivation est ce qui rend le geste réversible.

## 5. La liste vide n'ouvre rien (FR-004)

```bash
# base sans aucune adresse autorisée
curl localhost:<port>/api/v1/auth/methods    # rend les moyens configurés — ce n'est plus []
```

…et la connexion échoue au retour du fournisseur, en redirigeant vers
`/login?error=account_not_allowed`. C'est le changement de comportement assumé
en `plan.md` §Complexity Tracking : le garde de configuration ne pèse plus la
liste, le fail-closed tombe au retour de parcours. Le refus journalise l'adresse
soumise côté backend — c'est là qu'on lit quoi ajouter.

## 6. Les filets

```bash
cd backend && uv run pytest -m "not integration"
cd backend && uv run ruff check .
cd frontend && npm test && npm run lint && npm run build
```

Trois tests doivent être regardés nommément, parce qu'ils échouent pour de
bonnes raisons si la feature est mal posée :

- `tests/test_auth/test_public_routes_still_open.py` — aucune route publique ne
  se ferme, et les trois ressources nouvelles sont gardées.
- `tests/test_permissions_catalogue.py` — le pouvoir ajouté garde au moins une
  ressource (il rougit tant que la garde manque).
- `tests/test_migrations.py` — `alembic upgrade head` passe sur base vierge, et
  la reprise depuis l'environnement insère ce qu'il faut.

## 7. La mise en production, dans cet ordre

1. **Déployer.** Le `startCommand` de Render exécute `alembic upgrade head` avant
   `uvicorn` : la table est créée et **remplie depuis `AUTH_ALLOWED_EMAILS`**
   avant la première requête. Aucune fenêtre de refus (SC-005).
2. **Vérifier** dans `/admin/acces` que la liste porte bien les adresses
   attendues.
3. **Dans une PR de suivi**, une fois l'étape 2 constatée : retirer l'entrée de
   `render.yaml`, puis la variable du tableau de bord Render. Elle est
   **volontairement conservée** par la livraison qui pose la table — c'est elle
   que lit la reprise. La retirer du même geste ferait dépendre la production
   d'un comportement non vérifié (l'hébergeur nettoie-t-il une valeur
   `sync: false` quand la clé disparaît du blueprint ?). Une variable qui traîne
   est inoffensive : `Settings` porte `extra="ignore"`.

L'ordre 1-2-3 n'est pas cosmétique : inverser 1 et 3 vide la source de la reprise
et ferme l'accès à tout le monde. **Et le rattrapage n'est pas `allow-email`** :
les services backend tournent en `plan: free`, qui n'ouvre aucun shell. Le seul
recours serait un `INSERT` dans la console Supabase — écrit dans `docs/ci-cd.md`.
