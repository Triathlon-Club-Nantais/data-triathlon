# Quickstart — vérifier le RBAC de bout en bout

**Feature** : RBAC — rôles composables · **Révisé** : 2026-08-04 (v2)

Guide de **validation**, pas d'implémentation. Contrats :
[`contracts/admin-api.md`](contracts/admin-api.md) · [`contracts/cli.md`](contracts/cli.md).
Modèle : [`data-model.md`](data-model.md).

## Prérequis

```bash
cd backend && uv sync && uv run alembic upgrade head
```

Les réglages `AUTH_*` de #114 doivent être en place pour les étapes 3 et
suivantes. Rappel du piège multi-worktree : une application OAuth GitHub
n'accepte qu'une seule URL de retour, port compris — ces étapes ne se déroulent
que depuis l'espace de travail principal.

---

## 1. La suite passe

```bash
uv run pytest -m "not integration"
cd ../frontend && npm test && npm run build
```

Trois filets à regarder nommément dans la sortie :

- `test_permissions_catalogue.py` — **aucun pouvoir déclaré n'est inutilisé**, et
  aucune garde ne cite un code inexistant. Vérifiable en ajoutant temporairement
  un membre au catalogue : la suite doit rougir.
- `test_public_routes_still_open.py` — les ressources d'administration sont
  **classées**, pas exclues de l'inventaire. Ajouter temporairement une route au
  router `admin` sans la classer doit faire rougir la suite, en nommant la route.
- `test_lockout_invariant.py` — les quatre chemins de verrouillage sont refusés.

---

## 2. Amorcer un administrateur, sans réseau

```bash
uv run python -m app.cli grant-role --email inconnue@example.org --role admin
echo $?   # 2 — un utilisateur naît d'une connexion, pas d'une commande

# après vous être connecté une fois par l'interface :
uv run python -m app.cli grant-role --email <votre adresse> --role admin
echo $?   # 0
uv run python -m app.cli grant-role --email <votre adresse> --role admin
echo $?   # 0 — idempotent, le rapport dit « rien à faire »
uv run python -m app.cli grant-role --email <votre adresse> --role chef
echo $?   # 2 — rôle inconnu, les rôles existants sont nommés
```

---

## 3. Les trois issues d'une même ressource

Serveur lancé (`uv run python scripts/dev_server.py`, port dans
`.dev-backend.json`) :

```bash
PORT=$(jq -r .port ../.dev-backend.json)
URL="http://127.0.0.1:$PORT/api/v1/admin/pending-providers"

curl -s -o /dev/null -w '%{http_code}\n' "$URL"                      # 401 — anonyme
curl -s -o /dev/null -w '%{http_code}\n' -b "<cookie sans rôle>" "$URL"   # 403
curl -s -o /dev/null -w '%{http_code}\n' -b "<cookie admin>"    "$URL"    # 200
```

**Le point de la feature** : 401 et 403 sont deux réponses différentes. Un 401 au
deuxième appel dirait à quelqu'un de connecté d'aller se connecter.

---

## 4. Les deux routes destructives sont fermées

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE \
  "http://127.0.0.1:$PORT/api/v1/participations/1"                    # 401
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Content-Type: application/json' \
  -d '{}' "http://127.0.0.1:$PORT/api/v1/participations"              # 401
```

Avant cette feature, les deux répondaient sans aucune session — et le filet de
#114 **imposait** qu'elles le fassent.

---

## 5. Le signalement public n'a pas bougé

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://exemple-inconnu.fr/resultats"}' \
  "http://127.0.0.1:$PORT/api/v1/admin/pending-providers"             # 201, sans cookie
```

Puis en navigation privée : ouvrir `/ajouter`, coller une URL d'un chronométreur
inconnu, constater que le signalement part sans erreur en console.

---

## 6. Le site public, dans son entier

```bash
cd ../frontend && npm run dev
```

En navigation privée : `/`, `/dashboard`, `/resultats`, `/club`, `/carte`,
`/courses/<id>`, `/athletes/<id>`. Aucune redirection, aucun écran d'erreur.
Le test paramétré du §1 le couvre déjà route par route ; cette étape ne vérifie
que le rendu.

---

## 7. Composer un rôle à chaud — le cœur de la feature

Avec une session d'administrateur :

```bash
API="http://127.0.0.1:$PORT/api/v1/admin"

# a. l'inventaire des pouvoirs, servi depuis le code
curl -s -b "<cookie admin>" "$API/permissions" | jq '.[].feature'

# b. créer un rôle vide
curl -s -X POST -b "<cookie admin>" -H 'Content-Type: application/json' \
  -d '{"slug":"volunteer_moderator","name":"Modérateur bénévolat","permissions":[]}' \
  "$API/roles" | jq

# c. lui donner un pouvoir
curl -s -X PATCH -b "<cookie admin>" -H 'Content-Type: application/json' \
  -d '{"permissions":["quality:override"]}' "$API/roles/3" | jq

# d. l'attribuer
curl -s -X POST -b "<cookie admin>" -H 'Content-Type: application/json' \
  -d '{"role_id":3,"organisation_id":1}' "$API/users/2/roles" | jq
```

**Puis, avec la session de l'utilisateur 2 et sans qu'il se reconnecte** : il
franchit `PATCH /admin/courses/<id>/reliability` et reçoit 403 sur
`GET /admin/users`.

Retirer le pouvoir du rôle (`PATCH … {"permissions": []}`) et refaire l'appel :
**403 à la requête suivante**, toujours sans reconnexion. C'est SC-005.

### Ce qui doit être refusé

```bash
# pouvoir inexistant → 422
curl -s -X PATCH -b "<cookie admin>" -H 'Content-Type: application/json' \
  -d '{"permissions":["licorne:voler"]}' "$API/roles/3"

# rôle encore attribué → 409, avec le nombre de porteurs
curl -s -X DELETE -b "<cookie admin>" "$API/roles/3"

# rôle livré avec l'application → 409
curl -s -X DELETE -b "<cookie admin>" "$API/roles/1"
```

### Non-amplification

Avec une session portant `roles:write` **sans** `participations:delete` : tenter
d'accorder `participations:delete` à un rôle doit rendre **403**. Sans cette
règle, `roles:write` équivaut à `root`.

---

## 8. On ne peut pas fermer la porte de l'intérieur

Avec la session du **seul** administrateur, les quatre chemins doivent rendre
`409` :

```bash
curl -s -X DELETE -b "<cookie admin>" "$API/users/<son id>/roles/1"        # retrait
curl -s -X DELETE -b "<cookie admin>" "$API/roles/1"                       # suppression du rôle
curl -s -X PATCH  -b "<cookie admin>" -H 'Content-Type: application/json' \
  -d '{"is_superuser":false}' "$API/roles/1"                               # décochage
```

Nommer un second administrateur, refaire le premier : `204`.

---

## 9. Une livraison future est administrable le jour même

Ajouter temporairement un membre au catalogue **et** une garde qui le cite, puis
relancer le serveur : l'administrateur franchit la nouvelle ressource
**immédiatement**, sans migration, sans recochage. C'est `is_superuser`, et c'est
SC-006 — la vérification la plus facile à oublier de toute la feature.

---

## 10. Le pouvoir de qualité

Sur une épreuve que la machine juge **douteuse** :

```bash
curl -s -X PATCH -b "<cookie validateur>" -H 'Content-Type: application/json' \
  -d '{"reliability_override": true}' \
  "http://127.0.0.1:$PORT/api/v1/admin/courses/<id>/reliability" | jq
```

Les trois champs doivent **diverger** : `is_reliable_computed: false`,
`reliability_override: true`, `is_reliable: true`. Le verdict machine n'a pas été
écrasé, il a été recouvert.

```bash
uv run python -m app.cli rescrape-db --url "<source_url>"
```

`is_reliable` vaut toujours ce que l'humain a posé ; `is_reliable_computed` et
`quality_issues` ont été rafraîchis. Cette étape n'éprouve **aucun garde
applicatif** — il n'y en a pas : les deux chemins d'écriture ne se croisent pas.

Puis `{"reliability_override": null}` : `is_reliable` reprend immédiatement la
valeur du dernier import, pas celle qui valait au moment de la décision humaine.

---

## 11. L'écran d'administration dit « refusé »

Connecté avec un compte **sans rôle**, ouvrir `/admin`. Attendu : un message de
refus explicite. Avant correction, le tableau ne lisait que `isLoading` et
`data`, et un 403 s'affichait en « Aucun fournisseur signalé » — un écran qui
ment.

---

## 12. L'audit

```bash
uv run python -m app.cli grant-role --email <adresse> --role validator 2>&1 >/dev/null | tail -1
```

Une ligne nommant l'acteur, la cible, le rôle et le sens. Même chose dans les
logs du serveur après une création de rôle, une modification de ses pouvoirs, une
attribution et un retrait. Aucun jeton de session ne doit y figurer (FR-035).

---

## 13. Non vérifié par ce guide

- **Le comportement en PostgreSQL** : la suite tourne sur SQLite. L'index partiel
  `WHERE organisation_id IS NULL` et les contraintes sont portables, mais leur
  passage réel en production reste à faire — comme `unaccent` de #163.
- **Le multi-club** : une seule organisation existe en donnée. Aucune ressource
  n'est cloisonnée par club, aucune ne peut l'être tant qu'aucune donnée
  n'appartient à un club.
- **Les écrans d'administration des rôles** : différés à la sous-issue
  d'interface de #81. Tout se pilote ici par `curl` et par `grant-role`.
