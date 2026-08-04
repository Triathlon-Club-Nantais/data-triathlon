# Contrat HTTP — ressources d'administration

**Feature** : RBAC — rôles composables · **Révisé** : 2026-08-04 (v2)
**Base** : `/api/v1`

Chaque ressource porte sa garde **individuellement** et nomme un **pouvoir**,
jamais un rôle. Aucune n'est protégée par son préfixe.

| Route | Pouvoir exigé |
| --- | --- |
| `GET /admin/permissions` | `roles:read` |
| `GET /admin/roles` · `GET /admin/roles/{id}` | `roles:read` |
| `POST /admin/roles` · `PATCH /admin/roles/{id}` · `DELETE /admin/roles/{id}` | `roles:write` |
| `GET /admin/users` | `users:read` |
| `POST /admin/users/{user_id}/roles` · `DELETE /admin/users/{user_id}/roles/{role_id}` | `roles:assign` |
| `GET /admin/pending-providers` | `pending_providers:read` |
| `DELETE /admin/pending-providers/{entry_id}` | `pending_providers:handle` |
| `PATCH /admin/courses/{course_id}/reliability` | `quality:override` |
| `POST /participations` | `participations:write` |
| `DELETE /participations/{participation_id}` | `participations:delete` |
| **`POST /admin/pending-providers`** | **aucun — signalement public anonyme** |

Les deux avant-dernières lignes ferment une anomalie : ces routes sont
aujourd'hui **ouvertes à Internet** et permettent de créer et supprimer des
résultats sans aucune authentification.

La dernière est le fait de terrain qui interdit toute garde par préfixe : elle
est appelée par `ScrapeForm.tsx` et `TcnScrapeForm.tsx`, en `.catch(() => {})`,
quand un visiteur anonyme colle une URL non supportée.

---

## Réponses d'erreur communes

| Statut | Quand | Corps |
| --- | --- | --- |
| `401` | Aucune session valide (absente, expirée, compte désactivé) | `{"detail": "Vous devez être connecté pour accéder à cette ressource."}` |
| `403` | Session valide, pouvoir absent | `{"detail": "Vous n'avez pas les droits nécessaires pour cette action."}` |
| `404` | Ressource absente | `{"detail": "Ressource introuvable"}` |
| `409` | L'état de la ressource s'oppose à l'opération (voir chaque route) | message français explicite |
| `422` | Corps invalide, pouvoir hors catalogue | forme FastAPI habituelle |

**401 et 403 ne se confondent jamais** : la garde de pouvoir compose la
dépendance de session, donc une requête sans session ne l'atteint pas. L'ordre
est structurel, pas défensif.

Le message de 403 ne nomme ni le pouvoir exigé ni ceux portés (FR-019).

---

## `GET /admin/permissions`

L'inventaire de ce que l'application sait vérifier. **Servi depuis le code**,
jamais depuis une table : c'est ce qui garantit qu'un pouvoir livré aujourd'hui
est proposé aujourd'hui, sans migration.

```json
[
  {
    "feature": "Chronométreurs signalés",
    "permissions": [
      {
        "code": "pending_providers:read",
        "label": "Consulter les signalements",
        "description": "Voir la liste des chronométreurs non supportés signalés par les visiteurs."
      }
    ]
  }
]
```

Groupé par fonctionnalité, ordonné pour l'affichage. Les `code` sont des
identifiants techniques anglais et stables — ils traversent la base ; `feature`,
`label` et `description` sont du français d'affichage.

---

## `GET /admin/roles` · `GET /admin/roles/{id}`

```json
{
  "id": 2,
  "organisation_id": null,
  "slug": "validator",
  "name": "Validateur",
  "description": "Tranche la fiabilité des épreuves douteuses.",
  "is_system": true,
  "is_superuser": false,
  "permissions": ["quality:override"],
  "stale_permissions": [],
  "holders": 3
}
```

`organisation_id: null` = rôle partagé par toutes les organisations.
`stale_permissions` liste les codes présents en base mais absents du catalogue —
inertes, purgeables, jamais bloquants.

---

## `POST /admin/roles`

**Requête** : `{"slug": "volunteer_moderator", "name": "Modérateur bénévolat", "description": "", "organisation_id": null, "permissions": []}`

**201** — le rôle au format ci-dessus.

| Erreur | Statut |
| --- | --- |
| `slug` déjà pris dans cette portée | `409` |
| Un code de `permissions` hors catalogue | `422` |
| Un code que l'appelant ne porte pas lui-même | `403` |
| `is_superuser: true` demandé par un non-superutilisateur | `403` |

La quatrième ligne est la règle de **non-amplification** (FR-011) : sans elle,
`roles:write` équivaut à `root` — quiconque édite les rôles se fabrique en trois
clics celui qui peut tout. Elle est sans effet pour un superutilisateur, qui
porte déjà tout, et c'est précisément ce qui rend la délégation possible.

---

## `PATCH /admin/roles/{id}`

**Requête** — champs tous facultatifs :
`{"name": "…", "description": "…", "permissions": ["…"], "is_superuser": false}`

`permissions` **remplace** l'ensemble. **200**, rôle à jour.

| Erreur | Statut |
| --- | --- |
| `slug` soumis à modification | `422` — le slug est immuable |
| Pouvoir hors catalogue | `422` |
| Pouvoir non porté par l'appelant (ajout **ou** retrait) | `403` |
| `is_superuser` modifié par un non-superutilisateur | `403` |
| Retrait de `is_superuser` laissant l'organisation sans administrateur actif | `409` |

**Le changement s'applique à la requête suivante de tous les porteurs**, sans
reconnexion (FR-016).

---

## `DELETE /admin/roles/{id}`

**204**.

| Erreur | Statut | Corps |
| --- | --- | --- |
| Rôle encore attribué | `409` | `{"detail": "Ce rôle est porté par 3 utilisateurs. Retirez-le d'abord."}` |
| `is_system` | `409` | `{"detail": "Ce rôle est livré avec l'application et ne peut pas être supprimé."}` |

Pas de cascade : supprimer un rôle qui dépouille silencieusement trois personnes
est exactement ce qu'on rend explicite.

---

## `GET /admin/users`

```json
[
  {
    "id": 1,
    "email": "prenom.nom@example.org",
    "display_name": "Prénom Nom",
    "is_active": true,
    "roles": [{"id": 1, "slug": "admin", "name": "Administrateur", "organisation_id": 1}],
    "created_at": "2026-08-01T09:12:33"
  }
]
```

Sans pagination : le peuplement d'`users` est borné par `AUTH_ALLOWED_EMAILS`.

---

## `POST /admin/users/{user_id}/roles`

**Requête** : `{"role_id": 2, "organisation_id": 1}`. **Idempotent** — réattribuer
est un succès.

**201**, l'utilisateur à jour.

| Erreur | Statut |
| --- | --- |
| Utilisateur ou rôle inconnu | `404` |
| Rôle propre à une autre organisation | `422` |
| L'appelant ne porte pas tous les pouvoirs du rôle attribué | `403` |

---

## `DELETE /admin/users/{user_id}/roles/{role_id}`

**204**. Idempotent.

| Erreur | Statut | Corps |
| --- | --- | --- |
| L'organisation y perdrait son dernier administrateur actif | `409` | `{"detail": "Cette opération laisserait l'installation sans aucun administrateur."}` |

Le `409` porte sur l'état de la ressource : l'appelant *est* administrateur, sa
requête est bien formée, c'est le résultat qui est interdit.

---

## `PATCH /admin/courses/{course_id}/reliability`

| Corps | Effet |
| --- | --- |
| `{"reliability_override": true}` | L'épreuve est déclarée fiable par un humain. |
| `{"reliability_override": false}` | Déclarée douteuse par un humain. |
| `{"reliability_override": null}` | **Lève** l'avis humain ; l'épreuve reprend son verdict calculé, à jour. |

**200** :

```json
{
  "id": 42,
  "is_reliable": true,
  "is_reliable_computed": false,
  "reliability_override": true,
  "quality_issues": {"rank_gap": 3}
}
```

Les trois valeurs sont rendues délibérément : « la machine a relevé trois trous
de classement et doute ; un humain a tranché que l'épreuve est fiable ». C'est ce
qu'une interface de revue doit montrer, et ce qu'une valeur unique rendrait
indicible. Ces deux champs supplémentaires n'apparaissent **que** sur cette
route.

---

## Routes existantes modifiées

| Route | Avant | Après |
| --- | --- | --- |
| `GET /admin/pending-providers` | ouverte | `pending_providers:read` |
| `DELETE /admin/pending-providers/{id}` | ouverte | `pending_providers:handle` |
| `POST /admin/pending-providers` | ouverte | **ouverte** |
| `POST /participations` | **ouverte** | `participations:write` |
| `DELETE /participations/{id}` | **ouverte** | `participations:delete` |
| `GET /auth/me` | session + utilisateur | **+ `permissions`** (liste de codes) |

`GET /auth/me` est enrichi de façon **additive** (FR-020) : sans lui, une
interface ne peut distinguer « connecté sans droit » d'« administrateur » qu'en
collectant des 403. Aucun champ existant ne change.

Aucune autre route n'est touchée : les six pages publiques en rendu serveur,
l'import SSE, la détection de fournisseur, les statistiques et les classements
restent intacts (FR-024).

**Au regard du Principe IV** : aucun champ retiré, aucune sémantique inversée.
Quatre routes passent d'ouvertes à protégées — c'est l'objet de la feature, et
deux d'entre elles fermaient une anomalie de sécurité.
