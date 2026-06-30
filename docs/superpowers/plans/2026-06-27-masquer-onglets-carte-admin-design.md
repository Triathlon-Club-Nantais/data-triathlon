# Masquer les onglets Carte & Admin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Masquer les onglets **Carte** et **Admin** de la barre de navigation du frontend, sans rien supprimer (pages, routes et code conservés, réversible en une ligne).

**Architecture:** Changement localisé à un seul fichier applicatif, `frontend/components/layout/TcnTopbar.tsx`. On marque les entrées masquées du tableau `NAV` avec un drapeau `hidden: true` et on les filtre avant le rendu. Un test Vitest + RTL fige le contrat de visibilité de la nav.

**Tech Stack:** Next.js 16 (App Router), TypeScript strict, React 19, Vitest 4 + @testing-library/react (jsdom), ESLint (eslint-config-next).

## Global Constraints

- **Langue** : UI, commentaires et messages en **français** (avec accents).
- **TypeScript strict** : le build (`npm run build`) doit passer en mode strict + RSC.
- **Masquage, pas suppression** : aucune suppression de page, route, composant ni de code data-layer/API. Les entrées `/carte` et `/admin` restent présentes dans `NAV`, marquées `hidden: true`.
- **Onglet Club** : aucune modification (conservé tel quel).
- **Back-end** : aucun changement. Les chemins `/admin/...` dans `lib/api/client.ts` / `lib/api/server.ts` sont des chemins d'API back-end — **ne pas toucher**.
- Commits : Conventional Commits (`feat:`, `fix:`, `test:`…).
- **Toutes les commandes frontend se lancent depuis `frontend/`.**

---

### Task 1: Masquer Carte & Admin dans la nav (drapeau `hidden`) + test de non-régression

Tâche unique : le test fige le contrat de visibilité de la barre de navigation, et la modification du tableau `NAV` est ce qui le fait passer. Les deux forment un seul cycle TDD.

**Files:**
- Create: `frontend/components/layout/TcnTopbar.test.tsx`
- Modify: `frontend/components/layout/TcnTopbar.tsx` (tableau `NAV` lignes 9-15 ; rendu `.map` ligne 42)

**Interfaces:**
- Consumes: composant exporté `TcnTopbar` depuis `frontend/components/layout/TcnTopbar.tsx` (export nommé `export function TcnTopbar()`).
- Produces: rien de consommé par une tâche ultérieure (plan mono-tâche).

**Contexte vérifié (état actuel du fichier) :**

```ts
// frontend/components/layout/TcnTopbar.tsx, lignes 9-15
const NAV = [
  { href: "/dashboard", label: "Tableau de bord" },
  { href: "/resultats", label: "Résultats" },
  { href: "/club", label: "Club" },
  { href: "/carte", label: "Carte" },
  { href: "/admin", label: "Admin" },
];
```

```tsx
// frontend/components/layout/TcnTopbar.tsx, ligne 42 (dans <nav>)
{NAV.map((item) => {
```

`TcnTopbar` est `"use client"` et utilise `usePathname` + `useRouter` de `next/navigation`, ainsi que `apiClient` de `@/lib/api/client`. Ces deux modules doivent être mockés dans le test. `apiClient` n'est appelé que par le sous-composant `AthletePicker` (ouvert au clic) ; il suffit de le neutraliser pour éviter tout effet de bord à l'import.

Le projet a déjà l'outillage : `vitest.config.ts` (`environment: "jsdom"`, `globals: true`, `setupFiles: ["./test/setup.ts"]`, alias `@` → racine `frontend/`). Le pattern de mock de `next/navigation` existe déjà dans `components/results/EventList.test.tsx`.

---

- [ ] **Step 1: Écrire le test qui échoue**

Créer `frontend/components/layout/TcnTopbar.test.tsx` :

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TcnTopbar } from "./TcnTopbar";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: { listParticipations: vi.fn().mockResolvedValue([]) },
}));

describe("TcnTopbar — visibilité des onglets (issue #10)", () => {
  it("affiche les onglets conservés : Tableau de bord, Résultats, Club", () => {
    render(<TcnTopbar />);
    expect(screen.getByRole("link", { name: "Tableau de bord" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Résultats" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Club" })).toBeInTheDocument();
  });

  it("n'affiche pas les onglets masqués : Carte et Admin", () => {
    render(<TcnTopbar />);
    expect(screen.queryByRole("link", { name: "Carte" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd frontend && npm test -- TcnTopbar`
Expected: FAIL — le second test échoue car les liens « Carte » et « Admin » sont actuellement rendus (`queryByRole(...)` ≠ null). Le premier test passe déjà.

- [ ] **Step 3: Implémenter le masquage — drapeau `hidden` sur `NAV`**

Dans `frontend/components/layout/TcnTopbar.tsx`, remplacer le tableau `NAV` (lignes 9-15) par :

```ts
// `hidden: true` → onglet temporairement masqué (issue #10). Code et page
// conservés ; réafficher en retirant le drapeau.
const NAV = [
  { href: "/dashboard", label: "Tableau de bord" },
  { href: "/resultats", label: "Résultats" },
  { href: "/club", label: "Club" },
  { href: "/carte", label: "Carte", hidden: true },
  { href: "/admin", label: "Admin", hidden: true },
];
```

- [ ] **Step 4: Filtrer les onglets masqués au rendu**

Dans le même fichier, remplacer (ligne 42) :

```tsx
          {NAV.map((item) => {
```

par :

```tsx
          {NAV.filter((item) => !item.hidden).map((item) => {
```

Le reste du `.map` (calcul de `active`, `<Link>`) est **inchangé**.

- [ ] **Step 5: Lancer le test pour vérifier qu'il passe**

Run: `cd frontend && npm test -- TcnTopbar`
Expected: PASS — les deux tests verts (Carte et Admin absents, les trois autres présents).

- [ ] **Step 6: Vérifier lint, build et suite de tests complète**

Run: `cd frontend && npm run lint && npm test && npm run build`
Expected: lint propre (l'objet hétérogène de `NAV` reste valide en TS — `hidden` est une propriété optionnelle inférée) ; tous les tests verts ; build prod OK en TS strict.

- [ ] **Step 7: Vérifier que c'est bien un masquage (preuve de réversibilité)**

Run: `grep -n "Carte\|Admin" frontend/components/layout/TcnTopbar.tsx`
Expected: les deux entrées existent toujours et portent `hidden: true`.

Optionnel (preuve manuelle, hors CI) : `cd frontend && npm run dev` puis ouvrir `/carte` et `/admin` par URL directe → les pages se rendent toujours (non supprimées).

- [ ] **Step 8: Commit**

```bash
git add frontend/components/layout/TcnTopbar.tsx frontend/components/layout/TcnTopbar.test.tsx
git commit -m "feat(frontend): masque les onglets Carte et Admin de la nav (issue #10)"
```

---

## Self-Review

**1. Couverture de la spec :**
- §Périmètre 1 (drapeau `hidden` + filtre au rendu) → Steps 3-4. ✔
- §Périmètre 2 (test Vitest + RTL : Tableau de bord/Résultats/Club présents, Carte/Admin absents) → Steps 1-2, 5. ✔
- §Vérification (`lint`, `build`, `test`, `grep` `hidden: true`) → Steps 6-7. ✔
- §Hors périmètre (pas de suppression de page/route/composant/API, Club inchangé, back-end intact) → Global Constraints + modification limitée au seul `NAV`/`.map`. ✔
- §Réversibilité (retirer `hidden: true`) → documenté dans le commentaire de `NAV` (Step 3) et le grep (Step 7). ✔

**2. Placeholders :** aucun TBD/TODO ; tout le code (test + diff) est complet et littéral.

**3. Cohérence des types/noms :** export `TcnTopbar`, tableau `NAV`, propriété `hidden`, libellés (« Tableau de bord », « Résultats », « Club », « Carte », « Admin ») cohérents entre le fichier source vérifié, le test et les étapes. Les mocks (`usePathname`, `useRouter` de `next/navigation` ; `apiClient.listParticipations` de `@/lib/api/client`) correspondent aux imports réels du composant.
