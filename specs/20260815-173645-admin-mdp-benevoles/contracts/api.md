# Contrats API — Gestion admin du mot de passe partagé bénévoles

Nouveau routeur `app/api/v1/admin_benevole_access.py`, sur le patron
d'`admin_sessions.py`/`admin_allowed_emails.py` — un module par capacité
distincte du regroupement « Rôles et accès ». Garde : `require_permission(P.BENEVOLE_ACCESS_MANAGE)`
sur les trois routes, route par route (jamais par préfixe, cf.
`backend/app/api/AGENTS.md`).

## GET /api/v1/admin/benevoles/access

État courant de la configuration — **jamais le mot de passe ni son
empreinte**.

- Garde : `benevole_access:manage`.
- Réponse : `{"configured": bool, "updated_at": string | null, "updated_by": string | null}`.
  `updated_by` est le `display_name` de l'administrateur (résolu par
  jointure, même patron que `UserFeedback.user` dans `admin_feedback.py`) —
  jamais un `user_id` nu.
- 200 dans tous les cas, y compris si la configuration n'a jamais existé
  (`configured: false`, les deux autres champs à `null`) — pas une erreur,
  un état normal avant le tout premier réglage.

## PUT /api/v1/admin/benevoles/access

Remplace le mot de passe par une valeur saisie par l'administrateur
(Story 1).

- Garde : `benevole_access:manage`.
- Requête : `{"password": string}` — une contrainte de longueur minimale
  s'applique (cf. `data-model.md`/tâches, pas un détail de contrat de haut
  niveau), validée par le schéma Pydantic, jamais par le service.
- 200, même forme que `GET` (état après remplacement — jamais le mot de
  passe fourni, qui n'est ni renvoyé ni consigné).
- Invalide immédiatement toutes les sessions bénévoles ouvertes (research.md
  §D2) : le `session_secret` est régénéré dans le même geste que le
  hachage.

## POST /api/v1/admin/benevoles/access/generate

Génère un mot de passe sécurisé côté serveur (Story 2) — **seule route qui
renvoie jamais un mot de passe en clair**, et seulement dans cette réponse.

- Garde : `benevole_access:manage`.
- Pas de corps de requête.
- 200, `{"password": string, "updated_at": string, "updated_by": string}` —
  le mot de passe généré, en clair, **une seule fois** (FR-003). Rien côté
  serveur ne le conserve après cette réponse ; une requête `GET` immédiatement
  après ne le retrouve pas.
- Même effet secondaire que `PUT` : rotation du `session_secret`, entrée au
  journal d'audit.

## Ce qui ne change pas pour un bénévole

`POST /api/v1/benevoles/session`, `DELETE /api/v1/benevoles/session`, et les
quatre routes gardées de `benevoles.py` (#271) gardent exactement le même
contrat externe (FR-008) — seule la source de vérité du mot de passe et de
la clé de signature change, en interne.

## Hors contrat de cette feature

- Aucune route ne permet de retrouver un mot de passe déjà remplacé, sous
  quelque forme que ce soit (FR-004).
- Aucune route de suppression de la configuration (revenir à « non
  configuré » après avoir été configuré une fois) — non demandé par la
  spec ; un administrateur qui veut fermer l'accès remplace le mot de passe
  par une valeur qu'il ne communique à personne, ce qui a le même effet
  pratique.
