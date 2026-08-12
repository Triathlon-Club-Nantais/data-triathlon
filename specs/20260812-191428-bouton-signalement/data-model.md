# Data Model: Bouton de signalement (bug / feedback)

## `UserFeedback` (table `user_feedback`)

Un signalement unique, créé publiquement, instruit côté admin.

| Champ | Type | Contrainte | Notes |
|---|---|---|---|
| `id` | `int` | PK | |
| `type` | `str` | NOT NULL, dans `{"bug", "feedback"}` | Constante applicative, même patron que `Course.event_type` (chaîne nue, nomenclature en Python — pas de table de référence pour deux valeurs fixes). |
| `title` | `str` | NOT NULL, longueur bornée (ex. 200) | Validé côté schéma Pydantic, pas de contrainte SQL supplémentaire. |
| `body` | `text` | NOT NULL, longueur bornée (ex. 10 000) | Multi-lignes. |
| `page_url` | `str \| null` | | Peut être vide (cf. Edge Cases de la spec — page sans URL exploitable). |
| `user_agent` | `str \| null` | | Tel que reçu du navigateur, non interprété. |
| `ip_address` | `str \| null` | index avec `created_at` | **Jamais exposé** par un schéma de lecture (research.md §D4) — sert uniquement `count_recent_by_ip`. |
| `user_id` | `int \| null` | FK `users.id`, `ON DELETE SET NULL` | Renseigné seulement si l'émetteur était connecté au moment de l'envoi (SSO, #114). |
| `status` | `str` | NOT NULL, défaut `"nouveau"`, dans `{"nouveau", "en_cours", "traite", "ignore"}` | Transition libre entre les quatre valeurs (pas de machine à états stricte — la spec ne demande pas d'interdire un retour en arrière). |
| `github_url` | `str \| null` | | Renseignée manuellement par un administrateur après création de l'issue/discussion sur GitHub (aucune écriture automatique). |
| `created_at` | `datetime` | NOT NULL, défaut serveur | |

**Index** : `(status, created_at)` pour le tri par défaut de la liste admin ;
`(ip_address, created_at)` pour la requête de limitation de débit.

**Pas de contrainte d'unicité** : deux signalements identiques (même page,
même utilisateur) sont deux lignes distinctes — contrairement à `Athlete` /
`Course` / `Participation`, un signalement n'est pas une entité déduplicable
par nature (un même bug peut être signalé deux fois, légitimement).

## Relation avec `User` (#114)

`user_id` est une clé étrangère **nullable**, jamais l'inverse : `User` ne
porte aucune référence vers ses signalements (pas de besoin métier identifié
— l'admin parcourt les signalements, pas un historique par utilisateur). Le
même choix que #115 pour `users` : ne pas ajouter de colonne relative à un
usage tant qu'aucun besoin ne l'exige (cf. `backend/app/services/auth/
AGENTS.md`, « `users` ne porte aucun rôle »).

## Migration Alembic

Une seule révision : `create_table("user_feedback", ...)` + les deux index.
Aucune modification de table existante. `ip_address` et `user_agent` sont
`String` sans longueur contrainte en base (SQLite/Postgres), la validation de
longueur reste au niveau Pydantic pour `title`/`body` (cohérent avec le choix
déjà fait pour d'autres champs texte du dépôt, ex. `PendingProvider.url`).

## États du statut

```
nouveau → en_cours → traite
   │         │
   └────────→ ignore
```

Toutes les transitions sont autorisées dans les deux sens par `PATCH
/admin/feedback/{id}` — la spec ne demande pas de verrou directionnel, et un
admin qui rouvre un signalement « traité » par erreur doit pouvoir revenir en
arrière sans détour.
