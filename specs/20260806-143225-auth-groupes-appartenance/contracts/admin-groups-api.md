# Contrat — `/api/v1/admin/groups` et l'enrichissement de `/auth/me` (#197)

Sept ressources neuves, **sept gardes individuelles** — jamais une garde de
router ni de préfixe (FR-018 de #115 : `POST /admin/pending-providers` est le
signalement anonyme du site public, sous le même préfixe).

Codes de retour communs à toutes les ressources d'administration :

| Code | Quand |
| --- | --- |
| `401` | aucune session valide. **Toujours avant le 403** — la garde compose `current_user`. |
| `403` | session valide, pouvoir absent. Le corps ne nomme ni le pouvoir exigé ni ceux portés (FR-019 de #115). |
| `404` | groupe ou utilisateur inexistant. |
| `422` | corps invalide (slug malformé, champ inconnu, `slug` soumis en `PATCH`). |

---

## `GET /admin/groups` — la liste

**Pouvoir** : `groups:read`. Aucun paramètre. Pas de pagination (`users` est borné
par `AUTH_ALLOWED_EMAILS`, les groupes d'un club se comptent sur les doigts).

```json
[
  {
    "id": 1,
    "organisation_id": 1,
    "slug": "codir",
    "name": "Codir",
    "description": "Comité de direction élu au CA.",
    "member_count": 7,
    "created_at": "2026-08-06T14:32:25Z"
  }
]
```

Trié par `slug`, comme `GET /admin/roles`. `member_count` évite un aller-retour
par groupe pour afficher une liste ; il ne remplace pas le détail.

---

## `GET /admin/groups/{group_id}` — le détail et ses membres

**Pouvoir** : `groups:read`. C'est **la** ressource qui porte FR-012, la capacité
qui justifie l'objet entier : « liste-moi les membres du Codir ».

```json
{
  "id": 1,
  "organisation_id": 1,
  "slug": "codir",
  "name": "Codir",
  "description": "Comité de direction élu au CA.",
  "member_count": 2,
  "created_at": "2026-08-06T14:32:25Z",
  "members": [
    {
      "user_id": 3,
      "email": "president@example.org",
      "display_name": "Camille Roux",
      "is_active": true,
      "joined_at": "2026-08-06T15:02:11Z"
    }
  ]
}
```

Membres triés par `display_name` puis `email` — un ordre d'affichage stable, pas
l'ordre d'insertion. `is_active` est rendu : un compte désactivé **reste membre**
(spec §Edge Cases), et un écran qui l'ignorerait afficherait un Codir faux.

---

## `POST /admin/groups` — créer

**Pouvoir** : `groups:write`. **201.**

```json
{ "slug": "arbitres", "name": "Arbitres", "description": "", "organisation_id": null }
```

- `slug` — requis, `^[a-z][a-z0-9-]*$`, **fixé une fois pour toutes** ;
- `name` — requis, non vide ;
- `description` — facultatif, défaut `""` ;
- `organisation_id` — facultatif : **le seul club** en base à défaut, comme
  `POST /admin/users/{id}/roles`. La colonne, elle, est non nulle. Un
  identifiant de club **inexistant** rend **422** : le contrôle est fait en
  Python et non laissé au moteur, `core/database.py` n'émettant aucun
  `PRAGMA foreign_keys=ON` — la clé étrangère passerait en SQLite et lèverait en
  PostgreSQL.

`extra="forbid"` : un champ inconnu est un **422**, jamais un silence.

**409** si le couple `(organisation_id, slug)` est déjà pris. Le contrôle est
fait en lecture **et** rattrapé sur l'`IntegrityError`, le point de reprise
entourant l'**écriture** : sous concurrence, deux exploitants franchissent tous
deux la lecture, et seule la contrainte tranche.

Rend le **détail** (`members: []`), comme `PATCH` et l'ajout d'un membre : les
trois gestes qui portent sur un groupe précis rendent la même forme. Le groupe
naît **vide** (FR-004) — `member_count: 0`.

---

## `PATCH /admin/groups/{group_id}` — renommer, décrire

**Pouvoir** : `groups:write`. Rend le détail, code **200**.

```json
{ "name": "Comité de direction", "description": "Élu au CA." }
```

Les deux champs sont facultatifs et indépendants. **Aucune appartenance n'est
perdue** (FR-006). `slug` et `organisation_id` sont absents du DTO : les soumettre
rend **422** (`extra="forbid"`) plutôt que d'être ignorés en silence.

---

## `DELETE /admin/groups/{group_id}` — supprimer

**Pouvoir** : `groups:write`. **204** si le groupe est vide.

**409 s'il compte encore des membres**, et le nombre est **dans le message** —
« conflit » ne se corrige pas :

```json
{ "detail": "Ce groupe compte 7 membres. Retirez-les d'abord." }
```

L'accord suit le nombre (`1 membre. Retirez-le`), comme le 409 de suppression
d'un rôle porté.

Aucune cascade : le refus est la règle, pas un garde-fou de dernière minute
(`data-model.md` §Relations et cascades). Vider le groupe est libre et sans
aucune restriction — il n'existe pas d'invariant du dernier membre (FR-019).

---

## `POST /admin/groups/{group_id}/members` — ajouter un membre

**Pouvoir** : `groups:assign`. **201**, rend le détail du groupe.

```json
{ "user_id": 3 }
```

**Idempotent** (FR-008) : réajouter un membre est un **succès**, sans doublon et
sans erreur exposée. Aucune règle de non-amplification n'est appliquée — il n'y a
aucun pouvoir à amplifier (FR-018).

**404** si l'utilisateur n'existe pas. Un compte **désactivé** est un membre
parfaitement légitime : rien de ce que porte un groupe ne dépend de son activité.

---

## `DELETE /admin/groups/{group_id}/members/{user_id}` — retirer un membre

**Pouvoir** : `groups:assign`. **204**, y compris si la personne n'était pas
membre — idempotent dans les deux sens, patron de `revoke_role`.

Ne retire **rien d'autre** : ni session, ni rôle, ni autre appartenance (FR-009).

---

## `GET /auth/me` — enrichissement additif

**Aucun pouvoir exigé** : la lecture ne porte que sur soi. Le champ `groups`
s'ajoute à côté de `permissions` et `roles`, posés par #115 au même endroit et
pour la même raison.

```json
{
  "id": 3,
  "email": "president@example.org",
  "display_name": "Camille Roux",
  "created_at": "2026-07-02T09:14:00Z",
  "permissions": ["groups:read"],
  "roles": [{ "id": 2, "slug": "moderator", "name": "Modérateur", "organisation_id": 1 }],
  "groups": [{ "id": 1, "slug": "codir", "name": "Codir", "organisation_id": 1 }]
}
```

**Additif au sens du Principe IV** : aucun champ retiré, aucune sémantique
inversée, aucun code de retour modifié. Un consommateur existant ne voit
strictement rien changer. `groups` vaut `[]` pour qui n'appartient à rien — état
normal, celui de tout le monde sur une installation neuve.

**Le champ ne dit rien des droits.** Il sert à écrire « membre du Codir » ; c'est
`permissions` qui répond à « ai-je le droit d'afficher ce bouton ». Les confondre
serait faire entrer les groupes dans la décision d'accès **côté interface**, ce
que FR-016 refuse côté serveur.

---

## Ce que ce contrat n'offre pas

- **Aucune ressource ne rend « les groupes de tel utilisateur »** : `GET /auth/me`
  le fait pour soi, `GET /admin/users` (#115) le fera pour autrui le jour où
  quelqu'un le demandera. Une route de plus sans lecteur serait un pouvoir de
  plus à garder.
- **Aucune ressource ne remplace l'ensemble des membres d'un coup.**
  `PATCH {"members": […]}` serait le pendant de la recomposition d'un rôle, mais
  personne n'en a l'usage : on ajoute et on retire une personne à la fois.
- **Aucune ressource publique.** Les sept exigent un pouvoir, et le filet de #115
  le vérifie sans qu'on ait à les nommer.
