# Contrats API — Page de vérification des résultats par les bénévoles

Nouveau routeur `app/api/v1/benevoles.py`, monté dans `v1/router.py` comme les
autres. Garde dédiée (`require_benevole_access`, cf. `research.md` §D1),
**distincte** de `require_permission` (SSO/RBAC) utilisée par `/admin/*`. Les
trois routes d'action délèguent à des fonctions déjà existantes de
`services/admin_actions.py` (réutilisées, pas dupliquées) quand elles couvrent
déjà le geste ; seule la validation (geste 4) est nouvelle logique de service.

## POST /api/v1/benevoles/session

Connexion par mot de passe partagé. **Non gardée** (c'est l'endpoint qui pose
la garde des autres).

- Requête : `{"password": string}`
- 204 + cookie de session posé, si le mot de passe correspond
  (`hmac.compare_digest`).
- 401 si le mot de passe est incorrect, ou si `BENEVOLE_SHARED_PASSWORD` n'est
  pas configuré (fail-closed, sur le patron d'`auth_is_configured`).

## DELETE /api/v1/benevoles/session

Déconnexion explicite. Efface le cookie. 204, gardée ou non (geste sans effet
de bord sensible ; peut rester accessible sans garde pour permettre de sortir
d'un état de cookie invalide).

## GET /api/v1/benevoles/queue

Liste les résultats en attente de validation, tous clubs confondus (cf.
`research.md` §D5).

- Garde : `require_benevole_access`.
- Réponse : liste de `ParticipationOut` (ou schéma dédié incluant
  `evidence_url`, `team_name`, l'épreuve et l'athlète associés) — le schéma
  exact de sortie est un détail de tâche, pas de contrat de haut niveau ; il ne
  doit rien exposer que #270 n'a pas déjà rendu lisible côté `Participation`.
- 200, liste vide si aucun résultat en attente (pas d'erreur).

## PATCH /api/v1/benevoles/courses/{course_id}

Renomme l'épreuve associée à un résultat en attente (geste 2). **Délègue à
`admin_actions.update_course`** avec le `user_id` du compte système (cf.
`data-model.md`).

- Garde : `require_benevole_access`.
- Requête : `{"name": string}` (même schéma d'entrée que
  `AdminCourseUpdate`, restreint au seul champ nom pour cet écran — les trois
  autres champs de l'identité de `Course` — `event_date`, `event_type`,
  `is_relay` — ne sont pas éditables depuis la page bénévoles).
- 200 avec l'épreuve mise à jour, 409 en cas de collision avec une épreuve
  existante (`DuplicateError`, déjà levée par la fonction réutilisée).
- **Scopée** (relevé en revue de code, corrigé) : 404 si l'épreuve ne porte
  **aucun** résultat en attente de validation
  (`participation_repository.has_pending_for_course`). Sans ce garde-fou, le
  mot de passe partagé ouvrait la réécriture de **n'importe quelle** épreuve
  en base — un pouvoir d'administration de fait, sans le contrôle
  individuel du SSO — pour un geste censé se limiter au périmètre de
  validation.

## POST /api/v1/benevoles/participations/{participation_id}/reassign

Réattribue un résultat à un autre athlète existant (geste 3). **Délègue à
`admin_actions.reassign_participation`** avec le `user_id` du compte système.

- Garde : `require_benevole_access`.
- Requête : `{"athlete_id": int}`
- 200 avec la participation mise à jour, 409 en cas de conflit (l'athlète
  cible a déjà un résultat sur cette épreuve, `DuplicateError` déjà levée par
  la fonction réutilisée), 404 si l'athlète cible n'existe pas.
- **Scopée** (relevé en revue de code, corrigé) : 404 si la participation
  ciblée n'existe pas **ou** n'est plus en attente de validation — même
  raison que pour le renommage ci-dessus.

## POST /api/v1/benevoles/participations/{participation_id}/validate

Valide un résultat (geste 4) — **nouvelle logique de service**, propre à cette
feature : `is_pending_validation` passe à `false`, journalisé sous l'action
`participation.validate`.

- Garde : `require_benevole_access`.
- Pas de corps de requête.
- 200 avec la participation validée (désormais visible dans les agrégats
  publics, cf. FR-009). **Résolu** (cf. `tasks.md` T021/T022) : 404 seulement
  si la participation n'existe pas ; 200 **idempotent** (aucun second écrit au
  journal) si elle est déjà validée — même patron que `reassign_participation`,
  qui traite un geste sans effet comme un succès silencieux plutôt qu'une
  erreur (FR-012 de #117).

## Hors contrat de cette feature

- Aucune route de création d'athlète (réattribution limitée aux athlètes
  existants, cf. spec § Edge Cases).
- Aucune route de reprise en masse des résultats manuels antérieurs à #270 —
  sans objet, #330 a confirmé qu'aucun stock n'existe.
