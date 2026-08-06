# Quickstart — vérifier les groupes d'appartenance de bout en bout

**Feature** : groupes d'appartenance (#197) · **Créé** : 2026-08-06

Guide de **validation**, pas d'implémentation. Contrat :
[`contracts/admin-groups-api.md`](contracts/admin-groups-api.md) · Modèle :
[`data-model.md`](data-model.md).

## Prérequis

```bash
cd backend && uv sync && uv run alembic upgrade head
```

Les réglages `AUTH_*` de #114 doivent être en place pour les étapes 3 et
suivantes. Rappel du piège multi-worktree : une application OAuth GitHub
n'accepte qu'une seule URL de retour, port compris — ces étapes ne se déroulent
que depuis l'espace de travail principal.

---

## 1. La suite passe, et **deux filets de #115 sont restés verts sans être touchés**

```bash
uv run pytest -m "not integration"
```

C'est le point de contrôle le plus important de la feature :

- `test_permissions_catalogue.py` — paramétré sur `permissions.ALL`, il compte
  désormais **trois cas de plus**, un par pouvoir neuf, et exige que chacun garde
  une ressource. Aucune ligne du fichier n'a bougé. Pour l'éprouver : commenter
  la garde de `GET /admin/groups` doit faire rougir `groups:read` **en le
  nommant**.
- `test_public_routes_still_open.py` — ses sept routes de plus sont classées
  « gardées » par la seule règle du préfixe `/api/v1/admin/`. Aucune ligne du
  fichier n'a bougé, et `ADMIN_PUBLIQUES` compte toujours **une** entrée. Pour
  l'éprouver : retirer une garde doit faire rougir la suite en nommant la route.

```bash
git diff --stat main -- tests/test_permissions_catalogue.py \
                        tests/test_auth/test_public_routes_still_open.py
# attendu : aucune sortie
```

---

## 2. Le schéma appliqué, et la migration jouée sur base vierge

```bash
uv run pytest tests/test_migrations.py
uv run python - <<'PY'
import sqlalchemy as sa
from app.core.config import get_settings
inspecteur = sa.inspect(sa.create_engine(get_settings().database_url))
print(sorted(c["name"] for c in inspecteur.get_columns("groups")))
print(sorted(c["name"] for c in inspecteur.get_columns("user_groups")))
print([i["name"] for i in inspecteur.get_indexes("groups")])
PY
```

Attendu : `groups` porte `created_at, description, id, name, organisation_id,
slug` — **ni `is_superuser`, ni `is_system`, ni `parent_id`** ; `user_groups`
porte `group_id, id, joined_at, user_id` — **pas d'`organisation_id`**.

---

## 3. Les trois issues d'une ressource de groupe

Serveur lancé (`uv run python scripts/dev_server.py`, port dans
`.dev-backend.json`) :

```bash
PORT=$(jq -r .port ../.dev-backend.json)
URL="http://127.0.0.1:$PORT/api/v1/admin/groups"

curl -s -o /dev/null -w '%{http_code}\n' "$URL"                        # 401 — anonyme
curl -s -o /dev/null -w '%{http_code}\n' -b "<cookie sans rôle>" "$URL"  # 403
curl -s -o /dev/null -w '%{http_code}\n' -b "<cookie admin>"     "$URL"  # 200
```

401 et 403 restent deux réponses différentes — la garde des groupes n'invente
rien, elle compose `current_user` comme les sept de #115.

---

## 4. Le cycle de vie complet d'un groupe

```bash
ADMIN='-b <cookie admin> -H Content-Type:application/json'

# créer — naît vide
curl -s $ADMIN -X POST "$URL" -d '{"slug":"codir","name":"Codir"}' | jq '.member_count'
# 0

# renommer — aucune appartenance perdue
curl -s $ADMIN -X PATCH "$URL/1" -d '{"name":"Comité de direction"}' | jq '.name'

# le slug ne se renomme pas
curl -s -o /dev/null -w '%{http_code}\n' $ADMIN -X PATCH "$URL/1" -d '{"slug":"autre"}'
# 422 — extra="forbid", jamais un silence

# ajouter un membre, deux fois — idempotent
curl -s -o /dev/null -w '%{http_code}\n' $ADMIN -X POST "$URL/1/members" -d '{"user_id":1}'  # 201
curl -s $ADMIN -X POST "$URL/1/members" -d '{"user_id":1}' | jq '.member_count'              # 1

# le détail nomme ses membres — c'est la capacité qui justifie l'objet
curl -s $ADMIN "$URL/1" | jq '.members[].email'

# supprimer un groupe peuplé — refusé, et le nombre est dans le message
curl -s $ADMIN -X DELETE "$URL/1" | jq -r '.detail'
# « Ce groupe compte 1 membre. Retirez-le d'abord. » — accord au singulier compris

# le vider est libre — aucun invariant du dernier membre
curl -s -o /dev/null -w '%{http_code}\n' $ADMIN -X DELETE "$URL/1/members/1"   # 204
curl -s -o /dev/null -w '%{http_code}\n' $ADMIN -X DELETE "$URL/1/members/1"   # 204 — idempotent
curl -s -o /dev/null -w '%{http_code}\n' $ADMIN -X DELETE "$URL/1"             # 204
```

---

## 5. **Un groupe n'accorde rien** — la borne de la v1

Avec une session d'un utilisateur **sans aucun rôle**, membre de tous les groupes :

```bash
SANS_ROLE='-b <cookie sans rôle>'
curl -s $SANS_ROLE "http://127.0.0.1:$PORT/api/v1/auth/me" | jq '.groups, .permissions'
# les groupes sont là ; permissions vaut []

curl -s -o /dev/null -w '%{http_code}\n' $SANS_ROLE \
  "http://127.0.0.1:$PORT/api/v1/admin/pending-providers"
# 403 — exactement comme avant l'appartenance
```

C'est AC6 vu de l'extérieur. Sa version qui ne s'oublie pas est
`tests/test_auth/test_groups_grant_nothing.py`, dont le volet AST rougira le jour
où la v2 branchera les rôles d'un groupe sur la décision d'accès —
**au bon moment**, et il faudra le supprimer sciemment.

---

## 6. L'enrichissement de `/auth/me` est bien additif

```bash
curl -s -b "<cookie admin>" "http://127.0.0.1:$PORT/api/v1/auth/me" | jq 'keys'
# ["created_at","display_name","email","groups","id","permissions","roles"]
```

Un consommateur existant ne voit rien changer : aucun champ retiré, aucune
sémantique inversée, aucun code de retour modifié (Principe IV).

---

## 7. Ce qui reste à vérifier ailleurs

- **La migration sur PostgreSQL.** `tests/test_migrations.py` n'applique la
  chaîne que sur SQLite. Le nom de table `groups` a été vérifié non réservé
  contre le dialecte PostgreSQL de SQLAlchemy (`research.md` §D3), mais le
  premier `alembic upgrade head` réel reste le seul juge. `autoDeploy: false` :
  il se déroule sous les yeux d'un humain.
- **Aucun écran.** Le frontend n'est pas touché ; `npm test` et `npm run build`
  n'ont rien de neuf à couvrir. Les écrans relèvent de l'épique #81.
