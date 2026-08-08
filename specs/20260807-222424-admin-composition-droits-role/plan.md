# Implementation Plan: Écran de composition des droits d'un rôle

**Branch**: `admin-cran-de-composition-des-droits-dun-r-le` | **Date**: 2026-08-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260807-222424-admin-composition-droits-role/spec.md`

## Summary

**Frontend seul, zéro ligne de backend.** Les six ressources dont l'écran a
besoin sont livrées par #115 et ne bougent pas ; l'inventaire des pouvoirs
arrive déjà regroupé par fonctionnalité, avec libellé et description en
français, et `RoleRead` porte de quoi tout afficher sans second appel.

L'écran vit sous `/admin/droits`, sur le patron de `AllowedEmailsTable` : un
composant client, deux `useQuery`, trois `useMutation`, un `messageDErreur`
local pour les 401/403. La densité — dix-huit pouvoirs, sept fonctionnalités —
est absorbée par deux primitives déjà présentes plutôt que par une mise en page
inventée : un **accordéon** (`ui/accordion.tsx`), un rôle par panneau, et à
l'intérieur un `<fieldset>`/`<legend>` **par fonctionnalité**, avec des cases à
cocher natives — le patron déjà utilisé par `SeasonSelector` et
`EditCourseDialog`. Aucun composant `ui/` nouveau, aucune dépendance ajoutée.

Trois points où l'écran doit dire la vérité plutôt que la deviner :

- **Le statut de superutilisateur remplace la grille**, il ne la coche pas. Un
  rôle qui franchit tout n'affiche pas dix-huit cases cochées : il affiche la
  phrase qui le dit, et un rappel que les pouvoirs livrés demain sont compris.
- **La non-amplification se lit sur la session**, sans appel supplémentaire :
  une case dont le code n'est pas dans `session.permissions` est **figée dans
  son état courant**, jamais masquée. Le caractère superutilisateur de
  l'utilisateur connecté, lui, se **déduit exactement** — un de ses `roles`
  porte `is_superuser` dans la liste déjà chargée — et non par « il a les
  dix-huit codes », qui serait une inférence fausse.
- **`PATCH` n'envoie que les champs modifiés.** C'est ce qui fait qu'un simple
  renommage ne purge pas les codes périmés du rôle : `permissions` **remplace**
  l'ensemble, donc l'envoyer systématiquement transformerait chaque correction
  de libellé en purge silencieuse.

L'énoncé de #240 est suivi partout sauf sur un point, tranché par le code : un
rôle `is_system` reste **renommable et recomposable**, seule sa suppression est
refusée (cf. `spec.md` §Assumptions, [research.md](./research.md) §D1).

## Technical Context

**Language/Version**: TypeScript 5 / Next.js 16 (App Router), React 19. Aucun code Python.

**Primary Dependencies**: TanStack Query, shadcn/ui sur Base UI (`@base-ui/react`), Tailwind, `sonner`. **Aucune dépendance nouvelle** — les cases à cocher sont natives, l'accordéon et la boîte de dialogue existent déjà dans `components/ui/`.

**Storage**: N/A — l'écran ne persiste rien qui lui soit propre.

**Testing**: Vitest + RTL (`npm test`, depuis `frontend/`). Aucun test backend n'est touché : le contrat consommé est déjà couvert par `backend/tests/test_auth/`.

**Target Platform**: Vercel (frontend), backend Render inchangé.

**Project Type**: web — seul `frontend/` est modifié.

**Performance Goals**: **deux requêtes au chargement** (l'inventaire, la liste des rôles), aucune par rôle déplié — `RoleRead` porte déjà sa composition. L'inventaire est servi depuis le code Python : `staleTime: Infinity`, il ne change qu'au déploiement.

**Constraints**: l'écran exige **`roles:read`** pour lire et **`roles:write`** pour écrire ; l'entrée de navigation est portée par le second (déjà déclarée ainsi). Un 403 doit produire un message d'accès refusé, jamais une liste vide — le défaut fermé deux fois sur `PendingProvidersTable` puis `AllowedEmailsTable`. `RoleUpdate` porte `extra="forbid"` : un champ hors contrat (`slug`, `is_system`, `holders`) rend **422**, pas un silence.

**Scale/Scope**: 3 rôles livrés, une poignée à terme ; 18 pouvoirs, 7 fonctionnalités. Pas de pagination, pas de recherche, pas d'état dans l'URL. 1 route, 1 composant d'écran (plus deux composants internes), 5 hooks, 5 méthodes de client, 5 types, 2 clés de cache, 1 ligne de navigation.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | UI, messages d'erreur affichés et commentaires de règle métier en français ; identifiants, types et noms de fichiers en anglais (`RoleRead`, `PermissionGroup`, `useRoles`). Les libellés des pouvoirs ne sont **pas** traduits côté front : ils arrivent en français du serveur, seul endroit où ils sont écrits. |
| II | Architecture en couches (api → services → repositories → DB) | N/A | Aucun code backend. Le pendant front — `lib/api/client.ts` seul appelant `fetch`, `lib/queries/` seul détenteur des clés de cache, composants sans `fetch` — est respecté. |
| III | TDD sans réseau (non-négociable) | ✅ | Chaque tâche pose son test Vitest rouge d'abord. Le réseau est mocké au niveau `apiClient`, patron de `AllowedEmailsTable.test.tsx` (`vi.hoisted` + `vi.mock`). |
| IV | Contrats API et CLI stables | ✅ | Aucune ressource modifiée, aucune ajoutée. L'écran est un **consommateur** de `/api/v1/admin/{permissions,roles}`. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre de lecture transverse (`scope`, `federal_only`, `seasons`) n'intervient. |
| VI | Simplicité / YAGNI | ✅ | Zéro dépendance, zéro primitive `ui/` nouvelle (accordéon et dialogue existants, cases natives déjà employées deux fois dans le dépôt) ; sélection en `useState` plutôt qu'en paramètre d'URL ; pas de verrouillage optimiste que l'API ne supporte pas ; un troisième `messageDErreur` local plutôt qu'une fabrique paramétrée (voir [research.md](./research.md) §D9). |

**Re-check après Phase 1** : aucun statut ne bouge. Les deux points qui
auraient pu faire basculer le Principe VI sont tranchés dans `research.md` et
vont tous deux vers le moins de code : la composition initiale à la création
réutilise le **même** composant de grille que l'édition (§D6), et le caractère
superutilisateur de l'utilisateur connecté se déduit des données déjà chargées
plutôt que d'un champ à ajouter à `GET /auth/me` (§D4).

## Project Structure

### Documentation (this feature)

```text
specs/20260807-222424-admin-composition-droits-role/
├── plan.md              # Ce fichier
├── research.md          # Phase 0 — les dix décisions et leurs alternatives rejetées
├── data-model.md        # Phase 1 — les types front, et ce qui se déduit sans appel
├── quickstart.md        # Phase 1 — validation de bout en bout
├── contracts/
│   └── ui.md            # Ce que l'écran consomme, et ce qu'il promet à l'œil
├── checklists/
│   └── requirements.md  # Qualité de la spec (déjà produit)
└── tasks.md             # Phase 2 — /speckit-tasks, PAS produit ici
```

### Source Code (repository root)

```text
frontend/
├── app/admin/droits/
│   └── page.tsx                       # NOUVEAU — coquille serveur, patron de app/admin/acces/page.tsx
├── components/admin/
│   ├── RolePermissionsEditor.tsx      # NOUVEAU — l'écran : liste en accordéon, composition, gestes
│   ├── RolePermissionsEditor.test.tsx # NOUVEAU — Vitest + RTL
│   ├── PermissionGrid.tsx             # NOUVEAU — un <fieldset> par fonctionnalité, cases natives
│   ├── PermissionGrid.test.tsx        # NOUVEAU
│   ├── CreateRoleDialog.tsx           # NOUVEAU — nom, identifiant, description, composition initiale
│   └── CreateRoleDialog.test.tsx      # NOUVEAU
├── components/layout/
│   ├── nav.config.ts                  # MODIFIÉ — `u-droits` : href posé, `soon` retiré
│   └── AppNav.test.tsx                # MODIFIÉ — l'entrée cesse d'être `soon` et devient cliquable
├── lib/
│   ├── api/client.ts                  # MODIFIÉ — 5 méthodes (inventaire + 4 sur les rôles)
│   ├── queries/admin.ts               # MODIFIÉ — 5 hooks + invalidations
│   ├── queries/admin.test.ts          # MODIFIÉ — les 5 hooks
│   ├── queries/keys.ts                # MODIFIÉ — 2 clés
│   └── types.ts                       # MODIFIÉ — 5 types
└── (backend/ : aucun fichier touché)
```

**Structure Decision** : web, `frontend/` seul. Le découpage en trois composants
suit la ligne de `components/admin/` — un composant par écran, plus les blocs
qu'il monte (`CoursesAdminTable` + `EditCourseDialog` + `DeleteCourseDialog`).
`PermissionGrid` est extrait parce qu'il est monté **deux fois** — dans
l'édition d'un rôle et dans la création —, pas par principe.

## Complexity Tracking

> Aucun principe en ⚠️ : aucune violation à justifier.

**Portée du Principe III, pour que le gate n'ait rien à interpréter.** Trois
tâches de `tasks.md` — T001 (types), T002 (clés de cache), T003 (méthodes de
client) — ne sont précédées d'aucun test, et ce n'est **pas** une dérogation :
elles ne portent aucune logique métier. Pas de branche, pas de décision, pas de
calcul — une déclaration de types, deux constantes, cinq appels `fetch` qui ne
font que composer une URL. Le Principe III vise « toute nouvelle logique
métier » ; il n'y a rien ici à faire échouer d'abord.

Leur filet est double et il est réel : `npm run build` en TypeScript strict
(une déclaration fausse ne compile pas) et les tests des hooks qui les
consomment (T004, T016, T026), qui échoueraient si une clé ou une méthode
manquait. **Toutes les autres tâches portant de la logique ont leur test
rouge en amont**, sans exception.
