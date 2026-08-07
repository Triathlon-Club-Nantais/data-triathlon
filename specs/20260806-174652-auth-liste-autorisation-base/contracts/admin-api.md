# Contrat API — les accès au back-office

Trois ressources sous `/api/v1/admin/allowed-emails`, montées par
`app/api/v1/admin_allowed_emails.py`. **Chacune porte sa garde individuellement**
— aucune garde de préfixe : `admin.py` monte, sous le même `/admin/`, le
signalement anonyme du site public, et une garde de router le supprimerait sans
que rien ne le nomme (#115).

Le pouvoir exigé est le même pour les trois : **`allowed_emails:manage`**. Le
rôle `admin`, superutilisateur, le franchit sans qu'aucune donnée soit à
modifier.

## Représentation

```json
{
  "id": 12,
  "email": "contributeur@exemple.fr",
  "created_at": "2026-08-06T15:12:03",
  "created_by_name": "Camille Durand"
}
```

`created_by_name` est le nom d'affichage de la personne qui a inscrit l'adresse,
ou `null` quand l'inscription vient de la CLI ou de la reprise de production.
Le suffixe `_name` n'est pas décoratif : la colonne s'appelle
`created_by_user_id`, et un champ `created_by` nu se lirait comme l'identifiant
qu'il n'est pas. C'est un **nom** que l'écran affiche, rien ne le suit.

`email` est toujours rendu normalisé (minuscules, sans espaces de bordure),
quelle que soit la casse de la saisie.

## `GET /api/v1/admin/allowed-emails`

Rend la liste entière, triée par adresse. **Sans pagination** : le peuplement est
borné par la taille d'un club (quelques dizaines d'entrées).

| Cas | Statut | Corps |
| --- | --- | --- |
| Porteur du pouvoir | `200` | `[AllowedEmail]`, possiblement vide |
| Anonyme | `401` | `{"detail": …}` |
| Connecté sans le pouvoir | `403` | `{"detail": …}` |

L'ordre **401 avant 403** est structurel : la garde compose `current_user`, une
requête sans session n'atteint jamais le contrôle de pouvoir.

Une liste vide est une réponse **valide** — elle signifie « personne n'est
autorisé », et l'interface l'affiche comme telle. Elle ne se confond pas avec un
refus : le composant distingue `401`, `403` et « liste vide », comme
`PendingProvidersTable` a dû apprendre à le faire.

## `POST /api/v1/admin/allowed-emails`

```json
{ "email": "Contributeur@Exemple.FR " }
```

**Idempotent** : réinscrire une adresse déjà présente est un succès et ne crée
pas de doublon — même parti pris que `POST /admin/users/{id}/roles` en #115.

| Cas | Statut | Corps |
| --- | --- | --- |
| Adresse inscrite | `201` | `AllowedEmail` |
| Adresse déjà présente | `201` | `AllowedEmail` existant, inchangé |
| Adresse mal formée | `422` | `{"detail": …}` en français |
| Anonyme / sans le pouvoir | `401` / `403` | `{"detail": …}` |

**Effet de bord contractuel** : les comptes portant cette adresse repassent à
`is_active = True`. Sans quoi une réinscription n'ouvrirait rien — un compte
désactivé est refusé en `account_not_allowed` avant même la lecture de la liste.

## `DELETE /api/v1/admin/allowed-emails/{id}`

Par identifiant, pas par adresse : une adresse dans un chemin d'URL impose un
échappement à chaque appelant, pour un gain nul.

| Cas | Statut | Corps |
| --- | --- | --- |
| Adresse retirée | `204` | — |
| Identifiant inconnu | `204` | — (idempotent, comme la révocation de rôle) |
| Perte du dernier administrateur actif | `409` | `{"detail": …}` |
| Anonyme / sans le pouvoir | `401` / `403` | `{"detail": …}` |

**Effet de bord contractuel** : les comptes portant cette adresse passent à
`is_active = False`, ce qui ferme **immédiatement** toutes leurs sessions —
l'invariant de validité de session est une jointure, jamais un cache. Ni
l'utilisateur, ni ses rôles, ni son historique ne sont supprimés : le geste est
réversible par une réinscription.

**Le `409` et non un `403`** : l'appelant *est* administrateur et sa requête est
bien formée ; c'est le **résultat** qui est interdit. La garde est le
gestionnaire de contexte `authorization.administrateurs_preserves(db)` de #115,
appelé **sans** organisation — donc sur toutes —, et non une règle nouvelle du
type « on ne retire pas sa propre adresse » (voir `research.md` R5).

## Ce que le contrat n'expose pas

- **Aucune modification d'une entrée.** On inscrit, on retire ; corriger une
  faute de frappe, c'est retirer puis inscrire. Un `PATCH` sur une table à une
  colonne utile n'a pas d'objet.
- **Aucune recherche, aucun tri, aucune pagination** — voir la borne de volume.
- **Aucune ressource ne rend les tentatives refusées** : elles ne sont pas en
  base (hors périmètre).

## Ce que les tests existants exigent

- `tests/test_auth/test_public_routes_still_open.py` : toute ressource sous
  `/api/v1/admin/` est **gardée** ou **déclarée publique nommément**. Les trois
  ci-dessus sont gardées, aucune déclaration à ajouter.
- `tests/test_permissions_catalogue.py` (méta-test AST) : un pouvoir du catalogue
  garde au moins une ressource, et aucune garde ne cite un code hors catalogue.
  `allowed_emails:manage` en garde trois.
- Le méta-test AST de #115 interdit toute écriture directe dans les tables de
  rôles depuis un router. Le router de cette feature ne touche **aucune** table :
  il délègue à `services/auth/allowed_emails.py`.
