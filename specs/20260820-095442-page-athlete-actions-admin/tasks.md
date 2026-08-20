---
description: "Tâches d'implémentation — actions d'administration sur la page d'un coureur (#439)"
---

# Tasks: Actions d'administration sur la page d'un coureur

**Input**: Design documents from `specs/20260820-095442-page-athlete-actions-admin/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Le Principe III de la constitution v1.1.1 est **non-négociable** — TDD sans réseau. Chaque comportement neuf est précédé d'un test qui échoue. Aucune dérogation n'est demandée : `plan.md` §Complexity Tracking est vide.

**Organization**: tâches groupées par user story, chaque story livrable et testable seule.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable — **fichier distinct**, aucune dépendance sur une tâche non terminée
- **[Story]** : US1…US5 de `spec.md`
- Chemins de fichiers exacts, relatifs à la racine du dépôt

## Path Conventions

Application web à deux déploiements. Backend : `backend/app/` et `backend/tests/`
(sous-dossiers `test_repositories/`, `test_services/`, `test_api/`). Frontend :
`frontend/`, tests **colocalisés** à côté du composant (`*.test.tsx`).

**Commandes de vérification** — backend depuis `backend/`, frontend depuis `frontend/` :

```bash
uv run pytest -m "not integration"     # backend, sans réseau (défaut CI)
uv run ruff check .
npm test                               # vitest run
npm run lint
npm run build                          # strict TS + RSC
```

---

## Phase 1: Setup

**Purpose** : établir la référence rouge/vert avant d'écrire quoi que ce soit.

- [X] T001 Vérifier que la base de départ est verte : `cd backend && uv run pytest -m "not integration"` puis `cd frontend && npm test`. Toute défaillance préexistante est relevée ici, pas attribuée à la branche.
- [X] T002 [P] Confirmer la tête Alembic avec `cd backend && uv run alembic heads` ; si elle n'est plus `aeb0b98d1a51`, corriger le `down_revision` annoncé dans `specs/20260820-095442-page-athlete-actions-admin/data-model.md` §Migration.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose** : ouvrir une frontière cliente sur une page qui doit rester rendue côté serveur, et **verrouiller le coût nul pour le visiteur anonyme avant d'ajouter la moindre action**.

**⚠️ CRITICAL** : aucune user story ne peut commencer avant la fin de cette phase. C'est ici que se joue SC-004 — une fois une action ajoutée, une régression de mode de rendu ne se verrait plus.

- [X] T003 [P] Créer `frontend/components/athletes/AthleteAdminPanel.test.tsx` avec les cas **qui échouent** de l'absence de pouvoir : visiteur anonyme → rien de rendu ; connecté sans aucun des quatre pouvoirs → rien de rendu ; session illisible (`getSession` rejette) → rien de rendu (FR-008, US5-AC4) ; et **aucun appel à `apiClient.getSession`** quand le cookie témoin `tcn_logged_in` est absent (SC-004). Mocker `apiClient.getSession` sur le patron exact de `frontend/components/courses/CourseSourcesPanel.test.tsx`.
- [X] T004 Créer `frontend/components/athletes/AthleteAdminPanel.tsx` — composant **client**, `useSession()`, rend `null` tant que `athletes:write` n'est pas porté. Aucun formulaire à ce stade : la coquille suffit à faire passer T003.
- [X] T005 Monter `<AthleteAdminPanel>` dans l'en-tête de `frontend/app/athletes/[id]/page.tsx`, en ne lui passant que ce que la page tient déjà (id, nom, prénom, club). La page **continue de charger par `apiServer.getAthlete`** (`lib/api/server.ts:90`, bâti sur `serverFetch`, sans cookies) : ni `serverFetchAuthed`, ni lecture de cookie côté serveur (D11). Le composant se monte **à côté** de `SelectAthleteButton`, qui occupe déjà le créneau de droite de l'en-tête par un `marginLeft: "auto"` (`page.tsx:73-75`) — ne pas lui reprendre ce `auto`, deux `auto` sépareraient les commandes aux deux bouts de la ligne (`contracts/ui.md` §En-tête).
- [X] T006 Vérifier avec `cd frontend && npm run build` que `/athletes/[id]` **conserve son mode de rendu** d'avant la branche, et avec `npm test` qu'aucun test existant ne régresse (SC-004).

**Checkpoint** : la frontière cliente existe, le visiteur anonyme ne paie rien, et aucune action n'est encore offerte. Le scénario 11 de `quickstart.md` est déroulable **dès maintenant** — c'est son seul moment utile.

---

## Phase 3: User Story 1 - Corriger l'identité depuis la page (Priority: P1) 🎯 MVP

**Goal** : corriger nom, prénom et — sous `athletes:read` — date de naissance sans quitter la fiche, avec un refus propre en cas de conflit d'identité.

**Independent Test** : se connecter avec `athletes:write`, ouvrir une fiche, renommer, constater le nouveau nom **sur la page** et dans la recherche publique. Zéro navigation intermédiaire (SC-001).

**Note de cadrage** : le backend est déjà là — `PATCH /api/v1/admin/athletes/{id}` accepte `nom`, `prenom`, `birth_date` et journalise `athlete.update`. Cette story est **purement frontend**.

### Tests for User Story 1

> **Écrire ces tests d'abord et les voir ÉCHOUER** (Principe III, non-négociable). Ils visent tous `AthleteAdminPanel.test.tsx` : séquentiels, pas de `[P]` entre eux.

- [X] T007 [US1] Étendre `frontend/components/athletes/AthleteAdminPanel.test.tsx` avec le chemin nominal, **en échec** : `athletes:write` → l'accès aux corrections est visible ; l'ouvrir affiche nom et prénom **préremplis** ; enregistrer appelle `apiClient.updateAthlete` avec les seuls champs corrigés, ferme la modale et déclenche un `toast.success` (US1-AC1, US1-AC2).
- [X] T008 [US1] Ajouter dans le même fichier le cas du **conflit**, en échec : sur `ApiError` 409, la modale **reste ouverte**, le message du serveur est affiché verbatim, et la saisie de l'opérateur est **conservée** (FR-010, US1-AC3).
- [X] T009 [US1] Ajouter dans le même fichier les deux cas de la date de naissance, en échec : avec `athletes:write` **sans** `athletes:read`, aucun champ de date n'est rendu **et** le corps envoyé ne porte aucune clé `birth_date` ; avec `athletes:read`, la date est chargée via `useAdminAthlete` et préremplie (US1-AC4, D7).

### Implementation for User Story 1

- [X] T010 [US1] Implémenter le formulaire d'identité dans `frontend/components/athletes/AthleteAdminPanel.tsx` : `tcn/Modal`, `tcn/Input`, `tcn/Button` (jamais `components/ui/`, D8), mutation `useUpdateAthlete` de `frontend/lib/queries/admin.ts`, `toast.success` / `toast.error`.
- [X] T011 [US1] Charger la fiche gardée via `useAdminAthlete(id)` **uniquement** si la session porte `athletes:read`, et ne rendre ni n'envoyer `birth_date` qu'à cette condition — c'est l'**absence du champ** qui garantit la non-effacement, `exclude_unset` faisant le reste côté serveur (D7).
- [X] T012 [US1] Traiter l'`ApiError` 409 dans la modale : afficher `detail` tel quel, sans vider le formulaire ni fermer la modale.
- [X] T013 [US1] Appeler `router.refresh()` après un enregistrement réussi, pour que le nom en tête et les indicateurs calculés côté serveur reflètent la correction sans rechargement manuel (FR-015, D10 ; précédent `frontend/components/scrape/TcnScrapeForm.tsx`).

**Checkpoint** : US1 est complète et livrable seule. Elle justifie déjà la feature (SC-001 : 0 navigation contre 3).

---

## Phase 4: User Story 5 - Ne voir que ce que l'on peut faire (Priority: P1)

**Goal** : la visibilité se décide **pouvoir par pouvoir**, et le masquage d'un bouton n'est jamais une protection.

**Independent Test** : charger la même fiche dans les états de session de `quickstart.md` §scénario 9 et compter les actions offertes — le compte doit être **exactement** celui des pouvoirs qui **suffisent** à un geste, un pouvoir couplé comptant pour zéro tant que son binôme manque (SC-003).

**Note de cadrage** : la règle de US5 s'implémente **dans chaque composant**, pas dans un garde central — il n'existe aucun échelon « administrateur ». Cette phase porte donc la **vérification transverse** de la règle et le complément des gardes côté serveur. Les lignes de la matrice propres à US2, US3 et US4 sont posées dans leurs phases respectives.

### Tests for User Story 5

- [X] T014 [P] [US5] Dans `backend/tests/test_api/test_participations_api.py`, vérifier — et compléter si absent — que `DELETE /api/v1/participations/{id}` **sans** `participations:delete` répond 401/403, que le résultat existe toujours après, et qu'aucune entrée n'est écrite dans `admin_action_log` (FR-009, SC-005, US5-AC5).
- [X] T015 [P] [US5] Dans `backend/tests/test_api/test_admin_data_api.py`, vérifier — et compléter si absent — la même garantie pour `PATCH /admin/athletes/{id}` sans `athletes:write` et pour `POST /admin/participations/{id}/reassign` sans `participations:reassign` : refus, donnée inchangée, journal vide.
- [X] T016 [US5] Dans `frontend/components/athletes/AthleteAdminPanel.test.tsx`, ajouter le cas de la visibilité **croisée**, en échec : une session portant `participations:delete` seul ne voit **pas** l'accès aux corrections d'identité (US5-AC3).

### Implementation for User Story 5

- [X] T017 [US5] Corriger ce que T016 révèle : la condition de rendu de `AthleteAdminPanel` doit tester `athletes:write` **précisément**, jamais « la session porte au moins un pouvoir » ni « l'utilisateur est connecté ».
- [X] T018 [US5] Consigner dans `specs/20260820-095442-page-athlete-actions-admin/contracts/ui.md` toute divergence constatée entre la table de visibilité et le code — le contrat suit le terrain, pas l'inverse.

**Checkpoint** : la règle « si et seulement si » est vérifiée de bout en bout pour les actions livrées, et les refus serveur sont couverts pour les trois routes.

---

## Phase 5: User Story 2 - Supprimer un résultat erroné (Priority: P2)

**Goal** : supprimer un résultat depuis sa ligne, après une confirmation qui nomme l'épreuve, avec une **trace au journal** — que le geste n'avait pas jusqu'ici.

**Independent Test** : supprimer une ligne, constater sa disparition, les indicateurs recalculés, et l'entrée `participation.delete` au journal.

**Note de cadrage** : cette story comble deux écarts existants (`contracts/api.md` §2) — aucune entrée au journal, et `db.delete()` dans la route (Principe II). Le chemin, le verbe et le 204 **ne bougent pas** (Principe IV).

### Tests for User Story 2

> Trois fichiers distincts : T019, T020 et T021 sont parallélisables entre eux.

- [X] T019 [P] [US2] Dans `backend/tests/test_repositories/test_participation_repository.py`, test en échec pour `delete(db, participation)` : la ligne disparaît, **le coureur survit**, aucun commit n'est émis par le repository.
- [X] T020 [P] [US2] Dans `backend/tests/test_services/test_admin_actions.py`, tests en échec pour `delete_participation` : une entrée `action="participation.delete"`, `entity_type="participation"`, dont le `payload` permet de **relire** ce qui a disparu (coureur, épreuve, place, temps) ; le coureur **n'est pas purgé** même s'il ne lui reste aucun résultat (FR-012, D5 — divergence assumée avec `reassign_participation`) ; un identifiant inconnu lève `NotFoundError`.
- [X] T021 [P] [US2] Dans `backend/tests/test_api/test_participations_api.py`, tests en échec : `DELETE` avec le pouvoir répond **204** et écrit **une** entrée au journal ; un second `DELETE` sur le même identifiant répond **404** et n'écrit **rien** (FR-014, FR-016) ; supprimer un résultat **en attente de validation** répond **204** et journalise comme les autres — la route ne distingue pas les deux (US2-AC6).
- [X] T022 [US2] Créer `frontend/components/athletes/ParticipationAdminActions.test.tsx` avec les cas en échec de la suppression : visible seulement avec `participations:delete` ; le déclenchement ouvre une confirmation qui **nomme l'épreuve** et dit l'irréversibilité ; annuler ne supprime rien (SC-006) ; sur 404, un message compréhensible s'affiche — jamais une erreur technique brute (FR-016, US2-AC5) ; le `toast.success` est émis **aussi** pour une ligne en attente de validation, seul retour explicite dans ce cas puisque aucun indicateur ne bouge (US2-AC6).

### Implementation for User Story 2

- [X] T023 [US2] Ajouter `delete(db, participation)` dans `backend/app/repositories/participation_repository.py`, sœur des `delete_all` / `delete_for_course` existantes : `db.delete` + `db.flush`, **pas de commit**.
- [X] T024 [US2] Ajouter `delete_participation(db, *, participation_id, user_id)` dans `backend/app/services/admin_actions.py` : `_participation_or_404`, construction du `payload` de relecture **avant** la suppression, écriture au journal via `admin_action_log_repository.create`, puis `participation_repository.delete`. Aucune purge de fiche orpheline (D5).
- [X] T025 [US2] Réécrire le corps de la route dans `backend/app/api/v1/participations.py` : remplacer `_: User` par `user: User` (le journal a besoin de l'auteur), déléguer au service, `db.commit()`, et ajouter `capture_event("participation_deleted", …)` par cohérence avec les autres gestes. **Ne toucher ni le chemin, ni le verbe, ni le 204, ni la garde.**
- [X] T026 [US2] Ajouter `deleteParticipation(id)` dans `frontend/lib/api/client.ts`.
- [X] T027 [US2] Ajouter `useDeleteParticipation` dans `frontend/lib/queries/admin.ts`, aligné sur `useReassignParticipation` (invalidations et gestion d'erreur identiques).
- [X] T028 [US2] Créer `frontend/components/athletes/ParticipationAdminActions.tsx` : l'action de suppression, sa confirmation `tcn/Modal` nommant l'épreuve, `router.refresh()` au succès, `toast.success` / `toast.error`.
- [X] T029 [US2] Monter `<ParticipationAdminActions>` dans `frontend/app/athletes/[id]/page.tsx` en **sous-ligne**, sœur de celle du lien « Voir la preuve » — jamais à l'intérieur du `<Link>` de la ligne, qui rendrait le HTML invalide (D9). La grille de sept colonnes n'est pas touchée, et la sous-ligne ne s'affiche que si au moins une action est visible.

**Checkpoint** : US1 et US2 fonctionnent indépendamment. Le geste le plus irréversible de l'API laisse enfin une trace.

---

## Phase 6: User Story 3 - Changer le club actuel (Priority: P3)

**Goal** : corriger le club actuel depuis la page, et faire **primer cette correction sur tout import ultérieur**.

**Independent Test** : corriger le club vers le libellé du TCN, constater l'apparition dans la liste des coureurs du club ; réimporter une épreuve où le coureur figure avec l'ancien libellé et constater que la correction **tient** (SC-008).

**Note de cadrage** : seule story à toucher le schéma. `athlete_repository.resolve` est le **seul** écrivain de `Athlete.club` après création — vérifié sur tout `backend/app` (D1) —, donc l'invariant n'a qu'un point d'application.

### Tests for User Story 3

> Cinq fichiers distincts : T030 à T033 et T035 sont parallélisables entre eux.

- [X] T030 [P] [US3] Dans `backend/tests/test_repositories/test_athlete_repository.py`, tests en échec : `resolve` **ne réécrit pas** `club` quand `club_locked` est vrai (INV-1) ; il le réécrit quand il est faux, comportement d'aujourd'hui (INV-2) ; une fiche créée par import part à `club_locked = False`.
- [X] T031 [P] [US3] Dans `backend/tests/test_services/test_admin_actions.py`, tests en échec : une correction qui **change** `club` pose `club_locked` (INV-3) ; une correction qui ne touche que le nom le laisse tel quel (INV-4) ; une correction du club vers **la même valeur** n'écrit rien au journal et ne pose pas le drapeau ; le `payload` du journal porte `club` dans ses instantanés avant/après ; **corriger le club actuel ne touche à aucun `Participation.club`** du coureur — le club de l'époque est une autre donnée (FR-013).
- [X] T032 [P] [US3] Dans `backend/tests/test_services/test_import_service.py`, test en échec de bout en bout (sans réseau) : un réimport complet d'une épreuve **ne réécrit pas** le club d'un coureur verrouillé et **suit** celui d'un coureur non verrouillé de la même épreuve (SC-008, US3-AC4/AC5).
- [X] T033 [P] [US3] Dans `backend/tests/test_api/test_admin_data_api.py`, tests en échec : `PATCH {"club": "…"}` répond 200 avec le nouveau club **et laisse inchangés les `club` des résultats du coureur** (FR-013) ; `PATCH {"club": null}` répond 200 et met la colonne à `NULL`, pas à `""` (US3-AC2) ; `club_locked` **n'apparaît dans aucune réponse** — ni `AdminAthleteRead`, ni `AthleteBrief` (INV-5, D2).
- [X] T034 [US3] Dans `frontend/components/athletes/AthleteAdminPanel.test.tsx`, cas en échec : le champ club est présent sous `athletes:write` (sans exiger `athletes:read`, `AthleteBrief` le portant déjà publiquement) ; le vider envoie `null` et non `""`.
- [X] T035 [P] [US3] Dans `backend/tests/test_migrations.py`, ajouter `test_downgrade_puis_upgrade_de_club_locked`, en échec, sur le patron de `test_downgrade_puis_upgrade_de_l_indice_de_fiabilite` : après `downgrade` d'un cran la colonne `club_locked` a disparu de `athletes`, après `upgrade head` elle est de retour avec son `server_default`. Ce fichier ne couvre l'aller-retour que **révision par révision** — `test_upgrade_head_sur_base_vierge` est le seul test générique, aucun `downgrade` ne l'est. Sans ce test, le `downgrade` de la nouvelle révision n'est **jamais exécuté** (Principe III, `data-model.md` §Migration).

### Implementation for User Story 3

- [X] T036 [US3] Ajouter `club_locked: Mapped[bool]` à `backend/app/models/athlete.py` (`nullable=False`, `server_default=false()`), avec un commentaire **en français** — c'est une règle métier (Principe I) — expliquant le **pourquoi** : le club suit l'import sauf correction humaine. Ne pas paraphraser ce que le nom dit déjà (Principe VI).
- [X] T037 [US3] Générer la migration : `cd backend && uv run alembic revision --autogenerate -m "club_locked athlete"`, puis **relire à la main** la révision (obligation de la constitution §Additional Constraints) : `server_default=sa.false()` et non un `default` Python, `nullable=False`, `down_revision` conforme à T002, `downgrade` qui supprime la colonne. Appliquer avec `uv run alembic upgrade head`, et faire passer T035.
- [X] T038 [US3] Dans `backend/app/repositories/athlete_repository.py`, conditionner la mise à jour du club de `resolve` à `not existing.club_locked`. Le drapeau se lit comme un attribut déjà hydraté — **aucune requête supplémentaire** sur le chemin d'import (D1).
- [X] T039 [US3] Dans `backend/app/services/admin_actions.py`, ajouter `"club"` à `_CHAMPS_ATHLETE` et poser `club_locked = True` quand la valeur écrite de `club` diffère de l'ancienne. **Vérifier au passage que la détection de doublon reste intacte** : `vise` ne transmet à `get_by_identity` que `nom`, `prenom` et `birth_date` — le club ne doit pas entrer dans la clé d'unicité.
- [X] T040 [US3] Dans `backend/app/schemas/admin.py`, ajouter `club: str | None` à `AdminAthleteUpdate` et `"club"` à son `_NULLABLES` — sans `min_length` : `null` est la forme du geste « retirer le club », un `""` détrempé doit être refusé (`contracts/api.md` §1).
- [X] T041 [US3] Dans `backend/app/core/permissions.py`, compléter la **description** de `ATHLETES_WRITE` pour nommer le club — sinon l'écran de composition des rôles sous-annonce ce que le pouvoir permet. Le `code` et le `label` ne bougent pas (le code traverse la base). Ajuster `backend/tests/test_permissions_catalogue.py` s'il verrouille ce texte.
- [X] T042 [P] [US3] Dans `frontend/lib/types.ts`, ajouter `club: string | null` à `AdminAthleteUpdate`.
- [X] T043 [US3] Ajouter le champ club au formulaire de `frontend/components/athletes/AthleteAdminPanel.tsx`, dans **le même** formulaire que l'identité — un seul pouvoir les garde, un seul `PATCH` les écrit, et SC-002 borne à 2 interactions. Un champ vidé est envoyé à `null`.

**Checkpoint** : US1, US2 et US3 fonctionnent indépendamment. La correction manuelle du club survit aux imports.

---

## Phase 7: User Story 4 - Rattacher un résultat au bon coureur (Priority: P4)

**Goal** : rattacher un résultat au coureur qui l'a réellement couru, en le cherchant par son nom, avec la date de naissance pour départager les homonymes.

**Independent Test** : rattacher un résultat de la fiche A vers le coureur B, constater sa disparition de A et son apparition sur B.

**Note de cadrage** : le backend est déjà là et **inchangé** (`contracts/api.md` §3). L'action exige **deux** pouvoirs — `participations:reassign` **et** `athletes:read` —, la recherche gardée étant la seule à rendre la date de naissance (FR-004, D6). Cette phase **corrige aussi le back-office**, qui offre aujourd'hui l'action sur le seul `participations:reassign` et laisse donc son sélecteur finir en 403 (FR-020, US4-AC3). Une règle par geste, pas par écran.

### Tests for User Story 4

- [X] T044 [US4] Dans `frontend/components/athletes/ParticipationAdminActions.test.tsx`, cas en échec : l'action est visible avec les **deux** pouvoirs, et **absente** avec `participations:reassign` seul (FR-004, D6) ; le sélecteur affiche nom, prénom **et date de naissance** ; valider appelle `apiClient.reassignParticipation` puis `router.refresh()`.
- [X] T045 [P] [US4] Dans `backend/tests/test_services/test_admin_actions.py`, vérifier — et compléter si absent — que réattribuer vers le coureur qui **porte déjà** le résultat n'écrit rien et ne journalise rien (US4-AC2, FR-014).
- [X] T046 [P] [US4] Dans `frontend/components/admin/CourseParticipationsDialog.test.tsx`, cas en échec : une session portant `participations:reassign` **sans** `athletes:read` ne voit **aucune** action de rattachement, et le cas nominal (les deux pouvoirs) continue de la voir. C'est le bug latent que FR-020 corrige : `CourseParticipationsDialog.tsx:45-46` ne teste aujourd'hui qu'un pouvoir, alors que la chaîne `ReassignParticipationDialog` → `AthleteSearchPicker` → `useAdminAthleteSearch` → `GET /admin/athletes?search=` est gardée par `athletes:read` (`admin_data.py:69`).

### Implementation for User Story 4

- [X] T047 [US4] Ajouter l'action de rattachement à `frontend/components/athletes/ParticipationAdminActions.tsx` : sélecteur bâti sur `useAdminAthleteSearch`, mutation `useReassignParticipation`, `router.refresh()` au succès. Le choix du coureur cible **est** la confirmation — pas de seconde validation (`contracts/ui.md`).
- [X] T048 [US4] Conditionner la visibilité de cette action à la présence des **deux** pouvoirs, et rendre le cas « déjà porté par ce coureur » comme un message, pas comme une erreur.
- [X] T049 [US4] Gérer la conséquence d'écran de la purge des fiches orphelines : si la réattribution vide la fiche courante, `router.refresh()` la fait basculer sur son état « introuvable », que la page gère déjà (FR-016, `contracts/api.md` §3).
- [X] T050 [US4] Aligner `frontend/components/admin/CourseParticipationsDialog.tsx` sur la même règle : `peutRattacher` doit exiger `participations:reassign` **et** `athletes:read` (ligne 45-46). Une ligne de code, et le seul point de cette branche hors de la page coureur — assumé par FR-020 et §Hors périmètre de `spec.md`. Ne rien changer d'autre dans cet écran.

**Checkpoint** : les quatre gestes sont livrés, chacun reste testable seul, et la réattribution suit la même règle de visibilité aux deux endroits où elle est offerte.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T051 [P] Documenter la feature dans `docs/api/admin-donnees.md` §« Administration des données (#117) » : le champ `club` de `PATCH /admin/athletes/{id}`, la règle « la correction manuelle prime sur l'import » portée par `club_locked` (et le fait qu'elle **n'est pas** exposée), et la nouvelle entrée `participation.delete` — en signalant que `DELETE /participations/{id}` vit dans `participations.py`, hors du tableau des ressources `/admin/`. Consigner aussi le **couplage de visibilité** de la réattribution (FR-004/FR-020), qui vaut désormais pour le back-office.
- [X] T052 [P] Compléter la ligne **Athlete** de `backend/app/models/AGENTS.md` avec la sémantique de `club_locked` : le club suit l'import, sauf correction humaine.
- [X] T053 [P] Ajouter `athletes/` à l'inventaire des composants de `frontend/AGENTS.md` (§`components/`), en notant que ces composants prennent `tcn/` parce que la page est un écran public.
- [X] T054 [P] Ajouter un renvoi vers `specs/20260820-095442-page-athlete-actions-admin/` dans `docs/api/admin-donnees.md`, sur le modèle du renvoi existant vers `specs/20260806-180938-admin-crud-actions/`.
- [ ] T055 Dérouler les 12 scénarios de `specs/20260820-095442-page-athlete-actions-admin/quickstart.md`, en particulier le scénario 4 (les deux moitiés : un résultat validé bouge les indicateurs, une saisie en attente n'en bouge aucun), le scénario 7 (le club figé résiste, le club jamais corrigé suit) et le scénario 9 (la matrice des états de session **et** son contrôle du back-office, SC-003 et FR-020). Le scénario 11 a déjà été déroulé au checkpoint de la Phase 2 ; le rejouer ici ne vérifie plus rien d'utile.
- [X] T056 Passer les suites complètes : `cd backend && uv run pytest -m "not integration" && uv run ruff check .` puis `cd frontend && npm test && npm run lint && npm run build`. Le `build` reste le garde de SC-004.
- [X] T057 Préparer la fin de branche : `requesting-code-review`, puis le sous-agent `ui-ux-review` (la branche touche `frontend/`) — en lui signalant explicitement que `tcn/Modal` n'a **ni piège à focus ni restauration du focus**, limite des trois modales publiques existantes que cette feature n'aggrave ni ne corrige (D8) —, puis `verification-before-completion` et `finishing-a-development-branch`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : aucune dépendance.
- **Foundational (Phase 2)** : dépend de Setup. **Bloque toutes les stories** — c'est là que SC-004 se verrouille, avant qu'une action ne masque une régression de mode de rendu.
- **User Stories (Phases 3 à 7)** : toutes dépendent de la Phase 2, puis se déroulent dans l'ordre de priorité P1 → P1 → P2 → P3 → P4.
- **Polish (Phase 8)** : dépend des stories souhaitées.

### User Story Dependencies

- **US1 (P1)** : démarre après la Phase 2. Aucune dépendance sur une autre story. Purement frontend.
- **US5 (P1)** : la **règle** de US5 est implémentée dans chaque story ; cette phase en porte la vérification transverse. Ses tests côté serveur (T014, T015) sont indépendants de tout et pourraient être écrits dès la Phase 1.
- **US2 (P2)** : indépendante d'US1. Backend **et** frontend.
- **US3 (P3)** : indépendante d'US1 et d'US2 côté backend ; côté frontend elle **étend** le panneau créé par US1 (voir conflits de fichiers). T035 dépend de T037 pour **passer**, pas pour être écrit.
- **US4 (P4)** : indépendante côté backend (rien à changer) ; côté frontend elle **étend** le composant créé par US2. Son volet back-office (T046, T050) est indépendant de tout le reste de la branche et peut être mené à part.

### Conflits de fichiers — ce qui interdit le `[P]`

Huit fichiers sont touchés par plusieurs phases. Deux tâches qui les visent ne
sont **jamais** parallélisables entre elles :

| Fichier | Tâches |
| --- | --- |
| `frontend/components/athletes/AthleteAdminPanel.tsx` | T004, T010, T011, T012, T013, T017, T043 |
| `frontend/components/athletes/AthleteAdminPanel.test.tsx` | T003, T007, T008, T009, T016, T034 |
| `frontend/components/athletes/ParticipationAdminActions.tsx` | T028, T047, T048, T049 |
| `frontend/components/athletes/ParticipationAdminActions.test.tsx` | T022, T044 |
| `frontend/app/athletes/[id]/page.tsx` | T005, T029 |
| `backend/tests/test_services/test_admin_actions.py` | T020, T031, T045 |
| `backend/tests/test_api/test_admin_data_api.py` | T015, T033 |
| `backend/tests/test_api/test_participations_api.py` | T014, T021 |

Trois fichiers n'ont qu'une tâche et restent donc `[P]` sans réserve :
`backend/tests/test_migrations.py` (T035),
`frontend/components/admin/CourseParticipationsDialog.test.tsx` (T046) et
`frontend/components/admin/CourseParticipationsDialog.tsx` (T050).

**Conséquence pratique** : US3 et US4 ne peuvent pas être menées en parallèle
d'US1 et d'US2 respectivement sur leur part frontend. Leur part **backend**, en
revanche, l'est entièrement.

### Within Each User Story

- Les tests sont écrits et **échouent** avant l'implémentation (Principe III).
- Modèle avant repository, repository avant service, service avant route.
- Backend avant le composant qui le consomme.
- Story terminée avant de passer à la priorité suivante.

### Parallel Opportunities

- T002 seul en Phase 1.
- T003 seul en Phase 2 (les autres tâches se suivent sur les mêmes fichiers).
- **US2** : T019, T020 et T021 en parallèle (trois fichiers de test distincts).
- **US3** : T030, T031, T032, T033 et T035 en parallèle (cinq fichiers distincts) ; T042 en parallèle de tout le backend.
- **US4** : T045 et T046 en parallèle ; le volet back-office (T046 puis T050) est parallélisable à toute la Phase 7.
- **US5** : T014 et T015 en parallèle, et dès la Phase 1 si on veut.
- **Polish** : T051, T052, T053 et T054 en parallèle — attention, T051 et T054 visent le **même** fichier `docs/api/admin-donnees.md` : les deux se font en une seule passe, pas en parallèle l'une de l'autre.
- **En équipe** : la part backend d'US2 et celle d'US3 sont totalement disjointes et se mènent en parallèle.

---

## Parallel Example: User Story 3

```bash
# Les cinq fichiers de test de US3, en parallèle — cinq fichiers distincts :
Task: "T030 resolve respecte club_locked dans backend/tests/test_repositories/test_athlete_repository.py"
Task: "T031 update_athlete pose le drapeau dans backend/tests/test_services/test_admin_actions.py"
Task: "T032 un réimport ne réécrit pas un club figé dans backend/tests/test_services/test_import_service.py"
Task: "T033 le champ club au PATCH, club_locked jamais exposé dans backend/tests/test_api/test_admin_data_api.py"
Task: "T035 l'aller-retour de la révision club_locked dans backend/tests/test_migrations.py"

# Puis l'implémentation, séquentielle : modèle → migration → repository → service → schéma
```

## Parallel Example: Polish

```bash
Task: "T051 + T054 documenter la feature et son renvoi dans docs/api/admin-donnees.md"   # même fichier, une passe
Task: "T052 club_locked dans backend/app/models/AGENTS.md"
Task: "T053 athletes/ dans l'inventaire de frontend/AGENTS.md"
```

---

## Implementation Strategy

### MVP First (US1 seule)

1. Phase 1 : Setup.
2. Phase 2 : Foundational — **critique**, verrouille SC-004. Dérouler le scénario 11 à son checkpoint.
3. Phase 3 : US1.
4. **STOP et VALIDER** : dérouler les scénarios 1, 2 et 3 de `quickstart.md`.
5. Livrable en soi : corriger un nom sans quitter la page, zéro navigation contre trois (SC-001).

### Incremental Delivery

1. Setup + Foundational → la frontière cliente existe, le visiteur anonyme ne paie rien : **scénario 11**.
2. \+ US1 → **MVP**, scénarios 1 à 3.
3. \+ US5 → la règle « si et seulement si » est vérifiée, scénarios 9 et 10.
4. \+ US2 → scénarios 4, 5 et 12 ; le geste irréversible est enfin tracé.
5. \+ US3 → scénarios 6 et 7 ; la correction du club prime sur l'import.
6. \+ US4 → scénario 8, et le contrôle back-office du scénario 9.
7. Polish → docs, reprise des 12 scénarios, revues de fin de branche.

Chaque étape ajoute de la valeur sans casser la précédente.

### Parallel Team Strategy

Phases 1 et 2 ensemble. Ensuite :

- Développeur A : US1 puis US3 côté frontend (même fichier — séquentiel par nature).
- Développeur B : la part backend d'US2 (T019 → T025) puis celle d'US3 (T030 → T041, T035 inclus).
- Développeur C : US2 puis US4 côté frontend (même fichier — séquentiel).
- US5 : T014 et T015 par n'importe qui, dès le départ.
- Le volet back-office d'US4 (T046 puis T050) : par n'importe qui, à n'importe quel moment — il ne touche aucun fichier de la page coureur.

---

## Notes

- `[P]` = fichiers distincts, aucune dépendance — la table des conflits de fichiers ci-dessus est la référence.
- **Voir les tests échouer** avant d'implémenter : le Principe III est non-négociable, et un test qui passe du premier coup ne prouve rien.
- Commit par tâche ou par groupe cohérent, en Conventional Commits.
- S'arrêter à n'importe quel checkpoint pour valider une story seule.
- **Quatre pièges propres à cette feature**, tous documentés dans `research.md` :
  aucun `<button>` à l'intérieur du `<Link>` de la ligne (D9) ; jamais de
  `birth_date` sans `athletes:read` (D7) ; la page ne bascule **jamais** sur
  `serverFetchAuthed` (D11) ; et la réattribution exige **deux** pouvoirs aux
  **deux** endroits où elle est offerte (D6) — masquer sur un écran et laisser
  l'autre annoncer un 403 reviendrait à consigner le bug au lieu de le corriger.
