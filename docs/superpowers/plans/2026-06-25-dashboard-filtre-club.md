# Page d'accueil verrouillée sur le club — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sur la page d'accueil (`/dashboard`), n'afficher que les résultats des membres du TCN et retirer le sélecteur de portée « Tous / Membres TCN ».

**Architecture:** Changement frontend uniquement, dans un seul fichier RSC (`app/dashboard/page.tsx`). On remplace la dérivation du filtre club depuis l'URL (`clubFromScope(sp.scope)`) par la constante `TCN_CLUB_FILTER` (toujours `"nantais"`), et on supprime le composant `<ScopeToggle />` ainsi que son import. Aucun changement backend, schéma ou migration. Le composant `ScopeToggle` reste utilisé tel quel par `/resultats` et `/carte`.

**Tech Stack:** Next.js 16 (App Router, RSC async), TypeScript strict, Vitest + Testing Library, jsdom.

## Global Constraints

- UI, commentaires et messages en **français** (avec accents) — copié de `AGENTS.md`.
- Commits : Conventional Commits (`fix:`, `feat:`…).
- TypeScript strict + RSC : `npm run build` doit passer.
- Tests unitaires sans réseau : `apiServer` (qui fait des `fetch`) doit être mocké dans les tests, jamais appelé réellement.
- Spec de référence (validée par Vincent le 2026-06-25) : `docs/2026-06-24-dashboard-filtre-club-design.md`.
- Périmètre strict : **seule** la page d'accueil change. Ne pas toucher `app/resultats/page.tsx`, `app/carte/page.tsx`, `components/layout/ScopeToggle.tsx`, ni `lib/scope.ts`.

---

### Task 1: Test de rendu du dashboard (portée club forcée + absence du toggle)

On écrit d'abord le test qui décrit le comportement cible : la page appelle l'API avec `club="nantais"` quelles que soient les `searchParams`, et ne rend plus le `ScopeToggle` (libellés « Tous » / « Membres TCN »).

`DashboardPage` est un composant serveur **async** : le test l'appelle comme une fonction (`await DashboardPage({ searchParams })`), puis rend le JSX retourné avec Testing Library. `@/lib/api/server` est mocké pour éviter tout réseau et pour inspecter les arguments passés.

**Files:**
- Create: `frontend/app/dashboard/page.test.tsx`
- Test: `frontend/app/dashboard/page.test.tsx`

**Interfaces:**
- Consumes : export `default` de `@/app/dashboard/page` — `DashboardPage({ searchParams: Promise<Record<string, string | undefined>> }): Promise<JSX.Element>`.
- Consumes : `@/lib/api/server` → `apiServer.getStats(club?: string)`, `apiServer.listEvents(filters)`, `apiServer.listParticipations(filters)` (toutes mockées).
- Consumes : `@/lib/club-constants` → `TCN_CLUB_FILTER === "nantais"`.
- Produces : rien (tâche de test pure ; valide le comportement implémenté en Task 2).

- [ ] **Step 1: Écrire le test qui échoue**

Créer `frontend/app/dashboard/page.test.tsx` :

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { TCN_CLUB_FILTER } from "@/lib/club-constants";

const getStats = vi.fn();
const listEvents = vi.fn();
const listParticipations = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
    getStats: (club?: string) => getStats(club),
    listEvents: (filters: unknown) => listEvents(filters),
    listParticipations: (filters: unknown) => listParticipations(filters),
  },
}));

import DashboardPage from "./page";

const STATS = {
  total: 42,
  athletes: 10,
  events: 5,
  by_type: { "Triathlon S": 30, "Duathlon M": 12 },
  by_month: {},
  recent: [],
};
const EVENTS_PAGE = { items: [], total_events: 5, total_participations: 42 };
const PARTICIPATIONS = [{ rank_overall: 1 }, { rank_overall: 4 }, { rank_overall: 50 }];

beforeEach(() => {
  vi.clearAllMocks();
  getStats.mockResolvedValue(STATS);
  listEvents.mockResolvedValue(EVENTS_PAGE);
  listParticipations.mockResolvedValue(PARTICIPATIONS);
});

async function renderDashboard(searchParams: Record<string, string | undefined> = {}) {
  const ui = await DashboardPage({ searchParams: Promise.resolve(searchParams) });
  return render(ui);
}

describe("DashboardPage", () => {
  it("force la portée club sur tous les appels API, même sans ?scope=club", async () => {
    await renderDashboard({});

    expect(getStats).toHaveBeenCalledWith(TCN_CLUB_FILTER);
    expect(listEvents).toHaveBeenCalledWith(
      expect.objectContaining({ club: TCN_CLUB_FILTER }),
    );
    expect(listParticipations).toHaveBeenCalledWith(
      expect.objectContaining({ club: TCN_CLUB_FILTER }),
    );
  });

  it("ignore ?scope et reste sur le club même si l'URL demande « tous »", async () => {
    await renderDashboard({ scope: undefined }); // pas de scope = ancien mode « Tous »

    expect(getStats).toHaveBeenCalledWith(TCN_CLUB_FILTER);
  });

  it("ne rend plus le sélecteur de portée (Tous / Membres TCN)", async () => {
    await renderDashboard({});

    expect(screen.queryByText("Tous")).toBeNull();
    expect(screen.queryByText("Membres TCN")).toBeNull();
    expect(screen.queryByRole("group", { name: "Portée" })).toBeNull();
  });
});
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run : `cd frontend && npm test -- app/dashboard/page.test.tsx`
Expected : ÉCHEC. Le premier test échoue car `getStats` est appelé avec `undefined` (l'implémentation actuelle fait `clubFromScope(sp.scope)` qui vaut `undefined` sans `?scope=club`), et le troisième échoue car « Tous » / « Membres TCN » sont encore rendus par `<ScopeToggle />`.

> Note : si Testing Library n'arrive pas à rendre `<ScopeToggle />` (client component avec hooks `next/navigation`) avant suppression, le test peut planter au rendu plutôt qu'échouer proprement — c'est attendu et confirme aussi qu'il faut retirer le toggle. La Task 2 résout les deux cas.

---

### Task 2: Verrouiller le dashboard sur le club et retirer le toggle

**Files:**
- Modify: `frontend/app/dashboard/page.tsx` (imports lignes 1-7 ; calcul `club` ligne 25 ; rendu `<ScopeToggle />` ligne 48)
- Test: `frontend/app/dashboard/page.test.tsx` (créé en Task 1)

**Interfaces:**
- Consumes : `@/lib/club-constants` → `TCN_CLUB_FILTER`.
- Produces : `DashboardPage` rend désormais l'en-tête sans `<ScopeToggle />` et appelle l'API avec `club="nantais"` indépendamment de `searchParams`.

- [ ] **Step 1: Remplacer l'import `clubFromScope` par `TCN_CLUB_FILTER`**

Dans `frontend/app/dashboard/page.tsx`, remplacer la ligne :

```tsx
import { clubFromScope } from "@/lib/scope";
```

par :

```tsx
import { TCN_CLUB_FILTER } from "@/lib/club-constants";
```

- [ ] **Step 2: Supprimer l'import de `ScopeToggle`**

Supprimer entièrement la ligne :

```tsx
import { ScopeToggle } from "@/components/layout/ScopeToggle";
```

- [ ] **Step 3: Forcer la portée club**

Remplacer :

```tsx
  const sp = await searchParams;
  const club = clubFromScope(sp.scope);
```

par :

```tsx
  // Page d'accueil = vitrine du club : portée TCN forcée, pas de choix « Tous »
  // (validé par Vincent, issue #6). On garde la signature `searchParams` pour
  // l'App Router, mais le paramètre `?scope` est volontairement ignoré ici.
  await searchParams;
  const club = TCN_CLUB_FILTER;
```

- [ ] **Step 4: Retirer le `<ScopeToggle />` du rendu**

Supprimer la ligne :

```tsx
        <ScopeToggle />
```

(c'est le dernier enfant de la `<div>` d'en-tête, juste après le bloc `<div>…Vue d'ensemble…</div>`). Le `<div>` parent de l'en-tête reste en place avec son unique bloc titre.

- [ ] **Step 5: Lancer le test du dashboard pour vérifier qu'il passe**

Run : `cd frontend && npm test -- app/dashboard/page.test.tsx`
Expected : PASS (3 tests verts).

- [ ] **Step 6: Lint + suite de tests complète + build**

Run : `cd frontend && npm run lint && npm test && npm run build`
Expected : ESLint sans erreur (aucun import inutilisé : `clubFromScope` et `ScopeToggle` ne doivent plus apparaître), Vitest tout vert, build prod (strict TS + RSC) réussi.

- [ ] **Step 7: Commit**

```bash
cd frontend && git add app/dashboard/page.tsx app/dashboard/page.test.tsx
git commit -m "fix(frontend): page d'accueil verrouillée sur le club, sans toggle (#6)

La page d'accueil (dashboard) est la vitrine du TCN : on force club=nantais
et on retire le ScopeToggle. Le toggle reste sur /resultats et /carte, et le
détail d'une course conserve sa double vue (RaceFinishers). Validé par Vincent.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Refs #6"
```

---

### Task 3: Vérification manuelle et passage de la PR en Ready for review

Tâche de finalisation : on s'assure que le rendu réel correspond à l'attendu, puis on bascule la PR #13 (actuellement en Draft) en Ready for review.

**Files:** aucun changement de code.

**Interfaces:** aucune.

- [ ] **Step 1: Vérification manuelle locale**

Run : `cd frontend && npm run dev` (backend lancé en parallèle sur :8001).
Ouvrir `http://localhost:3000/` (redirige vers `/dashboard`). Vérifier :
- les KPI (Dossards, Victoires, Podiums, Top 10) reflètent le club, pas l'ensemble du jeu de données ;
- le sélecteur « Tous / Membres TCN » a disparu de l'en-tête ;
- ajouter `?scope=club` puis `?scope=` à l'URL ne change rien (paramètre ignoré).

Vérifier la non-régression ailleurs : `/resultats` et `/carte` affichent toujours le toggle ; `/courses/<id>` affiche toujours sa double vue « Tous les coureurs » / « Triathlon Club Nantais » (`RaceFinishers`).

- [ ] **Step 2: Pousser et passer la PR en Ready for review**

```bash
git push
gh pr ready 13
```

Expected : la PR #13 n'est plus en Draft ; le commentaire de Vincent est adressé.

---

## Self-Review

**1. Spec coverage** (`docs/2026-06-24-dashboard-filtre-club-design.md`) :
- « Forcer la portée club » → Task 2, Step 3. ✅
- « Retirer le toggle » → Task 2, Steps 2 & 4. ✅
- « Sous-titre conservé » → on ne touche pas à `Vue d'ensemble des performances des athlètes du club` (ligne 46). ✅
- « Hors périmètre : toggle conservé sur /resultats et /carte, double vue déjà présente sur /courses/[id] » → Global Constraints + Task 3 Step 1 (non-régression). ✅
- Tests : « test rendu vérifiant l'absence du ScopeToggle et l'appel API avec club=nantais » → Task 1. ✅
- « npm run build + npm test verts » → Task 2 Step 6. ✅
- « Passer la PR de Draft à Ready » → Task 3 Step 2. ✅

**2. Placeholder scan** : aucun TBD/TODO ; tout le code des steps est complet (test intégral, diffs exacts). ✅

**3. Type consistency** : `TCN_CLUB_FILTER` (string `"nantais"`) utilisé de façon identique dans le test (Task 1) et l'implémentation (Task 2). `getStats(club)`, `listEvents({ club, … })`, `listParticipations({ club, … })` correspondent aux signatures réelles de `apiServer` (`lib/api/server.ts`). ✅
