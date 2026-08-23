# Barre d'outils nommée, état vide unifié, dernières épreuves — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix NAV-5/NAV-6/NAV-7 (issue #483, epic #460, audit #325) on `/dashboard`: give each of the three toolbar controls a visible label and regroup the rank-type toggle with the three stat cards it governs (NAV-5); replace the two-message wall of zeros with one empty state that names the cause and offers a way out when `stats.total === 0` (NAV-6); replace the "favorite events" card (sorted by volume) with a new `RecentCourses` component sorted by date, at zero network cost since the data is already fetched (NAV-7).

**Architecture:** All three fixes live in `frontend/app/(public_restricted)/dashboard/page.tsx` and its immediate dependencies. Two new pure, unit-tested helpers (`seasonAbsenceLabel` in `lib/utils/season.ts`, `sortEventsByDateDesc` in `lib/utils/event.ts`) carry the only new logic; everything else is JSX restructuring and copy. One new presentational server component, `components/dashboard/RecentCourses.tsx`, replaces the inline "Épreuves préférées" card — it takes an already-sorted, already-sliced `EventOut[]` and renders it, no client hooks, no new fetch.

**Tech Stack:** Next.js 16 App Router, TypeScript strict, Vitest + React Testing Library.

**Spec:** `docs/superpowers/specs/2026-08-22-dashboard-toolbar-nav-5-6-7-design.md`

## Global Constraints

- No palette, Anton/Barlow, or `--tcn-*` gradient changes — visual identity is arbitrated and out of scope.
- `components/tcn/` vs `components/ui/` boundary is not re-litigated: `RecentCourses` composes `Card`/`FormatChip` (`tcn/`) with `EmptyState` (`ui/`), exactly like the code it replaces.
- No new backend call and no new route — `RecentCourses` is fed from the `listEvents` result already fetched in `page.tsx:38-41` (`page_size: 200`).
- The stat-cards grid (`hero` + `StatCardsRank`) must remain insertable-above for NAV-9 (#502, out of scope) — do not wrap it in anything that would make inserting a sibling block above it harder.
- TDD (constitution Principle III) — every step below writes the failing test before the implementation that makes it pass.
- All user-visible copy is French; all identifiers/tests stay English-named per repo convention — this plan already respects that split (French JSX strings, English function/test names... except test *descriptions*, which follow this repo's existing convention of French `it(...)` strings — see `page.test.tsx` as shipped).

---

### Task 1: `seasonAbsenceLabel` in `lib/utils/season.ts`

**Files:**
- Modify: `frontend/lib/utils/season.ts` (add export at the end of the file)
- Test: `frontend/lib/utils/season.test.ts`

**Interfaces:**
- Produces: `seasonAbsenceLabel(years: number[]): string` — for the NAV-6 empty-state title. Consumed by Task 5.

- [ ] **Step 1: Write the failing tests**

Add to `frontend/lib/utils/season.test.ts`, after the `import` line add `seasonAbsenceLabel` to the imported names:

```ts
import {
  currentSeason,
  seasonOf,
  seasonLabel,
  parseSeasonsParam,
  serializeSeasons,
  toggleSeason,
  seasonSelectionLabel,
  seasonAbsenceLabel,
} from "./season";
```

Append at the end of the file:

```ts
describe("seasonAbsenceLabel", () => {
  it("une saison → « la saison Y — Y+1 »", () => {
    expect(seasonAbsenceLabel([2015])).toBe("la saison 2015 — 2016");
  });
  it("plusieurs saisons → « les N saisons sélectionnées »", () => {
    expect(seasonAbsenceLabel([2025, 2023])).toBe("les 2 saisons sélectionnées");
  });
  it("liste vide → retombe sur la saison en cours", () => {
    expect(seasonAbsenceLabel([])).toBe(`la ${seasonLabel(currentSeason()).toLowerCase()}`);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- run lib/utils/season.test.ts`
Expected: FAIL — `seasonAbsenceLabel` is not exported by `./season`.

- [ ] **Step 3: Implement `seasonAbsenceLabel`**

Append to `frontend/lib/utils/season.ts`:

```ts
/** Formulation « la saison X — Y » (singulier) ou « les N saisons
 *  sélectionnées » (pluriel), pour l'état vide du dashboard (#483, NAV-6).
 *  Contrairement à `seasonSelectionLabel`, la phrase porte son article et sa
 *  minuscule : elle s'insère dans "Aucun résultat enregistré pour …", pas
 *  dans un <h1>. */
export function seasonAbsenceLabel(years: number[]): string {
  if (years.length <= 1) {
    return `la ${seasonLabel(years[0] ?? currentSeason()).toLowerCase()}`;
  }
  return `les ${years.length} saisons sélectionnées`;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- run lib/utils/season.test.ts`
Expected: PASS (all tests in the file, including the 3 new ones).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/utils/season.ts frontend/lib/utils/season.test.ts
git commit -m "feat(frontend): add seasonAbsenceLabel for the dashboard empty state

Refs #460, #325, #483"
```

---

### Task 2: Export `EventOut` and add `sortEventsByDateDesc` in `lib/utils/event.ts`

**Files:**
- Modify: `frontend/lib/types.ts:105-114` (add `export` to `interface EventOut`)
- Modify: `frontend/lib/utils/event.ts` (add `sortEventsByDateDesc`)
- Test: `frontend/lib/utils/event.test.ts`

**Interfaces:**
- Consumes: none new.
- Produces: `EventOut` becomes importable from `@/lib/types` (needed by Task 3 and Task 6). `sortEventsByDateDesc(events: EventOut[]): EventOut[]` — pure, does not mutate its input, sorts by `event_date` descending (ISO `"YYYY-MM-DD"` strings, lexicographic = chronological), events with `event_date: null` sorted last. Consumed by Task 6.

- [ ] **Step 1: Export `EventOut`**

In `frontend/lib/types.ts`, change:

```ts
interface EventOut {
```

to:

```ts
export interface EventOut {
```

This is a type-only change (no runtime effect); it has no test of its own but is required for the next step's test to compile, and for Task 3.

- [ ] **Step 2: Write the failing tests**

Replace the full content of `frontend/lib/utils/event.test.ts` with:

```ts
import { describe, it, expect } from "vitest";
import type { EventOut } from "@/lib/types";
import { formatEventName, sortEventsByDateDesc } from "./event";

describe("formatEventName", () => {
  it("suffixe « (Relais) » quand isRelay est vrai", () => {
    expect(formatEventName("Triathlon de Nantes", true)).toBe("Triathlon de Nantes (Relais)");
  });
  it("renvoie le nom inchangé quand isRelay est faux", () => {
    expect(formatEventName("Triathlon de Nantes", false)).toBe("Triathlon de Nantes");
  });
});

const BASE: EventOut = {
  id: 1,
  event_name: "E",
  event_date: null,
  event_type: "Triathlon S",
  is_relay: false,
  distance_km: null,
  total: 1,
  tcn_count: 1,
};

describe("sortEventsByDateDesc", () => {
  it("trie par date décroissante", () => {
    const events = [
      { ...BASE, id: 1, event_date: "2026-01-01" },
      { ...BASE, id: 2, event_date: "2026-06-01" },
      { ...BASE, id: 3, event_date: "2026-03-01" },
    ];
    expect(sortEventsByDateDesc(events).map((e) => e.id)).toEqual([2, 3, 1]);
  });

  it("relègue les épreuves sans date en fin de liste", () => {
    const events = [
      { ...BASE, id: 1, event_date: null },
      { ...BASE, id: 2, event_date: "2026-06-01" },
    ];
    expect(sortEventsByDateDesc(events).map((e) => e.id)).toEqual([2, 1]);
  });

  it("ne modifie pas le tableau d'origine", () => {
    const events = [
      { ...BASE, id: 1, event_date: "2026-01-01" },
      { ...BASE, id: 2, event_date: "2026-06-01" },
    ];
    const original = [...events];
    sortEventsByDateDesc(events);
    expect(events).toEqual(original);
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd frontend && npm test -- run lib/utils/event.test.ts`
Expected: FAIL — `sortEventsByDateDesc` is not exported by `./event`.

- [ ] **Step 4: Implement `sortEventsByDateDesc`**

Add to `frontend/lib/utils/event.ts` (keep the existing `formatEventName`, add this below it, plus the new import at the top):

```ts
import type { EventOut } from "@/lib/types";

/** Nom d'épreuve affiché, suffixé « (Relais) » quand la course est un relais. */
export function formatEventName(name: string, isRelay: boolean): string {
  return isRelay ? `${name} (Relais)` : name;
}

/**
 * Trie une liste d'épreuves par date décroissante (#483, NAV-7) — la page
 * d'atterrissage doit répondre à « qu'est-ce qui vient de se passer », pas
 * « que fait-on le plus souvent ». `event_date` est nullable
 * (`lib/types.ts`) : une épreuve sans date est reléguée en fin de liste,
 * jamais devant une épreuve datée. Ne mute pas son argument.
 */
export function sortEventsByDateDesc(events: EventOut[]): EventOut[] {
  return [...events].sort((a, b) => {
    if (!a.event_date && !b.event_date) return 0;
    if (!a.event_date) return 1;
    if (!b.event_date) return -1;
    return b.event_date.localeCompare(a.event_date);
  });
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npm test -- run lib/utils/event.test.ts`
Expected: PASS (all 6 tests in the file).

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/utils/event.ts frontend/lib/utils/event.test.ts
git commit -m "feat(frontend): export EventOut, add sortEventsByDateDesc

Refs #460, #325, #483"
```

---

### Task 3: `RecentCourses` component

**Files:**
- Create: `frontend/components/dashboard/RecentCourses.tsx`
- Test: `frontend/components/dashboard/RecentCourses.test.tsx`

**Interfaces:**
- Consumes: `EventOut` from `@/lib/types` (Task 2); `formatDate` from `@/lib/utils/date`; `formatEventName` from `@/lib/utils/event` (Task 2); `formatToken` from `@/lib/utils/format`; `Card`, `FormatChip` from `@/components/tcn`; `EmptyState` from `@/components/ui/empty-state`.
- Produces: `RecentCourses({ events: EventOut[] })` — a server component (no `"use client"`) that renders its `events` prop **in the order given** (it does not sort — the caller, Task 6, passes an already-sorted, already-sliced list). Consumed by Task 6.

- [ ] **Step 1: Write the failing test**

Create `frontend/components/dashboard/RecentCourses.test.tsx`:

```tsx
import type { ReactNode } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { EventOut } from "@/lib/types";

vi.mock("next/link", () => ({
  default: ({
    href,
    prefetch,
    children,
    ...rest
  }: {
    href: string;
    prefetch?: boolean;
    children?: ReactNode;
    [key: string]: unknown;
  }) => (
    <a href={href} data-prefetch={String(prefetch)} {...rest}>
      {children}
    </a>
  ),
}));

import { RecentCourses } from "./RecentCourses";

const EVENT: EventOut = {
  id: 5,
  event_name: "Ironman Nantes",
  event_date: "2026-06-14",
  event_type: "Triathlon L",
  is_relay: false,
  distance_km: 113,
  total: 30,
  tcn_count: 5,
};

describe("RecentCourses", () => {
  it("rend la date, le nom et le lien de chaque épreuve, sans prefetch (#425)", () => {
    render(<RecentCourses events={[EVENT]} />);

    expect(screen.getByRole("heading", { level: 2, name: "Dernières épreuves" })).toBeInTheDocument();
    expect(screen.getByText("14/06/2026")).toBeInTheDocument();
    const lien = screen.getByRole("link", { name: /Ironman Nantes/ });
    expect(lien).toHaveAttribute("href", "/courses/5");
    expect(lien).toHaveAttribute("data-prefetch", "false");
  });

  it("suffixe (Relais) quand l'épreuve est un relais", () => {
    render(<RecentCourses events={[{ ...EVENT, is_relay: true }]} />);
    expect(screen.getByText("Ironman Nantes (Relais)")).toBeInTheDocument();
  });

  it("affiche un tiret quand l'épreuve n'a pas de date", () => {
    render(<RecentCourses events={[{ ...EVENT, event_date: null }]} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("affiche un état vide avec un CTA vers /ajouter quand la liste est vide", () => {
    render(<RecentCourses events={[]} />);
    expect(screen.getByText("Aucune épreuve récente à afficher")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ajouter une épreuve/ })).toHaveAttribute("href", "/ajouter");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- run components/dashboard/RecentCourses.test.tsx`
Expected: FAIL — cannot find module `./RecentCourses`.

- [ ] **Step 3: Implement `RecentCourses`**

Create `frontend/components/dashboard/RecentCourses.tsx`:

```tsx
import Link from "next/link";
import { Card, FormatChip } from "@/components/tcn";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDate } from "@/lib/utils/date";
import { formatEventName } from "@/lib/utils/event";
import { formatToken } from "@/lib/utils/format";
import type { EventOut } from "@/lib/types";

const GRID_COLUMNS = "88px 1fr auto auto";

/**
 * Les dernières épreuves du club, triées par date décroissante (#483,
 * NAV-7). Remplace l'ancienne carte "Épreuves préférées" (triée par volume
 * de dossards) : la seule liste de l'écran d'atterrissage doit répondre à
 * "qu'est-ce qui vient de se passer", pas à "que fait-on le plus souvent".
 *
 * Reçoit déjà la liste triée et tronquée — `sortEventsByDateDesc` vit dans
 * `lib/utils/event.ts`, appelé côté page (`dashboard/page.tsx`). Ce
 * composant ne fait que rendre, dans l'ordre reçu.
 */
export function RecentCourses({ events }: { events: EventOut[] }) {
  return (
    <Card>
      <h2
        style={{
          fontFamily: "var(--tcn-font-display)",
          fontSize: 24,
          fontWeight: 400,
          color: "var(--tcn-ink)",
          margin: 0,
          marginBottom: 18,
        }}
      >
        Dernières épreuves
      </h2>
      {events.length === 0 ? (
        <EmptyState
          bare
          className="py-6"
          title="Aucune épreuve récente à afficher"
          action={
            <Link href="/ajouter" className="text-sm font-semibold text-accent-ink hover:underline">
              Ajouter une épreuve →
            </Link>
          }
        />
      ) : (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: GRID_COLUMNS,
              gap: "0 14px",
              fontSize: 12,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: ".04em",
              color: "var(--tcn-text-faint)",
              paddingBottom: 10,
              borderBottom: "1px solid var(--tcn-border)",
            }}
          >
            <div>Date</div>
            <div>Épreuve</div>
            <div>Format</div>
            <div style={{ textAlign: "right" }}>Dossards</div>
          </div>
          {events.map((e, i) => (
            // prefetch={false} (#425) : jusqu'à 6 liens au-dessus de la ligne
            // de flottaison, next/link les prefetch tous par défaut dès
            // l'atterrissage sur /dashboard — un coût réseau pour des
            // épreuves au hasard, rarement celle que le visiteur ouvrira.
            <Link
              key={e.id}
              href={`/courses/${e.id}`}
              prefetch={false}
              className="tcn-rowlink"
              style={{
                display: "grid",
                gridTemplateColumns: GRID_COLUMNS,
                gap: "0 14px",
                alignItems: "center",
                padding: "12px 0",
                borderBottom: i < events.length - 1 ? "1px solid var(--tcn-border-faint)" : "none",
                fontSize: 15,
              }}
            >
              <span style={{ fontFamily: "var(--tcn-font-display)", color: "var(--tcn-text-muted)" }}>
                {formatDate(e.event_date) || "—"}
              </span>
              <span style={{ color: "var(--tcn-ink)", fontWeight: 600 }}>
                {formatEventName(e.event_name, e.is_relay)}
              </span>
              <FormatChip>{formatToken(e.event_type, e.distance_km)}</FormatChip>
              <b style={{ textAlign: "right", fontFamily: "var(--tcn-font-display)", color: "var(--tcn-ink)" }}>
                {e.total}
              </b>
            </Link>
          ))}
        </>
      )}
    </Card>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- run components/dashboard/RecentCourses.test.tsx`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/dashboard/RecentCourses.tsx frontend/components/dashboard/RecentCourses.test.tsx
git commit -m "feat(frontend): add RecentCourses, the dashboard component AGENTS.md already promised

Refs #460, #325, #483"
```

---

### Task 4: `page.tsx` — NAV-5, visible labels + regroup the rank toggle

**Files:**
- Modify: `frontend/app/(public_restricted)/dashboard/page.tsx:1-79`
- Test: `frontend/app/(public_restricted)/dashboard/page.test.tsx`

**Interfaces:**
- Consumes: nothing new from earlier tasks.
- Produces: a `data-testid="dashboard-toolbar"` wrapper around the `Disciplines`/`Saisons` fields (no longer containing `RankTypeToggle`); a `FieldLabel` local helper (not exported); the stat-cards grid restructured into `hero` + a labeled rank cluster. Consumed by Task 5 (which wraps this same grid in a condition) and by nothing outside this file.

- [ ] **Step 1: Write the failing tests**

In `frontend/app/(public_restricted)/dashboard/page.test.tsx`, replace the existing test:

```js
  it("garde les tags de saison hors de la barre d'outils, pour que les boutons ne bougent pas (#445)", async () => {
    // Dans la barre, les tags l'élargissaient jusqu'à la faire basculer sous
    // le titre et repartir tout à gauche : les quatre boutons de sélection
    // changeaient de place à la deuxième saison cochée. La ligne de tags est
    // donc un frère de la barre, pas un de ses enfants.
    url.qs = "seasons=2026,2025";
    await renderDashboard({ seasons: "2026,2025" });

    const barre = screen.getByLabelText("Choisir les saisons").parentElement;
    const tags = screen.getByTestId("season-tags");

    expect(barre).not.toBeNull();
    expect(barre).toContainElement(screen.getByLabelText("Inclure les autres disciplines"));
    expect(barre).not.toContainElement(tags);
    expect(tags).toHaveTextContent("Saison 2026");
    expect(tags).toHaveTextContent("Saison 2025");
  });
```

with:

```js
  it("garde les tags de saison hors de la barre d'outils, pour que les boutons ne bougent pas (#445)", async () => {
    // Dans la barre, les tags l'élargissaient jusqu'à la faire basculer sous
    // le titre et repartir tout à gauche : les quatre boutons de sélection
    // changeaient de place à la deuxième saison cochée. La ligne de tags est
    // donc un frère de la barre, pas un de ses enfants.
    url.qs = "seasons=2026,2025";
    await renderDashboard({ seasons: "2026,2025" });

    const barre = screen.getByTestId("dashboard-toolbar");
    const tags = screen.getByTestId("season-tags");

    expect(barre).toContainElement(screen.getByLabelText("Choisir les saisons"));
    expect(barre).toContainElement(screen.getByLabelText("Inclure les autres disciplines"));
    expect(barre).not.toContainElement(tags);
    expect(tags).toHaveTextContent("Saison 2026");
    expect(tags).toHaveTextContent("Saison 2025");
  });

  it("nomme visiblement les 3 contrôles de filtrage, et sort le sélecteur de rang de la barre d'outils (NAV-5)", async () => {
    await renderDashboard({});

    const barre = screen.getByTestId("dashboard-toolbar");
    expect(screen.getByText("Disciplines")).toBeInTheDocument();
    expect(screen.getByText("Saisons")).toBeInTheDocument();
    expect(screen.getByText("Type de rang")).toBeInTheDocument();

    const rankGroup = screen.getByRole("group", { name: "Type de rang" });
    expect(barre).not.toContainElement(rankGroup);
    expect(barre).toContainElement(screen.getByLabelText("Inclure les autres disciplines"));
    expect(barre).toContainElement(screen.getByLabelText("Choisir les saisons"));
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- run "app/(public_restricted)/dashboard/page.test.tsx"`
Expected: FAIL on both tests above — `getByTestId("dashboard-toolbar")` finds nothing, and the three label texts don't exist yet.

- [ ] **Step 3: Implement the restructuring**

In `frontend/app/(public_restricted)/dashboard/page.tsx`, add a `ReactNode` import at the top (line 1 becomes two import lines):

```tsx
import type { ReactNode } from "react";
import Link from "next/link";
```

Add a local `FieldLabel` helper right after the imports, before `export default async function DashboardPage`:

```tsx
/** Petit libellé visuel au-dessus d'un contrôle de filtrage (NAV-5, #483) —
 *  même style que les en-têtes de la table "Dernières épreuves" plus bas
 *  dans ce fichier, réutilisé ici pour la 3ᵉ fois plutôt qu'un nouveau
 *  token. */
function FieldLabel({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        fontSize: 12,
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: ".04em",
        color: "var(--tcn-text-faint)",
        marginBottom: 6,
      }}
    >
      {children}
    </div>
  );
}
```

Replace the toolbar `<div>` (currently holding all three controls):

```tsx
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <RankTypeToggle />
            <DisciplineToggle />
            <SeasonSelector seasons={seasons} />
          </div>
```

with:

```tsx
          <div data-testid="dashboard-toolbar" style={{ display: "flex", alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
            <div>
              <FieldLabel>Disciplines</FieldLabel>
              <DisciplineToggle />
            </div>
            <div>
              <FieldLabel>Saisons</FieldLabel>
              <SeasonSelector seasons={seasons} />
            </div>
          </div>
```

Replace the stat-cards grid:

```tsx
      <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard variant="hero" label="Dossards enregistrés" value={stats.total.toLocaleString("fr-FR")} delta={`${stats.athletes} athlètes · ${stats.events} épreuves`} />
        <StatCardsRank rankCounters={stats.rank_counters} />
      </div>
```

with:

```tsx
      <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,3fr)] lg:items-start">
        <StatCard variant="hero" label="Dossards enregistrés" value={stats.total.toLocaleString("fr-FR")} delta={`${stats.athletes} athlètes · ${stats.events} épreuves`} />
        <div>
          <div className="mb-2 flex items-center justify-between">
            <FieldLabel>Type de rang</FieldLabel>
            <RankTypeToggle />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCardsRank rankCounters={stats.rank_counters} />
          </div>
        </div>
      </div>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- run "app/(public_restricted)/dashboard/page.test.tsx"`
Expected: PASS on all tests in the file (including the two touched in Step 1 — no other test in this file asserts on the old flat toolbar/grid structure).

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(public_restricted\)/dashboard/page.tsx frontend/app/\(public_restricted\)/dashboard/page.test.tsx
git commit -m "feat(frontend): label the dashboard toolbar, regroup rank toggle with its cards (NAV-5)

Refs #460, #325, #483"
```

---

### Task 5: `page.tsx` — NAV-6, unified empty state

**Files:**
- Modify: `frontend/app/(public_restricted)/dashboard/page.tsx` (import + new consts + wrap the grid section)
- Test: `frontend/app/(public_restricted)/dashboard/page.test.tsx`

**Interfaces:**
- Consumes: `seasonAbsenceLabel` from `@/lib/utils/season` (Task 1).
- Produces: when `stats.total === 0`, the page renders a single `EmptyState` in place of the whole grid section (both the stat-cards grid from Task 4 and the two-card grid below it, still holding the pre-Task-6 "Épreuves préférées" card at this point).

- [ ] **Step 1: Write the failing tests**

In `frontend/app/(public_restricted)/dashboard/page.test.tsx`, add a new `describe` block, after the closing of `describe("DashboardPage — sélecteur de type de rang", ...)`:

```js
describe("DashboardPage — état vide unifié (NAV-6)", () => {
  const STATS_VIDE = { ...STATS, total: 0, athletes: 0, events: 0, by_type: {} };
  const EVENTS_PAGE_VIDE = { items: [], total_events: 0, total_participations: 0 };

  it("remplace toute la grille par un état vide unique quand stats.total === 0", async () => {
    getStats.mockResolvedValue(STATS_VIDE);
    listEvents.mockResolvedValue(EVENTS_PAGE_VIDE);

    await renderDashboard({ seasons: "2015" });

    expect(screen.getByText("Aucun résultat enregistré pour la saison 2015 — 2016")).toBeInTheDocument();
    expect(screen.queryByText("Dossards enregistrés")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "Type d'épreuves" })).not.toBeInTheDocument();
  });

  it("propose « Voir la saison en cours » quand la sélection n'est pas la saison en cours", async () => {
    getStats.mockResolvedValue(STATS_VIDE);
    listEvents.mockResolvedValue(EVENTS_PAGE_VIDE);

    await renderDashboard({ seasons: "2015" });

    expect(screen.getByRole("link", { name: "Voir la saison en cours" })).toHaveAttribute("href", "/dashboard");
  });

  it("n'affiche pas « Voir la saison en cours » quand la saison en cours est déjà sélectionnée", async () => {
    getStats.mockResolvedValue(STATS_VIDE);
    listEvents.mockResolvedValue(EVENTS_PAGE_VIDE);

    await renderDashboard({});

    expect(screen.queryByRole("link", { name: "Voir la saison en cours" })).not.toBeInTheDocument();
  });

  it("garde le CTA « Ajouter une épreuve » dans l'état vide", async () => {
    getStats.mockResolvedValue(STATS_VIDE);
    listEvents.mockResolvedValue(EVENTS_PAGE_VIDE);

    await renderDashboard({});

    expect(screen.getByRole("link", { name: /Ajouter une épreuve/ })).toHaveAttribute("href", "/ajouter");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- run "app/(public_restricted)/dashboard/page.test.tsx"`
Expected: FAIL on all 4 new tests — today the page always renders the full grid, so "Dossards enregistrés" and the "Type d'épreuves" heading are present even when `stats.total === 0`, and no "Aucun résultat enregistré…" text exists anywhere.

- [ ] **Step 3: Implement the unified empty state**

Add `seasonAbsenceLabel` to the `season` import in `frontend/app/(public_restricted)/dashboard/page.tsx`:

```tsx
import { currentSeason, parseSeasonsParam, seasonAbsenceLabel, seasonSelectionLabel } from "@/lib/utils/season";
```

Right after the existing `const disciplines = aggregateDisciplines(stats.by_type);` line (and before the `return`), add:

```tsx
  const isEmptySeason = stats.total === 0;
  const isCurrentSeasonSelected = selected.length === 1 && selected[0] === currentSeason();
  const voirSaisonEnCoursHref = (() => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(sp)) {
      if (value !== undefined && key !== "seasons") params.set(key, value);
    }
    const qs = params.toString();
    return qs ? `/dashboard?${qs}` : "/dashboard";
  })();
```

Then wrap the two existing grid blocks — the stat-cards grid from Task 4 and the "Type d'épreuves" / events two-column grid — in a conditional. The section between the closing `</div>` of the header (`{/* Hors de la barre d'outils... */} <SeasonTags .../> </div>`) and the closing `</PageShell>` changes from:

```tsx
      <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,3fr)] lg:items-start">
        {/* … Task 4 content … */}
      </div>

      <div className="grid gap-4 lg:grid-cols-2" style={{ gridTemplateColumns: undefined }}>
        {/* … "Type d'épreuves" Card and "Épreuves préférées" Card … */}
      </div>
```

to:

```tsx
      {isEmptySeason ? (
        <EmptyState
          title={`Aucun résultat enregistré pour ${seasonAbsenceLabel(selected)}`}
          description="Change de saison ou ajoute les premiers résultats du club."
          action={
            <div className="flex flex-wrap items-center justify-center gap-4">
              {!isCurrentSeasonSelected && (
                <Link href={voirSaisonEnCoursHref} className="text-sm font-semibold text-accent-ink hover:underline">
                  Voir la saison en cours
                </Link>
              )}
              <Link href="/ajouter" className="text-sm font-semibold text-accent-ink hover:underline">
                Ajouter une épreuve →
              </Link>
            </div>
          }
        />
      ) : (
        <>
          <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,3fr)] lg:items-start">
            {/* … Task 4 content, unchanged … */}
          </div>

          <div className="grid gap-4 lg:grid-cols-2" style={{ gridTemplateColumns: undefined }}>
            {/* … "Type d'épreuves" Card and "Épreuves préférées" Card, unchanged for now — Task 6 swaps the second Card … */}
          </div>
        </>
      )}
```

(Only the wrapping changes here — do not touch the inner content of either grid in this task; Task 6 is the one that swaps the second card for `RecentCourses`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- run "app/(public_restricted)/dashboard/page.test.tsx"`
Expected: PASS on all tests in the file.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(public_restricted\)/dashboard/page.tsx frontend/app/\(public_restricted\)/dashboard/page.test.tsx
git commit -m "feat(frontend): unify the dashboard's empty-season state, name the cause (NAV-6)

Refs #460, #325, #483"
```

---

### Task 6: `page.tsx` — NAV-7, wire `RecentCourses`

**Files:**
- Modify: `frontend/app/(public_restricted)/dashboard/page.tsx`
- Test: `frontend/app/(public_restricted)/dashboard/page.test.tsx`

**Interfaces:**
- Consumes: `sortEventsByDateDesc` from `@/lib/utils/event` (Task 2); `RecentCourses` from `@/components/dashboard/RecentCourses` (Task 3).
- Produces: the page no longer defines `topEvents`; it defines `recentEvents` and renders `<RecentCourses events={recentEvents} />` in place of the old inline "Épreuves préférées" card.

- [ ] **Step 1: Write the failing tests**

In `frontend/app/(public_restricted)/dashboard/page.test.tsx`, update the two tests that reference the old card. Replace:

```js
  it("propose d'ajouter une épreuve quand la liste des épreuves préférées est vide", async () => {
    // `EVENTS_PAGE` par défaut a déjà `items: []` : l'état vide est le cas
    // par défaut de la fixture, pas un cas à construire.
    await renderDashboard({});

    expect(screen.getByText("Aucune épreuve à afficher")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ajouter une épreuve/ })).toHaveAttribute("href", "/ajouter");
  });
```

with:

```js
  it("propose d'ajouter une épreuve quand la liste des dernières épreuves est vide", async () => {
    // `EVENTS_PAGE` par défaut a déjà `items: []` : l'état vide est le cas
    // par défaut de la fixture, pas un cas à construire.
    await renderDashboard({});

    expect(screen.getByText("Aucune épreuve récente à afficher")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ajouter une épreuve/ })).toHaveAttribute("href", "/ajouter");
  });
```

Replace:

```js
  it("désactive le prefetch des liens « Épreuves préférées » (#425) — au-dessus de la ligne de flottaison, jusqu'à 6 à la fois, prefetchées au hasard sans intérêt", async () => {
```

with:

```js
  it("désactive le prefetch des liens « Dernières épreuves » (#425) — au-dessus de la ligne de flottaison, jusqu'à 6 à la fois, prefetchées au hasard sans intérêt", async () => {
```

(the body of that test is unchanged — it already asserts on the `Ironman Nantes` link, `href="/courses/5"`, `data-prefetch="false"`, all of which `RecentCourses` still produces).

Replace:

```js
  it("rend les titres de carte comme des <h2> (A11Y-2)", async () => {
    await renderDashboard({});

    expect(screen.getByRole("heading", { level: 2, name: "Type d'épreuves" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Épreuves préférées" })).toBeInTheDocument();
  });
```

with:

```js
  it("rend les titres de carte comme des <h2> (A11Y-2)", async () => {
    await renderDashboard({});

    expect(screen.getByRole("heading", { level: 2, name: "Type d'épreuves" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Dernières épreuves" })).toBeInTheDocument();
  });
```

Add one more test, in the top-level `describe("DashboardPage", ...)` block, right after the "désactive le prefetch" test:

```js
  it("trie les dernières épreuves par date décroissante plutôt que par volume (NAV-7)", async () => {
    listEvents.mockResolvedValue({
      items: [
        { id: 1, event_name: "Petit format", event_date: "2026-01-10", event_type: "Triathlon S", is_relay: false, distance_km: null, total: 50, tcn_count: 5 },
        { id: 2, event_name: "Ironman Nantes", event_date: "2026-06-14", event_type: "Triathlon L", is_relay: false, distance_km: 113, total: 5, tcn_count: 5 },
      ],
      total_events: 2,
      total_participations: 55,
    });

    await renderDashboard({});

    const liens = screen.getAllByRole("link", { name: /Petit format|Ironman Nantes/ });
    expect(liens[0]).toHaveTextContent("Ironman Nantes");
    expect(liens[1]).toHaveTextContent("Petit format");
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- run "app/(public_restricted)/dashboard/page.test.tsx"`
Expected: FAIL on the renamed/new tests — the page still renders "Épreuves préférées" sorted by `total` descending, not "Dernières épreuves" sorted by date.

- [ ] **Step 3: Wire `RecentCourses`**

In `frontend/app/(public_restricted)/dashboard/page.tsx`:

Add imports:

```tsx
import { RecentCourses } from "@/components/dashboard/RecentCourses";
import { sortEventsByDateDesc } from "@/lib/utils/event";
```

Replace:

```tsx
  const topEvents = [...eventsPage.items].sort((a, b) => b.total - a.total).slice(0, 6);
```

with:

```tsx
  const recentEvents = sortEventsByDateDesc(eventsPage.items).slice(0, 6);
```

Replace the second `<Card>` in the two-column grid (the current "Épreuves préférées" card, spanning from its opening `<Card>` through the `topEvents.length === 0 && (...)` block and its closing `</Card>`) with:

```tsx
        <RecentCourses events={recentEvents} />
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- run "app/(public_restricted)/dashboard/page.test.tsx"`
Expected: PASS on all tests in the file.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(public_restricted\)/dashboard/page.tsx frontend/app/\(public_restricted\)/dashboard/page.test.tsx
git commit -m "feat(frontend): sort the dashboard's landing list by date, not volume (NAV-7)

Refs #460, #325, #483"
```

---

### Task 7: Final verification

**Files:** none (verification only).

**Interfaces:** none.

- [ ] **Step 1: Full frontend test suite**

Run: `cd frontend && npm test`
Expected: all suites PASS, including `lib/utils/season.test.ts`, `lib/utils/event.test.ts`, `components/dashboard/RecentCourses.test.tsx`, `components/dashboard/StatCardsRank.test.tsx`, and `app/(public_restricted)/dashboard/page.test.tsx`.

- [ ] **Step 2: Lint**

Run: `cd frontend && npm run lint`
Expected: no errors.

- [ ] **Step 3: Production build**

Run: `cd frontend && npm run build`
Expected: build succeeds (strict TS + RSC) — this is the step that would catch a missed `EventOut` export or a JSX structural mistake that Vitest's mocked `next/navigation`/`next/link` wouldn't.

- [ ] **Step 4: Manual sanity check (optional but recommended given 3 visual changes on one screen)**

Run: `cd backend && uv run python scripts/dev_server.py` (in one terminal) and `cd frontend && npm run dev` (in another), then open `/dashboard` and:
- confirm "Disciplines", "Saisons", "Type de rang" are visible as on-screen text, not just accessible names;
- confirm the rank toggle sits above the 3 Victoires/Podiums/Top10 cards, not in the top toolbar;
- confirm `/dashboard?seasons=2015` (or any past season with no club data) renders the single empty-state message, not a wall of zeros;
- confirm the "Dernières épreuves" card shows real dates in `DD/MM/YYYY`, most recent first.

- [ ] **Step 5: Commit (only if Step 4 surfaced a fix)**

If the manual check requires no change, there is nothing to commit here — Task 6's commit is the last one. If it does, make the fix, re-run the affected test file, and commit normally following the same message convention as the tasks above.

---

## Self-review notes (for the plan author, not a task)

- **Spec coverage** — NAV-5 (Task 4), NAV-6 (Task 5), NAV-7 (Tasks 2, 3, 6) are each covered; the `data-testid="dashboard-toolbar"` robustness fix and the `EventOut` export called out in the design's "Décisions de cadrage" table are both folded into the tasks that need them (Task 4 and Task 2, respectively), per the task right-sizing rule rather than kept as standalone no-op tasks.
- **Type consistency** — `EventOut` (Task 2) is the type threaded through `sortEventsByDateDesc` (Task 2), `RecentCourses` (Task 3), and `page.tsx`'s `recentEvents` (Task 6) without renaming across tasks.
- **Ordering** — the `EventOut` export had to move from the design's "Task 3-shaped" home into Task 2, because Task 2's own test (`sortEventsByDateDesc`) needs to import the type to type its fixtures; Task 3 then just consumes the already-exported type. This is called out explicitly so a reader comparing this plan to the design doesn't flag it as a drift.
