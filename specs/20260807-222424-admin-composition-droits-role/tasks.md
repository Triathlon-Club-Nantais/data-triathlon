---

description: "Tâches — écran de composition des droits d'un rôle"
---

# Tasks: Écran de composition des droits d'un rôle

**Input**: Design documents from `specs/20260807-222424-admin-composition-droits-role/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/ui.md](./contracts/ui.md), [quickstart.md](./quickstart.md)

**Tests**: Principe III (non-négociable) — chaque tâche portant de la logique est
précédée de son test Vitest rouge. T001, T002 et T003 en sont exemptes parce
qu'elles ne portent aucune logique métier ; la portée est tranchée dans
[plan.md](./plan.md) §Complexity Tracking, seul endroit que lit le gate
constitutionnel.

**Organization**: par user story, dans l'ordre de priorité de `spec.md`.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers distincts, aucune dépendance ouverte)
- **[Story]** : US1, US2, US3
- Chemins exacts dans chaque description

## Path Conventions

Web app — **seul `frontend/` est modifié**. Aucun fichier de `backend/` n'est
touché : les six ressources consommées sont livrées par #115.

---

## Phase 1: Setup (déclarations partagées)

**Purpose**: le vocabulaire que tout le reste consomme. Aucune logique, donc
aucun test propre (voir §Tests ci-dessus).

- [X] T001 [P] Déclarer `Permission`, `PermissionGroup`, `Role`, `RoleCreate`, `RoleUpdate` dans `frontend/lib/types.ts`, à l'identique de `data-model.md` §Types transportés — `RoleUpdate` ne porte **ni** `slug` **ni** `is_system` **ni** `holders` (`extra="forbid"` côté serveur rend 422)
- [X] T002 [P] Ajouter `adminPermissions()` → `["admin-permissions"]` dans `frontend/lib/queries/keys.ts`. **Pas de clé pour la liste des rôles** : #239 a posé `roles()` → `["roles"]`, même ressource, même cache (`research.md` §D15)
- [X] T003 [P] Ajouter les **cinq** méthodes dans `frontend/lib/api/client.ts` : `listPermissions()`, `listRoles()`, `createRole(body)`, `updateRole(id, champs)`, `deleteRole(id)` — patron de `listAllowedEmails` / `updateCourse`, `deleteRole` typée `request<null>`. Le tableau de `contracts/ui.md` en compte six : il énumère des **gestes**, et la bascule du statut de superutilisateur passe par le même `PATCH` que la recomposition

**Checkpoint**: `npm run build` compile ; rien n'est encore appelé.

---

## Phase 2: Foundational (lecture — bloque toutes les stories)

**Purpose**: les deux `useQuery` sans lesquels aucun écran n'affiche quoi que ce
soit. **⚠️ Aucune story ne peut démarrer avant.**

- [X] T004 Écrire les tests rouges des hooks de lecture dans `frontend/lib/queries/admin.test.ts` : `useAdminPermissions` appelle `apiClient.listPermissions` sous la clé `["admin-permissions"]`, `useRoles` appelle `apiClient.listRoles` sous `["roles"]`, et une `ApiError` 403 remonte à l'appelant (elle n'est **pas** avalée en liste vide)
- [X] T005 Implémenter `useAdminPermissions()` et `useAdminRoles()` dans `frontend/lib/queries/admin.ts` — l'inventaire en `staleTime: Infinity` (servi depuis le code Python, il ne change qu'au déploiement), `retry: false` sur les deux pour qu'un 403 s'affiche sans trois tentatives

**Checkpoint**: les données arrivent ; les stories peuvent démarrer.

---

## Phase 3: User Story 1 — Lire la composition des rôles (Priority: P1) 🎯 MVP

**Goal**: répondre à « que peut faire ce rôle ? » sans ouvrir la base.

**Independent Test**: sur une base neuve, l'écran montre les trois rôles livrés
avec leur composition lisible, groupée par fonctionnalité, en français.

### Tests for User Story 1

> **Écrire d'abord, vérifier qu'ils échouent** (Principe III).

- [X] T006 [P] [US1] Tests de la grille en lecture dans `frontend/components/admin/PermissionGrid.test.tsx` : un `<fieldset>` par fonctionnalité dans **l'ordre reçu**, `<legend>` portant `feature` verbatim, chaque case étiquetée par `label` et décrite par `description` — et **jamais** le code technique seul (FR-002, FR-003)
- [X] T007 [P] [US1] Tests de l'écran en lecture dans `frontend/components/admin/RolePermissionsEditor.test.tsx` : les rôles listés avec nom, description et nombre de porteurs (FR-001) ; un rôle `is_superuser` affiche la **phrase de statut** et non dix-huit cases cochées (FR-005) ; `stale_permissions` apparaît dans un bloc distinct annoncé comme sans effet (FR-004) ; un 403 rend « Accès refusé » et un 401 « Session expirée », jamais une liste vide ni « aucun rôle » (FR-017, FR-018)
- [X] T008 [P] [US1] Test de navigation dans `frontend/components/layout/AppNav.test.tsx` : l'entrée « Droits des rôles » est rendue et pointe `/admin/droits` pour une session portant `roles:write` (FR-021)

### Implementation for User Story 1

- [X] T009 [US1] Créer `frontend/components/admin/PermissionGrid.tsx` : un `<fieldset>`/`<legend>` par `PermissionGroup`, une `<input type="checkbox">` native par pouvoir (patron `EditCourseDialog.tsx:121`), `htmlFor`/`id` sur l'étiquette et `aria-describedby` sur la description ; props `{ groupes, coches, onToggle?, disabledCodes?, raisons? }` — sans `onToggle`, la grille est en lecture seule
- [X] T010 [US1] Créer `frontend/components/admin/RolePermissionsEditor.tsx` en **lecture seule** : `Accordion` (`components/ui/accordion.tsx`), un rôle par panneau, en-tête `nom · marqueurs · N porteurs` en `Badge`, panneau montant `PermissionGrid` ; `Skeleton` au chargement, `EmptyState` sur erreur
- [X] T011 [US1] Ajouter dans le même fichier le `messageDErreur(erreur)` local — 401 « Session expirée », 403 « Accès refusé » (le texte de `contracts/ui.md` §Messages d'erreur), autre « Rôles indisponibles » — sur le patron de `AllowedEmailsTable.tsx` ; **un troisième exemplaire assumé**, pas une fabrique (`research.md` §D9)
- [X] T012 [US1] Rendre le bloc des codes périmés sous la grille : code brut (aucun libellé n'existe plus), mention « sans effet », distinct des cases de l'inventaire
- [X] T013 [US1] Rendre le bloc de statut d'un rôle `is_superuser` : la phrase — franchit tout pouvoir, **y compris ceux livrés après lui** — et la grille en dessous, inerte et signalée comme telle (`research.md` §D5)
- [X] T014 [P] [US1] Créer `frontend/app/admin/droits/page.tsx` : `PageShell` + `PageHeader` (eyebrow « Gestion des utilisateurs », titre « Droits des rôles ») + `RolePermissionsEditor`, patron de `app/admin/acces/page.tsx`
- [X] T015 [P] [US1] Dans `frontend/components/layout/nav.config.ts`, entrée `u-droits` : poser `href: "/admin/droits"`, retirer `soon`, laisser `permission: "roles:write"` — et retirer la mention de #240 du commentaire des « trois écrans manquants »

**Checkpoint**: l'écran se lit de bout en bout. §3 du `quickstart.md` passe.

---

## Phase 4: User Story 2 — Recomposer un rôle existant (Priority: P2)

**Goal**: cocher, décocher, renommer — et que le serveur ne refuse rien qui ait
été offert.

**Independent Test**: retirer un pouvoir au « Validateur », recharger, constater
le changement.

### Tests for User Story 2

- [X] T016 [P] [US2] Test du hook dans `frontend/lib/queries/admin.test.ts` : `useUpdateRole` appelle `apiClient.updateRole(id, champs)` et invalide `["roles"]` **et** `["session"]` (recomposer un rôle qu'on porte soi-même est le cas nominal)
- [X] T017 [P] [US2] Tests de la grille éditable dans `frontend/components/admin/PermissionGrid.test.tsx` :
  - une case dont le code est dans `disabledCodes` est `disabled`, **conserve son état** (ni décochée ni masquée) et porte sa raison en texte lié par `aria-describedby` (FR-014) ;
  - **un code périmé reste retirable par une session aux pouvoirs limités** : avec `disabledCodes` couvrant tout l'inventaire, le bloc des codes périmés reste actif (FR-016). C'est l'invariant que `authorization.assert_may_grant` appelle « la condition de réversibilité » — sans lui, un rôle traînant un code périmé deviendrait immodifiable pour tout le monde, et `is_system` ou attribué, indélébile
- [X] T018 [P] [US2] Tests de l'édition dans `frontend/components/admin/RolePermissionsEditor.test.tsx` :
  - renommer seul n'envoie **que** `{name}` — pas `permissions` (FR-007, `research.md` §D6) ;
  - recomposer envoie `{permissions}` avec l'ensemble complet des codes cochés (FR-008) ;
  - un rôle `is_system` reste renommable et recomposable (FR-013, `research.md` §D1) ;
  - **le panneau d'édition n'expose aucun champ d'identifiant** : le slug est fixé à la création, et `RoleUpdate` le refuse par `extra="forbid"` — 422, pas un silence (FR-010) ;
  - un rôle portant des codes périmés affiche l'avertissement de purge **avant** validation, et l'enregistrement de la composition les emporte (FR-011) ;
  - un refus (403/409) affiche le message du serveur **verbatim** et l'état affiché retombe sur celui du serveur (FR-019, FR-020) ;
  - la bascule du statut de superutilisateur n'est **pas rendue** pour une session dont aucun rôle ne porte `is_superuser` (FR-015)
- [X] T019 [P] [US2] Test de la déduction dans `frontend/components/admin/RolePermissionsEditor.test.tsx` : la session est superutilisateur **si et seulement si** l'un de ses `roles` correspond par `id` à un rôle `is_superuser` de la liste — porter les dix-huit codes sans un tel rôle ne suffit **pas** (`research.md` §D4)

### Implementation for User Story 2

- [X] T020 [US2] Implémenter `useUpdateRole()` dans `frontend/lib/queries/admin.ts` — `mutationFn: ({ id, champs }: { id: number; champs: RoleUpdate })`, invalidation `["roles"]` + `["session"]`
- [X] T021 [US2] Ajouter le brouillon dans `RolePermissionsEditor.tsx` — `{ roleId, name, description, codes: Set<string> }`, né à l'ouverture du panneau, mort à sa fermeture, **jamais fusionné** avec la réponse du serveur (`data-model.md` §État local)
- [X] T022 [US2] Câbler `useSession()` et calculer, par rôle, `disabledCodes` = les codes hors de `session.permissions`, avec la raison « Vous ne portez pas ce pouvoir. » ; les codes périmés n'y entrent jamais (FR-016)
- [X] T023 [US2] Écrire la diffusion vers `RoleUpdate` selon la table de `data-model.md` §État local — un champ n'est envoyé que s'il a changé
- [X] T024 [US2] Ajouter l'avertissement de purge : visible dès que `role.stale_permissions.length > 0` et que la composition est modifiée, à côté du bouton « Enregistrer »
- [X] T025 [US2] Ajouter la bascule du statut de superutilisateur — geste **distinct** de l'enregistrement de la grille, confirmé par `window.confirm`, rendu seulement si la session est superutilisateur au sens de T019 ; le 409 du dernier administrateur remonte tel quel dans un toast `sonner`

**Checkpoint**: §4, §5 et §7 du `quickstart.md` passent.

---

## Phase 5: User Story 3 — Créer et supprimer un rôle (Priority: P3)

**Goal**: un rôle « Bénévole » qui n'existait pas, et le retrait de celui qui ne
sert plus.

**Independent Test**: créer un rôle à un pouvoir, le voir apparaître à 0
porteur, le supprimer.

### Tests for User Story 3

- [X] T026 [P] [US3] Tests des hooks dans `frontend/lib/queries/admin.test.ts` : `useCreateRole` et `useDeleteRole` appellent le client et invalident `["roles"]` + `["session"]`
- [X] T027 [P] [US3] Tests de la création dans `frontend/components/admin/CreateRoleDialog.test.tsx` : l'identifiant se dérive du nom (minuscules, accents retirés, espaces en tirets — « Bénévole » → `benevole`) et reste corrigeable ; la même `PermissionGrid` y compose l'état initial ; un 409 d'identifiant déjà pris s'affiche **et la saisie est conservée** (US3 scénario 2)
- [X] T028 [P] [US3] Tests de la suppression dans `frontend/components/admin/RolePermissionsEditor.test.tsx` : le bouton est `disabled` sur `is_system` avec « Rôle livré avec l'application. », `disabled` sur `holders > 0` avec le **nombre** de porteurs, actif sinon et confirmé par `window.confirm` (FR-009, FR-012)

### Implementation for User Story 3

- [X] T029 [P] [US3] Implémenter `useCreateRole()` et `useDeleteRole()` dans `frontend/lib/queries/admin.ts`
- [X] T030 [US3] Créer `frontend/components/admin/CreateRoleDialog.tsx` — `Dialog` (`components/ui/dialog.tsx`), champs nom / identifiant / description, `PermissionGrid` pour la composition initiale, dérivation du slug au motif `^[a-z][a-z0-9-]*$`
- [X] T031 [US3] Monter le bouton « Créer un rôle » et le dialogue dans `RolePermissionsEditor.tsx`
- [X] T032 [US3] Ajouter le bouton de suppression dans le panneau, avec sa raison de désactivation en **texte** (pas seulement en `title`) et sa confirmation `window.confirm` (patron `AllowedEmailsTable.tsx`)

**Checkpoint**: §6 du `quickstart.md` passe. Les trois stories sont livrées.

---

## Phase 6: Polish & Cross-Cutting

- [X] T033 [P] Ajouter `admin/droits` à la liste des routes de `frontend/AGENTS.md` §Architecture frontend, et y noter en une phrase que la composition d'un rôle n'invente aucun regroupement — il vient de `GET /admin/permissions`
- [X] T034 [P] Vérifier que `frontend/app/admin/layout.test.tsx` et `frontend/components/layout/AppNav.test.tsx` restent verts : l'entrée cesse d'être `soon`, elle ne devient pas une exception au test « une entrée `soon` n'est pas rendue » (#242)
- [X] T035 Relire l'accessibilité de `frontend/components/admin/PermissionGrid.tsx` et `frontend/components/admin/RolePermissionsEditor.tsx` : chaque case liée à son étiquette (`htmlFor`/`id`), description et raison de désactivation liées par `aria-describedby`, `<legend>` non masqué — une raison qui n'existe que pour l'œil n'existe pas
- [X] T036 Lancer la vérification complète depuis `frontend/` : `npm test`, `npm run lint`, `npm run build` ; puis depuis `backend/` : `uv run pytest -m "not integration"` (doit rester vert — aucun fichier backend touché)
- [~] T037 Dérouler `quickstart.md` de bout en bout sur une base fraîche
      (`uv run python scripts/reset_db.py`). **Partiellement fait** — 21 des 34
      points, à la main, sur base réelle :
  - [X] §2 navigation, §3 lecture, §4 recomposition, §5 codes périmés (fabriqués
        en SQL), §6 création et suppression, §8 refus de lecture, §9 dernier
        administrateur.
  - [ ] §7 non-amplification, §7 bis consultation seule, §7 ter écriture
        concurrente — les trois demandent une seconde session aux pouvoirs
        distincts, que le fournisseur d'identité unique (GitHub) ne donne pas
        sans second compte. `scripts/dev_login.py` lève l'obstacle, mais il n'est
        pas encore versé.

  Le déroulé a rapporté un défaut que les tests ne pouvaient pas voir : une case
  à cocher `disabled` ne change pas d'apparence, donc une case figée était
  indistinguable d'une case cliquable (corrigé, commit suivant).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001–T003)** : aucune dépendance, les trois en parallèle.
- **Foundational (T004–T005)** : dépend du Setup. **Bloque toutes les stories.**
- **US1 (T006–T015)** : dépend de Foundational.
- **US2 (T016–T025)** : dépend de US1 — elle édite le composant que US1 crée.
- **US3 (T026–T032)** : dépend de US1 (la liste et le panneau), **pas** de US2.
- **Polish (T033–T037)** : après les stories retenues.

### User Story Dependencies

- **US1 (P1)** : indépendante. C'est le MVP.
- **US2 (P2)** : greffe l'édition sur le composant de US1. Testable seule une
  fois US1 en place.
- **US3 (P3)** : greffe création et suppression sur le même composant. Ne
  dépend pas de US2 — l'ordre P2 → P3 est un ordre de valeur, pas une chaîne
  technique.

### Within Each User Story

- Les tests d'abord, rouges, **vérifiés rouges** avant toute implémentation.
- `PermissionGrid` avant `RolePermissionsEditor` : le second monte le premier.
- Hooks avant composants.

### Parallel Opportunities

- T001, T002, T003 — trois fichiers distincts.
- T006, T007, T008 — trois fichiers de test distincts.
- T014 et T015 — la page et la navigation ne se touchent pas.
- T016 à T019 — deux fichiers, mais T017 est seul dans `PermissionGrid.test.tsx`
  et T018/T019 se **partagent** `RolePermissionsEditor.test.tsx` : les écrire
  d'un seul tenant plutôt qu'en parallèle.
- T033 et T034 — documentation et vérification de tests existants.

**Fausse parallélisation à éviter** : T009 à T013 touchent tous
`RolePermissionsEditor.tsx` ou `PermissionGrid.tsx`. Aucun `[P]` sur cette
tranche, et ce n'est pas un oubli.

---

## Parallel Example: User Story 1

```bash
# Les trois fichiers de test de US1, ensemble :
Task: "Tests de la grille en lecture dans frontend/components/admin/PermissionGrid.test.tsx"
Task: "Tests de l'écran en lecture dans frontend/components/admin/RolePermissionsEditor.test.tsx"
Task: "Test de navigation dans frontend/components/layout/AppNav.test.tsx"

# Puis, une fois le composant écrit, la page et la navigation :
Task: "Créer frontend/app/admin/droits/page.tsx"
Task: "Activer l'entrée u-droits dans frontend/components/layout/nav.config.ts"
```

---

## Implementation Strategy

### MVP (US1 seule)

1. Phase 1 (T001–T003) puis Phase 2 (T004–T005).
2. Phase 3 (T006–T015).
3. **Arrêt et validation** : `quickstart.md` §2 et §3.
4. Livrable en l'état — l'écran répond déjà à « que peut faire ce rôle ? » sans
   base de données, ce qui est la moitié du besoin.

### Livraison incrémentale

1. Setup + Foundational → les données arrivent.
2. + US1 → lecture (MVP).
3. + US2 → recomposition. C'est ici que la feature tient sa promesse.
4. + US3 → création et suppression.
5. Polish → `quickstart.md` complet, vérification, documentation.

## Phase 8 — Correctifs de la revue de code

Quatre défauts relevés en relecture, dont trois qu'aucun test de la livraison ne
voyait. Chacun a été repris **test rouge d'abord**, puis éprouvé par mutation :
la ligne corrigée, remise en arrière, fait bien rougir le test qui la garde.

- [X] T038 Figer les pouvoirs non détenus **dans la modale de création**
      (`figes` remonté au niveau de l'écran, passé aux deux grilles) — FR-014,
      SC-003, `research.md` §D11. Le seul écart à une exigence normative.
- [X] T039 Rendre l'écran en consultation sans `roles:write` — FR-014b, §D12.
- [X] T040 Rapprocher le brouillon de l'état sur lequel il a été ouvert
      (`base`, `signature`, encadré de conflit) — FR-020c, §D13. Corrige du
      même geste l'encadré des codes périmés resté vrai après sa purge.
- [X] T041 Garder localement ce que le serveur refuserait pour sa forme (nom
      vide ou blanc, identifiant hors `^[a-z][a-z0-9-]*$`) — FR-020b, §D14.
- [X] T042 Traiter la session illisible comme une lecture en panne, pas comme
      une absence de pouvoirs — FR-020d.
- [X] T043 Désactiver la bascule de statut tant qu'un brouillon est en cours :
      elle n'envoie que `is_superuser` et la réponse rend l'état d'avant, donc
      l'appliquer jetterait la saisie en annonçant un succès.
- [X] T044 Durcir trois tests complaisants : `ADMIN.permissions` non vide (la
      boucle « aucune case cochée » était vacue), `mockReset` sur `listRoles` /
      `listPermissions` (les compteurs fuyaient d'un test à l'autre), et un cas
      qui monte un `QueryClient` **réessayant** pour que le `retry: false` des
      hooks soit celui du code et non celui du test.

### Fin de branche

`requesting-code-review` → `verification-before-completion` →
`finishing-a-development-branch`. La PR porte `Closes #240` — jeton machine, en
anglais, seule forme que GitHub reconnaît.

---

## Notes

- **Aucun fichier de `backend/` n'est touché.** Une tâche qui en ouvrirait un
  est le signe d'une divergence à instruire, pas d'un travail à faire.
- **Un rôle `is_system` est modifiable** — seule sa suppression est refusée. Si
  une tâche vous conduit à désactiver un renommage sur `is_system`, relire
  `research.md` §D1 avant d'écrire la ligne.
- **`permissions` remplace l'ensemble.** Tout `PATCH` qui l'envoie sans que la
  composition ait changé purge les codes périmés en silence.
- Le regroupement par fonctionnalité vient du serveur. Aucun tri, aucun
  intitulé, aucun ordre écrit côté front.
- Commits : Conventional Commits, un par tâche ou par groupe cohérent.
