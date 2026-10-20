# Objectifs de la saison dans le récap (#1669) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** le récap `/mon-espace/recap?saison=` d'une saison close affiche les objectifs de cette saison, en lecture seule, chacun « Atteint » ou « Non atteint » ; la section n'existe pas sans objectif.

**Architecture:** aucun changement backend (`GET /auth/me/goals?season=` existe). La branche part de PR #1723 (#1721), qui fait déjà transmettre la saison à `getSeasonGoals(season)` et met la saison dans la clé de `useSeasonGoals(enabled, season)`. Un petit composant `RecapObjectifs` lit `useSeasonGoals(true, season)` et réutilise `libelle` / `progression` de `SeasonGoals.tsx`, exportés pour l'occasion. `SeasonRecap` le rend après « En chiffres ».

**Tech Stack:** Next.js 16, TanStack Query, vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-20-mon-espace-vague-2-design.md` (section « #1669 »).

## Global Constraints

- Lecture seule : ni bouton, ni formulaire, ni lien de modification dans le récap.
- Texte visible en français, vouvoiement ; identifiants, tests, commits en anglais.
- Jamais de tiret (—, –, -) comme ponctuation dans les commentaires, textes UI, messages de commit ou corps de PR.
- Un squelette ou un état vide teste `isPending`, jamais `isLoading` (`frontend/AGENTS.md`, #1290).
- Ne pas toucher : config vitest, `frontend/app/login`, `/account`, `components/auth`, la fiche athlète, les écrans jeunes.
- Aucun trailer `Co-Authored-By`, aucune mention d'IA.

## Review Focus

- Saison sans objectif : la section n'apparaît pas (ni titre, ni « Aucun objectif »).
- Erreur de lecture des objectifs : la section ne s'affiche pas et le reste du récap reste visible (le récap n'est pas bloqué par un bonus).
- Saison du récap sans résultat validé (« Aucun résultat validé sur cette saison ») mais avec objectifs : les objectifs s'affichent quand même, tous « Non atteint ».
- Objectif « Non atteint » : statut en texte, pas seulement une couleur.

---

### Task 1: section « Mes objectifs » du récap

**Files:**
- Modify: `frontend/components/dashboard/SeasonGoals.tsx` (exporter `libelle` et `progression`, sans changer leur corps)
- Create: `frontend/components/dashboard/RecapObjectifs.tsx`
- Modify: `frontend/components/dashboard/SeasonRecap.tsx` (rendre `<RecapObjectifs season={season} />` après la carte « En chiffres » ; dans la branche « Aucun résultat validé », après cette carte)
- Test: `frontend/components/dashboard/RecapObjectifs.test.tsx` ; ajuster `SeasonRecap.test.tsx` s'il mocke l'API sans `getSeasonGoals`.

**Interfaces:**
- Consumes: `useSeasonGoals(enabled: boolean, season: number)` de `frontend/lib/queries/auth.ts` (PR #1723), `SeasonGoal` (`frontend/lib/types.ts`, champ `reached: boolean`).
- Produces: `export function RecapObjectifs({ season }: { season: number }): JSX.Element | null`.

- [ ] **Step 1: tests qui échouent** dans `RecapObjectifs.test.tsx` (mock d'`apiClient.getSeasonGoals` comme `SeasonGoals.test.tsx`) :
  - `requests the recap season` : `getSeasonGoals` appelé avec `2024`.
  - `shows each goal with its final outcome` : un objectif `reached: true` et un `reached: false` → titre « Mes objectifs », textes « Atteint » et « Non atteint », libellé et progression de chacun (mêmes chaînes que `SeasonGoals`).
  - `renders nothing without goals` : `[]` → `container` vide.
  - `renders nothing when goals fail to load` : rejet → `container` vide.
  - `is read only` : aucun `button` rendu.
- [ ] **Step 2:** `npx vitest run components/dashboard/RecapObjectifs.test.tsx` → FAIL.
- [ ] **Step 3:** implémenter : `Card` + `Eyebrow` « Mes objectifs » comme les cartes voisines du récap ; `null` tant que `isPending`, en erreur ou sur liste vide ; statut en `MetaPill` (« Atteint » `accent`, « Non atteint » neutre).
- [ ] **Step 4:** brancher dans `SeasonRecap` ; `npx vitest run components/dashboard` → PASS.
- [ ] **Step 5:** `npm test`, `npm run lint`, `npx tsc --noEmit` propres.
- [ ] **Step 6: Commit** `feat(mon-espace): show the season goals and their outcome in the season recap (#1669)`.
