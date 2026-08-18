# Écran bénévoles : champs éditables complets et signalement non conforme

Status: Design validé — implémentation non commencée
Issue : #437

## Contexte

L'écran de validation des bénévoles (« Vérification des résultats »,
`frontend/app/benevoles/page.tsx` + `frontend/components/benevoles/ParticipationPanel.tsx`,
livré par #271/PR #368) ne permet aujourd'hui d'éditer que le nom de
l'épreuve et de réattribuer un résultat à un autre athlète. #437 demande
deux choses :

1. Rendre éditables des champs déjà portés par le modèle `Participation`
   mais absents de l'écran : dossard (`bib_number`), place au général
   (`rank_overall`), club, catégorie.
2. Une action « signaler non conforme », distincte de « valider ce
   résultat », pour les entrées manifestement invalides.

Aucun de ces deux points n'a de flux existant à étendre trivialement :
le premier ajoute des champs à un formulaire qui n'en avait que deux, le
second introduit un état métier qui n'existe pas encore
(`is_pending_validation` est aujourd'hui un booléen à sens unique,
pending → validé, sans état de rejet). Traité comme un seul cadrage
architectural, à la demande de l'utilisateur, plutôt que décomposé.

## Modèle de données et sémantique

Un seul champ nouveau : `Participation.is_rejected: bool`
(`server_default=false()`, même patron que `is_pending_validation` —
attention au piège `server_default` sous SQLite déjà documenté dans
`backend/app/models/AGENTS.md`).

**Invariant clé : `is_pending_validation` ne change jamais de valeur au
rejet.** Il reste `True` pour toujours sur une entrée rejetée — elle n'a
jamais été *validée*, seulement écartée. Conséquence directe : les cinq
fonctions de `participation_repository.py` qui excluent déjà
`is_pending_validation=True` des agrégats publics (`_apply_filters`,
`for_stats`, `list_page_for_course`, `summary_rows_for_course`,
`finishers_count_by_group`, cf. `backend/app/api/AGENTS.md`) excluent
gratuitement toute entrée rejetée, sans aucune modification. Le filtre
KPI de #438 (`participations.filter(p => !p.is_pending_validation)`, page
athlète) en bénéficie de la même façon.

Deux endroits seulement ont besoin de connaître `is_rejected`
spécifiquement :
- la file d'attente bénévoles (une entrée rejetée doit en sortir) ;
- l'affichage du badge sur la page athlète (« non conforme » plutôt que
  « en attente »).

Réversibilité : « annuler le rejet » repose sur `is_rejected=False` —
l'entrée réapparaît dans la file automatiquement, puisqu'elle n'a jamais
quitté l'état pending.

Visibilité athlète : une entrée rejetée reste visible dans « Toutes les
épreuves » de sa page, avec un badge « non conforme » — cohérent avec le
traitement actuel du pending (l'athlète comprend ce qui est arrivé à sa
saisie plutôt que de la voir disparaître sans explication). Exclue des
KPI/stats dans tous les cas (héritage de l'invariant ci-dessus).

## API backend

- Migration Alembic : colonne `Participation.is_rejected`.
- `app/core/validation.py` gagne un prédicat composé :
  `is_actionable_pending(participation)` — vrai si `is_pending_validation`
  et pas `is_rejected`. Remplace les vérifications actuelles à base de
  `is_pending_validation` seul dans `reassign`, `rename_course`
  (`has_pending_for_course`) et les deux nouvelles routes ci-dessous : une
  entrée rejetée ne doit plus être réattribuable, renommable ni éditable
  tant qu'elle n'est pas d'abord « dé-rejetée ».
- `participation_repository.list_pending` (alimente `GET
  /benevoles/queue`) exclut aussi `is_rejected=True`.
- Nouvelles fonctions dans `app/services/admin_actions.py`, même patron
  idempotent que `validate_participation` (log `AdminActionLog`, sous le
  compte système bénévoles) :
  - `reject_participation(db, *, participation_id, user_id)` /
    `unreject_participation(db, *, participation_id, user_id)`
  - `update_participation_fields(db, *, participation_id, champs: dict,
    user_id)` — seuls les champs fournis sont modifiés (`exclude_unset`,
    jamais un remplacement intégral, sur le modèle du piège déjà identifié
    côté `admin/droits`). Si `bib_number` est fourni, vérifie l'absence de
    conflit via `participation_repository.exists_for_bib` (en excluant la
    participation elle-même) et lève une `DomainError` française sinon.
- Nouvelles routes dans `app/api/v1/benevoles.py`, gardées par
  `require_benevole_access`, scopées à `is_actionable_pending` (404 sinon,
  même pattern que `reassign` aujourd'hui) :
  - `POST /benevoles/participations/{id}/reject`
  - `POST /benevoles/participations/{id}/unreject`
  - `PATCH /benevoles/participations/{id}` — corps
    `{bib_number?, rank_overall?, club?, category?}`, tous optionnels.

## Frontend

- `ParticipationPanel.tsx` : 4 nouveaux champs (dossard, place au
  général, club, catégorie) sous un bloc dédié, un seul bouton
  « Enregistrer les modifications » → `PATCH
  /benevoles/participations/{id}`. Le champ « Nom de l'épreuve » existant
  garde son bouton propre, inchangé.
- Bouton « Signaler non conforme » à côté de « Valider ce résultat »
  (style secondaire/attention, pas la couleur d'action principale) →
  `POST .../reject`. Confirmation légère en deux clics (« Signaler non
  conforme » → « Confirmer ? » inline, sans modal) pour éviter un clic
  accidentel sur une action qui retire l'entrée de la file.
- `ValidationQueue.tsx` : ajout d'un filtre/onglet secondaire « Non
  conformes » listant les entrées rejetées (masquées de la file
  principale côté backend), avec une action « Annuler le rejet » → `POST
  .../unreject` qui les fait réapparaître dans la file principale.
- Page athlète (`app/athletes/[id]/page.tsx`) : le badge `PendingBadge`
  se décline en « Non conforme » quand `is_rejected` est vrai (sinon « En
  attente de validation » comme aujourd'hui, quand seul
  `is_pending_validation` est vrai).

## Gestion d'erreurs

- Conflit de dossard (`bib_number` déjà pris sur la même épreuve) →
  `PATCH .../{id}` renvoie une erreur métier française (« Ce dossard est
  déjà attribué à un autre participant de cette épreuve »), le bénévole
  reste sur le panneau avec les champs édités intacts (pas de perte de
  saisie).
- Action sur une entrée qui n'est plus « actionnable » (déjà validée ou
  déjà rejetée par un autre bénévole entre-temps — deux bénévoles peuvent
  travailler en parallèle) → 404 côté API (même pattern que
  `reassign`/`rename_course` aujourd'hui), le frontend retire l'entrée de
  la file et affiche un message discret plutôt qu'une erreur bloquante.
- `rank_overall` / `bib_number` : valeurs non numériques ou négatives
  refusées côté formulaire avant l'appel réseau (validation identique à
  celle déjà en place côté saisie manuelle athlète, `ManualResultForm`).

## Tests

- Backend : extension de `tests/test_repositories/test_pending_exclusion.py`
  — une participation `is_rejected=True` reste exclue des mêmes agrégats
  que `is_pending_validation` (verrouille explicitement un comportement
  déjà garanti par l'invariant du modèle). Tests unitaires pour
  `reject_participation`/`unreject_participation` (idempotence, log
  `AdminActionLog`), `update_participation_fields` (partiel, conflit de
  dossard → erreur), et les 3 nouvelles routes (`require_benevole_access`,
  404 si non actionnable).
- Frontend : `ParticipationPanel.test.tsx` — nouveaux champs édités +
  sauvegarde groupée, bouton reject avec confirmation, affichage du badge
  « non conforme ». `ValidationQueue.test.tsx` — filtre/onglet
  non-conformes, action annuler-rejet. `page.test.tsx` (athlète) — badge
  « non conforme » distinct de « en attente ».

## Hors périmètre

- Toute notion d'historique/diff visible par l'athlète sur pourquoi son
  résultat a été rejeté (le badge affiche seulement le statut, pas de
  justification textuelle du bénévole).
- Édition de champs autres que dossard/place au général/club/catégorie
  (ex. temps, splits) — non demandée par #437.
