# Contract: API des retours utilisateurs

Quatre routes, **deux préfixes, et c'est le chemin qui dit qui peut appeler** :
la soumission est publique et vit sous `/api/v1/feedback`
(`app/api/v1/feedback.py`) ; la consultation et l'instruction vivent sous
`/api/v1/admin/feedback` (`app/api/v1/admin_feedback.py`), où rien n'est
public. Décidé en revue de #315 : un verbe public sous `/admin` se lit comme
une garde oubliée.

## `POST /feedback` — publique, aucune authentification requise

**Request body** (`FeedbackCreate`):

```json
{
  "type": "bug",
  "title": "Le classement n'affiche pas mon temps",
  "body": "Après l'import de l'épreuve X, mon temps total reste vide.",
  "page_url": "https://tcn.example/courses/123",
  "user_agent": "Mozilla/5.0 ...",
  "honeypot": ""
}
```

- `type` : `"bug"` ou `"feedback"`, requis.
- `title`, `body` : requis, non vides, longueur bornée (422 sinon).
- `page_url`, `user_agent` : optionnels.
- `honeypot` : optionnel, doit être vide ou absent. S'il est renseigné, la
  réponse est identique à un succès mais rien n'est persisté (research.md §D2).
- L'email de l'émetteur n'est **jamais** un champ du corps de la requête : il
  est déduit côté serveur de la session SSO courante (cookie), jamais déclaré
  par le client.

**Response** : `201`, `FeedbackRead` minimal (`id`, `status`) — ou la même
forme sans persistance réelle si le honeypot a été déclenché.

**Erreurs** :
- `422` — champs requis manquants ou trop longs.
- `429` — seuil de limitation de débit par IP dépassé (FR-011). Corps
  `{"detail": "Trop de signalements envoyés récemment, réessayez plus tard."}`
  (français utilisateur, `DomainError`).

## `GET /admin/feedback` — garde `FEEDBACK_READ`

Liste des signalements. Paramètres de tri : `sort` parmi `created_at`, `type`,
`status` (défaut `created_at` descendant), `order` parmi `asc`/`desc`. Pas de
pagination dans cette v1 (volume attendu modeste, cf. plan.md §Scale/Scope) —
cohérent avec le Principe VI, à revisiter si le volume réel le justifie.

**Response** : liste de `FeedbackRead` (sans `ip_address`, cf. data-model.md).

## `GET /admin/feedback/{id}` — garde `FEEDBACK_READ`

Détail complet d'un signalement (`FeedbackRead` : titre, description, type,
statut, `page_url`, `user_agent`, email de l'émetteur si `user_id` est
renseigné, `github_url`, `created_at`). `404` si absent.

## `PATCH /admin/feedback/{id}` — garde `FEEDBACK_MANAGE`

**Request body** (`FeedbackUpdate`, champs modifiés seulement — même
convention que `PATCH /admin/roles/{id}`) :

```json
{ "status": "traite" }
```

ou

```json
{ "github_url": "https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/321" }
```

Les deux champs peuvent être envoyés ensemble ou séparément. `404` si le
signalement n'existe pas ; `422` si `status` n'est pas une des quatre valeurs
autorisées ou si `github_url` n'est pas une URL valide.

**Response** : `FeedbackRead` mis à jour.

## Ce que le contrat n'inclut PAS (hors périmètre v1)

- Aucune route n'appelle l'API GitHub ni n'en dépend pour répondre.
- Aucune notification (email, webhook) n'est envoyée à la création d'un
  signalement.
- Aucune pagination ni filtre serveur au-delà du tri (FR-009 ne demande que le
  tri, pas le filtrage).
