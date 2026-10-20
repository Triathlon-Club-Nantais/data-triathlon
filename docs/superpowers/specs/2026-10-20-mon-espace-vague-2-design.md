# Mon espace, vague 2 : objectifs passés, mes demandes, validation de saison, objectif cible (design)

Date : 2026-10-20. Milestone v0.9.0 (gel jeudi 22/10 au soir, tag vendredi 23/10).
Issues : #1669, #1670, #1671, #1694 (epic #1667). Voie Superpowers, exécuteur
subagent-driven-development. Une PR et un worktree par issue, dans cet ordre.

## Intention

Le membre rattaché à sa fiche (#1325) doit trouver dans Mon espace où il en est
avec le club (validation de saison, demandes en cours) et avec lui‑même
(objectifs, saison passée comprise, et un objectif qui structure sa saison).
Tout est privé, lu sur `/auth/me/*`, jamais sur la fiche publique.

## Décisions du product owner (2026-10-20)

- #1670 et #1671 : deux cartes **en tête de la colonne de droite**
  (`frontend/components/mon-espace/ColonneDroite.tsx`), pas de nouvel onglet.
  Ordre : validation de saison, puis mes demandes (masquée si vide).
- #1694 : une épreuve cible saisie librement se clôt **par la date** : dès que la
  fiche rattachée a un résultat validé à cette date, dans la même discipline et
  le même format si la cible en précise un, l'objectif prend ce résultat.
- #1694 passe en dernier et sort de v0.9.0 si elle n'est pas en revue jeudi
  22/10 à midi.

## Contexte déjà livré (ne pas refaire)

- PR #1721 (en cours, palier 0) : `getSeasonGoals(season?)` transmet `?season=`,
  la clé de requête inclut la saison, `SeasonGoals` reçoit les saisons choisies
  et passe en lecture seule hors saison en cours. #1669 **part de cette
  branche** (ou de main une fois fusionnée) et réutilise ce mode lecture seule.
- `GET /auth/me/goals?season=` existe (`backend/app/api/v1/auth.py`).
- `admin_actions.season_quota(db, athlete_id, season)` rend déjà
  `validated_count`, `has_volunteer_action`, `has_pending_volunteer_action`,
  `season_validated`, `quota_met` (schéma `SeasonQuota`), en s'appuyant sur
  `core.season.season_quota_met`.
- Réclamations : `GET /auth/me/result-claims` (statuts `pending` / `rejected`
  seulement : une réclamation acceptée est supprimée, le résultat est passé sur
  la fiche) ; demande de fiche dans `GET /auth/me` (`athlete_claim`, mêmes
  statuts). Annulation : `DELETE /auth/me/athlete-claim`,
  `DELETE /auth/me/result-claims/{id}`.

## #1669 : objectifs des saisons passées dans le récap

- `/mon-espace/recap?saison=` (`SeasonRecap`) affiche une section « Mes
  objectifs » de la saison du récap, en lecture seule, chaque objectif avec son
  issue finale : « Atteint » ou « Non atteint » (la saison est close).
- Aucun objectif sur cette saison : la section ne s'affiche pas.
- Réutiliser `SeasonGoals` en lecture seule (issu de #1721) plutôt qu'un
  nouveau composant, si son rendu convient au récap ; sinon un petit composant
  de liste qui partage `libelle` / `progression`.
- Tests : client (la saison passe dans l'URL), composant (atteint / non
  atteint, section absente sans objectif).

## #1670 : « Mes demandes »

- Carte « Mes demandes » dans la colonne de droite : la demande de rattachement
  (si présente dans la session) et chaque réclamation de résultat, avec statut
  (« En attente », « Refusée »), date de la demande, et lien vers le résultat
  (fiche épreuve).
- Annuler une demande **en attente** depuis la carte, avec les mutations
  existantes (`lib/queries/auth.ts`), confirmation légère (le geste est
  réversible : on peut redemander).
- Carte masquée s'il n'y a aucune demande.
- Pour le lien et le libellé, `ResultClaimRead` gagne des champs **ajoutés**
  (Principe IV, pas de champ modifié) : `course_id`, `course_name`,
  `event_date`. Pas de nouvel endpoint (hors périmètre de l'issue). *Choix de
  l'agent.*
- Une réclamation acceptée n'apparaît plus (elle est supprimée) : pas de statut
  « Acceptée », le résultat est sur la fiche. Le texte d'aide le dit en une
  ligne. *Choix de l'agent.*
- Tests : API (champs ajoutés), composant (liste, statuts, annulation, carte
  masquée).

## #1671 : ma validation de saison

- Endpoint `GET /auth/me/season-quota`, lecture seule, saison en cours,
  réutilise `admin_actions.season_quota` tel quel (aucune duplication de la
  règle). Compte non rattaché : `null` en 200 (même convention que les autres
  lectures `/auth/me/*` qui rendent vide sans fiche). *Choix de l'agent.*
- Carte « Ma saison au club » en tête de colonne de droite : « N épreuves
  comptées sur 3 », bénévolat (« validé », « en attente de validation »,
  « aucune action », avec lien `/benevolat`), et statut : « Saison validée »,
  « Conditions remplies, en attente de validation par le club », ou ce qui
  manque.
- Toujours la saison en cours, quelle que soit la sélection de saisons de la
  page (le dire dans le titre).
- Membre non rattaché : rien (Mon espace montre déjà l'invitation).
- Tests : API (rattaché, non rattaché, non connecté 401), composant (les trois
  statuts).

## #1694 : épreuve cible et objectif majeur

- Nouveau type d'objectif `race` : une épreuve cible, **connue** (`course_id`
  d'une épreuve importée) ou **saisie libre** (`race_name` + `race_date`
  obligatoires), discipline et format facultatifs (`event_type`), temps visé
  facultatif (`target` en secondes, nullable pour ce type seulement).
- Drapeau `major` : un seul objectif majeur par compte et par saison (le passer
  sur un objectif le retire des autres, dans la même transaction).
- Progression calculée à la lecture, comme aujourd'hui, jamais stockée :
  - cible connue : le résultat validé de la fiche rattachée sur cette épreuve ;
  - saisie libre : un résultat validé de la fiche à `race_date` (et
    `event_type` s'il est fixé) ; plusieurs candidats : le meilleur temps.
  - Pas de résultat et date future : à venir ; pas de résultat et date passée :
    en attente d'import (pas « échoué »).
  - Résultat trouvé : objectif clos, `reached` = pas de temps visé, ou temps
    total inférieur ou égal au temps visé.
- Mise en avant de l'objectif majeur : en tête du centre de Mon espace (au
  dessus de « Mes chiffres ») avec compte à rebours en jours jusqu'à la date,
  temps visé, ou issue une fois clos ; et rappel compact dans la colonne de
  droite. Compte à rebours en texte (« J‑12 » doublé d'un libellé accessible
  « dans 12 jours »), pas d'animation.
- Formulaire : la sorte « Une épreuve cible » s'ajoute à la radio existante ;
  choix d'une épreuve connue par recherche dans les épreuves importées (API de
  recherche existante si elle convient), sinon nom et date. Case « Objectif
  majeur de la saison ».
- Privé, comme #1373.
- Migration Alembic : colonnes nullables ajoutées à `season_goals`
  (`course_id` FK, `race_name`, `race_date`, `major` booléen non nul défaut
  faux), `target` devient nullable. Rebase sur origin/main et une seule tête
  avant de l'écrire.
- Tests backend : cible connue et libre, clôture par la date, majeur unique,
  validation (saisie libre sans date refusée). Front : mise en avant, compte à
  rebours, accessibilité.

### Précisions #1694 (choix de l'agent après relecture)

- **Saison** : dérivée de la date (`season_of`, bascule au 1ᵉʳ septembre) :
  date de l'épreuve connue, ou `race_date`. Comme les autres objectifs, la
  création reste bornée à la saison en cours : une date hors saison en cours est
  refusée (422). Pas de champ saison dans le formulaire.
- **Résultat retenu** : un résultat est « validé » avec la même sémantique que
  `admin_actions.season_quota` (`not is_pending_validation`, statut
  `finisher`). Un DNF ou DNS ne clôt pas l'objectif.
- **Épreuve connue** : `course_id` désigne une course d'un format donné
  (`Course.event_type`), donc au plus un résultat de la fiche ; `event_type`
  de l'objectif est repris de la course.
- **Saisie libre** : un temps visé exige `event_type` (même règle que `_check`
  pour un temps). Sans `event_type` (donc sans temps visé), n'importe quel
  résultat validé à la date clôt l'objectif comme atteint ; avec `event_type`,
  le meilleur temps de ce format à la date.
- **État** : `SeasonGoalRead` gagne un champ ajouté `outcome` :
  `"upcoming"` (date future, pas de résultat), `"awaiting_results"` (date
  passée, pas de résultat), `"reached"`, `"missed"`. `reached` reste tel quel
  (Principe IV). Pour les sortes `time` et `count`, `outcome` vaut `reached` ou,
  sinon, `missed` sur une saison close et `upcoming` sur la saison en cours.
  #1669 (livrée avant) n'affiche que `reached` ; #1694 étend le récap pour
  afficher « Sans résultat » sur `awaiting_results`.
- **Modification** : le même `SeasonGoalWrite` étendu porte tous les champs ;
  changer de sorte est permis, les colonnes inutiles sont remises à null. Les
  objectifs `race` comptent dans la limite de 10 par saison.
- **Majeur** : possible sur toute sorte, comme le dit l'issue. La mise en avant
  montre le compte à rebours pour une épreuve cible, la progression (meilleur
  temps, N sur M) pour les autres.
- **Mise en avant** : l'objectif majeur de la saison en cours seulement,
  toujours affiché, avec son issue une fois clos ; « En attente des résultats »
  sur `awaiting_results`.

### Précisions #1670

- Les deux lectures portent déjà `created_at` : c'est la date de la demande
  affichée. `event_date` ajouté sert au libellé du résultat, pas de date de
  demande.
- Annulation : confirmation en ligne (bouton « Annuler la demande », puis
  « Confirmer »), pas de modale, sauf motif existant plus proche dans le code.

## Non‑objectifs

- Notification d'un changement de statut d'une demande (#1670).
- Valider sa propre saison, détail des déclarations de bénévolat (#1671).
- Créer ou modifier un objectif d'une saison passée (#1669).
- Calendrier des épreuves à venir du club, « j'y vais » (#1694, parqué #1377).
- Publication des objectifs sur la fiche publique.

## Anti‑objectifs

- Une règle de quota dupliquée côté front ou dans un nouveau service.
- Un objectif affiché « non atteint » alors que le résultat n'est simplement
  pas encore importé.
- Toucher aux écrans réservés à l'autre session (login, /account, composants
  auth, fiche athlète, écrans jeunes) ou à l'outillage de tests (config
  pytest/vitest, conftest, ci.yml).

## Laissé au builder

Libellés exacts, ordre interne des cartes, découpage en composants, forme des
tests, choix de la recherche d'épreuve pour #1694.
