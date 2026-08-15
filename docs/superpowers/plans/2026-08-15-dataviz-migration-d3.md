# Migration des graphiques SVG vers d3 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the four hand-written SVG/CSS charts under `frontend/` (histogram, gender donut, category bars, ranking-evolution line) to `d3-scale`/`d3-shape`, per issue #370, while keeping visual output and RSC-compatibility unchanged.

**Architecture:** Extract the three components currently inline in `app/courses/[id]/page.tsx` (Histogram, gender donut, category bars) into standalone files under `components/charts/`, matching the existing pattern of `BarList.tsx`/`MonthlyTrend.tsx`. For each of the four charts, swap only the linear-interpolation math for `d3.scaleLinear()` (coordinate projection) or `d3.arc()`/`d3.pie()` (donut geometry) — never `d3-scale`'s `.ticks()`/`.nice()`, which choose different tick *values* than this codebase's existing tick logic and would silently change the rendered numbers.

**Tech Stack:** Next.js 16 (App Router), TypeScript strict, Vitest + React Testing Library, `d3-scale` + `d3-shape` (new deps).

**Spec:** `docs/superpowers/specs/2026-08-15-dataviz-migration-d3-design.md`

## Global Constraints

- `d3-scale` / `d3-shape` — modules only, no `"use client"` anywhere they're used (all four target files are RSC-compatible today, except `RankingEvolutionChart.tsx` which is already `"use client"` and stays that way).
- **`d3.scaleLinear()` projects a domain value to a pixel — it never chooses which values to display as ticks.** Tick *values* stay hand-computed (evenly-spaced-by-index for the histogram Y axis and the ranking chart, `histogram-ticks.ts` for the histogram X axis) exactly as today. Do not call `.ticks()` or `.nice()` on any scale in this plan — they produce "nice round number" ticks, a different set of values than what's rendered today, which would violate the "rendu iso" acceptance criterion.
- Every extracted component (`Histogram`, `GenderDonut`, `CategoryBars`) owns only its chart — no `<Card>` wrapper, no title. The parent (`page.tsx`) keeps composing `<Card>` + title exactly as today, matching how `MonthlyTrend`/`BarList` are already composed by `ClubDashboard.tsx`.
- French copy, French code comments only where they explain a non-obvious *why* (project convention, `AGENTS.md`).
- No dead code left behind: once a value/function/import is fully replaced, delete it in the same task, not a follow-up.
- All commands below run from `frontend/` inside this worktree (`/home/mherrmann/work/tcn/data-triathlon/.claude/worktrees/dataviz-migration-d3/frontend`).

---

### Task 0: Add d3 dependencies

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json` (via `npm install`)

**Interfaces:**
- Produces: `d3-scale` (`scaleLinear`) and `d3-shape` (`arc`, `pie`, `line`, `curveMonotoneX`) importable from any component in later tasks.

- [ ] **Step 1: Install the runtime packages**

```bash
cd frontend
npm install d3-scale d3-shape
```

- [ ] **Step 2: Install their type declarations**

```bash
npm install -D @types/d3-scale @types/d3-shape
```

- [ ] **Step 3: Verify the existing test suite is still green before any code change**

Run: `npm test`
Expected: all tests PASS (this is the baseline — if anything fails here, stop and investigate before proceeding, it's not related to this plan).

- [ ] **Step 4: Verify the production build still succeeds with the new dependencies present but unused**

Run: `npm run build`
Expected: build succeeds (confirms the new packages don't break Next's RSC bundling before any component imports them).

- [ ] **Step 5: Commit**

```bash
git add package.json package-lock.json
git commit -m "chore(frontend): ajoute d3-scale et d3-shape (#370)"
```

---

### Task 1: Extract and migrate the histogram (PR/lot 1)

**Files:**
- Create: `frontend/components/charts/Histogram.tsx`
- Create: `frontend/components/charts/Histogram.test.tsx`
- Modify: `frontend/app/courses/[id]/page.tsx` (remove the inline `Histogram` function at lines ~198-256 and the now-unused `histogram-ticks` import at line 12; add an import and keep the call site)

**Interfaces:**
- Consumes: `buildTicks`, `formatTickLabel` from `@/lib/utils/histogram-ticks` (unchanged).
- Produces: `Histogram({ bars: number[]; max: number; startSec: number; bucketSec: number })` — a named export, same prop shape the call site in `page.tsx` already uses.

- [ ] **Step 1: Write the characterization test**

Create `frontend/components/charts/Histogram.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Histogram } from "./Histogram";

describe("Histogram", () => {
  it("trace une barre par tranche de temps", () => {
    const { container } = render(
      <Histogram bars={[2, 5, 3]} max={5} startSec={0} bucketSec={300} />,
    );
    expect(container.querySelectorAll("rect").length).toBe(3);
  });

  it("la barre avec le plus de finishers est la plus haute", () => {
    const { container } = render(
      <Histogram bars={[2, 5, 3]} max={5} startSec={0} bucketSec={300} />,
    );
    const heights = [...container.querySelectorAll("rect")].map((r) =>
      Number(r.getAttribute("height")),
    );
    expect(heights[1]).toBeGreaterThan(heights[0]);
    expect(heights[1]).toBeGreaterThan(heights[2]);
  });

  it("n'affiche aucune barre quand max est nul (aucun finisher)", () => {
    const { container } = render(
      <Histogram bars={[0, 0]} max={0} startSec={0} bucketSec={300} />,
    );
    const heights = [...container.querySelectorAll("rect")].map((r) =>
      Number(r.getAttribute("height")),
    );
    expect(heights).toEqual([0, 0]);
  });

  it("gradue l'axe Y de 0 au maximum", () => {
    const { container } = render(
      <Histogram bars={[10]} max={10} startSec={0} bucketSec={60} />,
    );
    const labels = [...container.querySelectorAll("text")].map((t) => t.textContent);
    expect(labels).toContain("0");
    expect(labels).toContain("10");
  });

  it("aligne les graduations X sur des multiples ronds du pas (#129)", () => {
    // 6 tranches de 15 min = 90 min de fenêtre → pas de 15 min (histogram-ticks.ts).
    const { container } = render(
      <Histogram bars={[1, 1, 1, 1, 1, 1]} max={1} startSec={0} bucketSec={900} />,
    );
    const labels = [...container.querySelectorAll("text")].map((t) => t.textContent);
    expect(labels).toContain("0:15");
    expect(labels).toContain("1:30");
  });

  it("reste un bandeau large plutôt qu'un pavé", () => {
    const { container } = render(
      <Histogram bars={[1, 2, 3]} max={3} startSec={0} bucketSec={300} />,
    );
    const [, , w, h] = container
      .querySelector("svg")!
      .getAttribute("viewBox")!
      .split(" ")
      .map(Number);
    expect(h / w).toBeLessThanOrEqual(0.3);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails (module doesn't exist yet)**

Run: `npm test -- Histogram`
Expected: FAIL with "Failed to resolve import './Histogram'" or similar.

- [ ] **Step 3: Extract the current implementation verbatim**

Create `frontend/components/charts/Histogram.tsx` with the **unmodified** logic currently in `page.tsx` (only the export and import paths change):

```tsx
import { buildTicks, formatTickLabel } from "@/lib/utils/histogram-ticks";

export function Histogram({
  bars,
  max,
  startSec,
  bucketSec,
}: {
  bars: number[];
  max: number;
  startSec: number;
  bucketSec: number;
}) {
  const W = 900;
  const H = 240;
  const top = 20;
  const bottom = 190;
  const left = 46;
  const usableW = W - left - 10;
  const barGap = usableW / bars.length;
  const barW = Math.max(4, barGap * 0.72);
  const yTicks = 5;

  const endSec = startSec + bars.length * bucketSec;
  const xTicks = bars.length > 0 ? buildTicks(startSec, endSec) : [];
  const secToX = (sec: number) => left + ((sec - startSec) / bucketSec) * barGap;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      {Array.from({ length: yTicks + 1 }, (_, i) => {
        const v = Math.round((max / yTicks) * i);
        const y = bottom - (i / yTicks) * (bottom - top);
        return (
          <g key={i}>
            <line x1={left - 6} y1={y} x2={W - 10} y2={y} stroke="var(--tcn-border-faint)" />
            <text x={left - 14} y={y + 4} textAnchor="end" fontSize="11" fill="var(--tcn-text-faint)" fontFamily="Barlow">{v}</text>
          </g>
        );
      })}
      {bars.map((c, i) => {
        const h = max ? (c / max) * (bottom - top) : 0;
        return <rect key={i} x={left + i * barGap} y={bottom - h} width={barW} height={h} rx="2" fill="var(--tcn-orange)" />;
      })}
      {xTicks.map((tickSec) => {
        const x = secToX(tickSec);
        return (
          <g key={tickSec}>
            <line x1={x} y1={top} x2={x} y2={bottom} stroke="var(--tcn-border-faint)" />
            <text x={x} y={bottom + 16} textAnchor="middle" fontSize="11" fill="var(--tcn-text-faint)" fontFamily="Barlow">{formatTickLabel(tickSec)}</text>
          </g>
        );
      })}
    </svg>
  );
}
```

- [ ] **Step 4: Run the test to verify the extraction alone didn't change behavior**

Run: `npm test -- Histogram`
Expected: all 6 tests PASS.

- [ ] **Step 5: Refactor the Y axis to d3-scale**

Replace the two manual Y computations in `Histogram.tsx` (bar height and Y-tick position) with a `d3.scaleLinear()`. Full replacement for the body of the function:

```tsx
import { scaleLinear } from "d3-scale";
import { buildTicks, formatTickLabel } from "@/lib/utils/histogram-ticks";

export function Histogram({
  bars,
  max,
  startSec,
  bucketSec,
}: {
  bars: number[];
  max: number;
  startSec: number;
  bucketSec: number;
}) {
  const W = 900;
  const H = 240;
  const top = 20;
  const bottom = 190;
  const left = 46;
  const usableW = W - left - 10;
  const barGap = usableW / bars.length;
  const barW = Math.max(4, barGap * 0.72);
  const yTicks = 5;

  // Domaine [0, max] → pixel [bottom, top] (plus de finishers = plus haut).
  // Repli constant si max=0 : scaleLinear diviserait par un domaine nul.
  const yScale = max > 0 ? scaleLinear().domain([0, max]).range([bottom, top]) : () => bottom;

  const endSec = startSec + bars.length * bucketSec;
  const xTicks = bars.length > 0 ? buildTicks(startSec, endSec) : [];
  const secToX = (sec: number) => left + ((sec - startSec) / bucketSec) * barGap;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      {Array.from({ length: yTicks + 1 }, (_, i) => {
        const v = Math.round((max / yTicks) * i);
        const y = yScale(v);
        return (
          <g key={i}>
            <line x1={left - 6} y1={y} x2={W - 10} y2={y} stroke="var(--tcn-border-faint)" />
            <text x={left - 14} y={y + 4} textAnchor="end" fontSize="11" fill="var(--tcn-text-faint)" fontFamily="Barlow">{v}</text>
          </g>
        );
      })}
      {bars.map((c, i) => {
        const y = yScale(c);
        return <rect key={i} x={left + i * barGap} y={y} width={barW} height={bottom - y} rx="2" fill="var(--tcn-orange)" />;
      })}
      {xTicks.map((tickSec) => {
        const x = secToX(tickSec);
        return (
          <g key={tickSec}>
            <line x1={x} y1={top} x2={x} y2={bottom} stroke="var(--tcn-border-faint)" />
            <text x={x} y={bottom + 16} textAnchor="middle" fontSize="11" fill="var(--tcn-text-faint)" fontFamily="Barlow">{formatTickLabel(tickSec)}</text>
          </g>
        );
      })}
    </svg>
  );
}
```

Note: the X axis (`secToX`, `buildTicks`) is untouched — it's `histogram-ticks.ts`'s business logic, not a projection d3-scale should own (per Global Constraints).

- [ ] **Step 6: Run the test to verify the migration preserved behavior**

Run: `npm test -- Histogram`
Expected: all 6 tests still PASS.

- [ ] **Step 7: Wire the new component into `page.tsx` and delete the old one**

In `frontend/app/courses/[id]/page.tsx`:
1. Replace the import at line 12 (`import { buildTicks, formatTickLabel } from "@/lib/utils/histogram-ticks";`) with:
   ```tsx
   import { Histogram } from "@/components/charts/Histogram";
   ```
2. Delete the entire `function Histogram({ ... }) { ... }` block (the old inline implementation, currently lines ~198-256 — everything from `function Histogram(` to its closing `}`).
3. Leave the call site (`<Histogram bars={...} max={...} startSec={...} bucketSec={...} />`) untouched — same props, same import name.

- [ ] **Step 8: Run the full frontend test suite**

Run: `npm test`
Expected: all tests PASS, including `app/courses/[id]/page.test.tsx` and the new `Histogram.test.tsx`.

- [ ] **Step 9: Verify the production build**

Run: `npm run build`
Expected: succeeds, no new `"use client"` boundary introduced (the histogram stays server-rendered).

- [ ] **Step 10: Commit**

```bash
git add frontend/components/charts/Histogram.tsx frontend/components/charts/Histogram.test.tsx "frontend/app/courses/[id]/page.tsx"
git commit -m "refactor(frontend): migre l'histogramme des temps vers d3-scale (#370)"
```

---

### Task 2: Extract and migrate the gender donut

**Files:**
- Create: `frontend/components/charts/GenderDonut.tsx`
- Create: `frontend/components/charts/GenderDonut.test.tsx`
- Modify: `frontend/app/courses/[id]/page.tsx` (replace the inline donut markup at lines ~110-122 and remove the `Legend` helper at lines ~188-196, now unused)

**Interfaces:**
- Consumes: `pctFr` from `@/lib/utils/format` (already used elsewhere in the codebase, e.g. `app/dashboard/page.tsx`).
- Produces: `GenderDonut({ malePct: number; femalePct: number; hasGender: boolean })` — a named export.

- [ ] **Step 1: Write the characterization test**

Create `frontend/components/charts/GenderDonut.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { GenderDonut } from "./GenderDonut";

describe("GenderDonut", () => {
  it("trace une tranche par genre quand le genre est renseigné", () => {
    const { container } = render(
      <GenderDonut malePct={63.7} femalePct={36.3} hasGender />,
    );
    expect(container.querySelectorAll("path").length).toBe(2);
  });

  it("donne une alternative textuelle à chaque tranche", () => {
    const { container } = render(
      <GenderDonut malePct={63.7} femalePct={36.3} hasGender />,
    );
    const labels = [...container.querySelectorAll("path")].map((p) =>
      p.getAttribute("aria-label"),
    );
    expect(labels.some((l) => l?.includes("Homme") && l?.includes("63,7"))).toBe(true);
    expect(labels.some((l) => l?.includes("Femme") && l?.includes("36,3"))).toBe(true);
  });

  it("affiche un cercle neutre, sans tranche, quand le genre est absent", () => {
    const { container } = render(
      <GenderDonut malePct={0} femalePct={0} hasGender={false} />,
    );
    expect(container.querySelectorAll("path").length).toBe(0);
    expect(container.querySelector("circle")).toBeTruthy();
  });

  it("affiche le pourcentage d'hommes arrondi au centre", () => {
    const { getByText } = render(
      <GenderDonut malePct={63.7} femalePct={36.3} hasGender />,
    );
    expect(getByText("64%")).toBeInTheDocument();
  });

  it("légende les deux tranches avec leur pourcentage exact", () => {
    const { getByText } = render(
      <GenderDonut malePct={63.7} femalePct={36.3} hasGender />,
    );
    expect(getByText("Homme")).toBeInTheDocument();
    expect(getByText("63,7%")).toBeInTheDocument();
    expect(getByText("Femme")).toBeInTheDocument();
    expect(getByText("36,3%")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- GenderDonut`
Expected: FAIL, module `./GenderDonut` not found.

- [ ] **Step 3: Implement `GenderDonut.tsx`**

Create `frontend/components/charts/GenderDonut.tsx`:

```tsx
import { arc, pie, type PieArcDatum } from "d3-shape";
import { pctFr } from "@/lib/utils/format";

const SIZE = 130;
const OUTER_R = SIZE / 2;
// Reprend l'épaisseur de l'ancien anneau CSS (`inset: 26` sur un disque de 130).
const RING_THICKNESS = 26;
const INNER_R = OUTER_R - RING_THICKNESS;

interface GenderSlice {
  label: "Homme" | "Femme";
  value: number;
}

const SLICE_COLOR: Record<GenderSlice["label"], string> = {
  Homme: "var(--tcn-orange)",
  Femme: "var(--tcn-ink)",
};

const pieLayout = pie<GenderSlice>()
  .sort(null)
  .value((d) => d.value);

const arcGenerator = arc<PieArcDatum<GenderSlice>>()
  .innerRadius(INNER_R)
  .outerRadius(OUTER_R);

/**
 * Donut de répartition hommes/femmes (`/courses/[id]`). Remplace le
 * dégradé CSS (`conic-gradient`) par un `<path>` par tranche : chacune porte
 * sa propre alternative textuelle, que le dégradé ne pouvait pas offrir.
 */
export function GenderDonut({
  malePct,
  femalePct,
  hasGender,
}: {
  malePct: number;
  femalePct: number;
  hasGender: boolean;
}) {
  const slices = hasGender
    ? pieLayout([
        { label: "Homme", value: malePct },
        { label: "Femme", value: femalePct },
      ])
    : [];

  return (
    <>
      <div style={{ position: "relative", width: SIZE, height: SIZE }}>
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} width={SIZE} height={SIZE}>
          <g transform={`translate(${OUTER_R}, ${OUTER_R})`}>
            {hasGender ? (
              slices.map((slice) => (
                <path
                  key={slice.data.label}
                  d={arcGenerator(slice) ?? undefined}
                  fill={SLICE_COLOR[slice.data.label]}
                  role="img"
                  aria-label={`${slice.data.label} : ${pctFr(slice.data.value)}%`}
                />
              ))
            ) : (
              <circle r={OUTER_R} fill="var(--tcn-grey-300)" />
            )}
          </g>
        </svg>
        <div
          style={{
            position: "absolute",
            inset: RING_THICKNESS,
            borderRadius: 999,
            background: "var(--tcn-surface)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexDirection: "column",
          }}
        >
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)", lineHeight: 1 }}>
            {Math.round(malePct)}%
          </div>
          <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", color: "var(--tcn-text-faint)", letterSpacing: ".05em" }}>
            Hommes
          </div>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%" }}>
        <Legend color="var(--tcn-orange)" label="Homme" value={`${pctFr(malePct)}%`} />
        <Legend color="var(--tcn-ink)" label="Femme" value={`${pctFr(femalePct)}%`} />
      </div>
    </>
  );
}

function Legend({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
      <span style={{ width: 10, height: 10, borderRadius: 3, background: color }} />
      <span style={{ color: "var(--tcn-text-body)" }}>{label}</span>
      <b style={{ marginLeft: "auto", fontFamily: "var(--tcn-font-display)", color: "var(--tcn-ink)" }}>{value}</b>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test -- GenderDonut`
Expected: all 5 tests PASS.

- [ ] **Step 5: Wire into `page.tsx` and remove the now-dead `Legend` helper**

In `frontend/app/courses/[id]/page.tsx`:
1. Add import: `import { GenderDonut } from "@/components/charts/GenderDonut";`
2. Replace lines ~112-121 (the donut `<div>` and the two `<Legend .../>` calls) with:
   ```tsx
   <GenderDonut malePct={malePct} femalePct={femalePct} hasGender={hasGender} />
   ```
   The surrounding `<Card padding={24} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 18 }}>` and its title div (`Répartition genre`) stay as-is.
3. Delete the `function Legend({ color, label, value }) { ... }` block (currently lines ~188-196) — it now lives only in `GenderDonut.tsx`. Confirm with a search that `Legend` is not referenced anywhere else in `page.tsx` before deleting.

- [ ] **Step 6: Run the full frontend test suite**

Run: `npm test`
Expected: all tests PASS.

- [ ] **Step 7: Verify the production build**

Run: `npm run build`
Expected: succeeds, no new `"use client"` boundary.

- [ ] **Step 8: Commit**

```bash
git add frontend/components/charts/GenderDonut.tsx frontend/components/charts/GenderDonut.test.tsx "frontend/app/courses/[id]/page.tsx"
git commit -m "refactor(frontend): migre le donut genre vers d3-shape (#370)"
```

---

### Task 3: Extract and migrate the category bars

**Files:**
- Create: `frontend/components/charts/CategoryBars.tsx`
- Create: `frontend/components/charts/CategoryBars.test.tsx`
- Modify: `frontend/app/courses/[id]/page.tsx` (replace the inline category markup at lines ~124-141, remove the now-fully-unused `CAT_COLORS` constant and `pctFr` local function, and the `catTotal`/`categories` derived variables at lines ~78-85)

**Interfaces:**
- Consumes: `pctFr` from `@/lib/utils/format`.
- Produces: `CategoryBars({ categories: { name: string; count: number }[]; total: number })` — a named export. `total` is `summary.categories_total` (all categories), not the sum of the categories passed in — this is the exact bug #322/the existing page test guards against, so the ratio math must stay `count / total`, never `count / categories.reduce(...)`.

- [ ] **Step 1: Write the characterization test**

Create `frontend/components/charts/CategoryBars.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CategoryBars } from "./CategoryBars";

describe("CategoryBars", () => {
  it("affiche une barre par catégorie", () => {
    render(
      <CategoryBars
        categories={[
          { name: "S1", count: 284 },
          { name: "S2", count: 216 },
        ]}
        total={1000}
      />,
    );
    expect(screen.getAllByText(/^S[12]$/).length).toBe(2);
  });

  it("rapporte chaque barre au total fourni, pas à la somme des catégories affichées", () => {
    // 284/1000 = 28,4 % ; les rapporter aux 500 affichés donnerait 56,8 %.
    render(<CategoryBars categories={[{ name: "S1", count: 284 }]} total={1000} />);
    expect(screen.getByText("28,4%")).toBeInTheDocument();
  });

  it("affiche un état vide quand aucune catégorie n'est renseignée", () => {
    render(<CategoryBars categories={[]} total={0} />);
    expect(screen.getByText("Catégories non renseignées.")).toBeInTheDocument();
  });

  it("n'échoue pas quand le total est nul", () => {
    const { container } = render(
      <CategoryBars categories={[{ name: "S1", count: 0 }]} total={0} />,
    );
    expect(container.textContent).not.toContain("NaN");
    expect(screen.getByText("0,0%")).toBeInTheDocument();
  });

  it("donne une couleur distincte à chaque catégorie", () => {
    const { container } = render(
      <CategoryBars
        categories={[
          { name: "S1", count: 1 },
          { name: "S2", count: 1 },
        ]}
        total={2}
      />,
    );
    const fills = [...container.querySelectorAll("[style*='border-radius: 999px'] > div")].map(
      (bar) => (bar as HTMLElement).style.background,
    );
    expect(fills[0]).not.toBe(fills[1]);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- CategoryBars`
Expected: FAIL, module `./CategoryBars` not found.

- [ ] **Step 3: Implement `CategoryBars.tsx`**

Create `frontend/components/charts/CategoryBars.tsx`:

```tsx
import { scaleLinear } from "d3-scale";
import { pctFr } from "@/lib/utils/format";

const CAT_COLORS = [
  "var(--tcn-orange)", "var(--tcn-orange-300)", "var(--tcn-ink)", "var(--tcn-ink-2)",
  "var(--tcn-ink-3)", "var(--tcn-grey-400)", "var(--tcn-orange-200)", "var(--tcn-grey-300)",
];

/**
 * Barres de répartition par catégorie (`/courses/[id]`). `total` est la somme
 * de **toutes** les catégories (`categories_total` de l'API), pas la somme
 * des catégories passées ici — sinon chaque barre se gonfle (cf. page test).
 */
export function CategoryBars({
  categories,
  total,
}: {
  categories: { name: string; count: number }[];
  total: number;
}) {
  if (categories.length === 0) {
    return (
      <div style={{ color: "var(--tcn-text-faint)", fontSize: 14 }}>Catégories non renseignées.</div>
    );
  }

  const scale = total > 0 ? scaleLinear().domain([0, total]).range([0, 100]) : () => 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {categories.map((c, i) => {
        const pct = scale(c.count);
        return (
          <div key={c.name} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ flex: "none", width: 36, fontWeight: 800, fontSize: 13, color: "var(--tcn-ink)" }}>{c.name}</span>
            <div style={{ flex: 1, height: 13, background: "var(--tcn-fill)", borderRadius: 999, overflow: "hidden" }}>
              <div style={{ width: pct + "%", height: "100%", background: CAT_COLORS[i % CAT_COLORS.length], borderRadius: 999 }} />
            </div>
            <span style={{ flex: "none", width: 48, textAlign: "right", fontSize: 13, fontWeight: 700, color: "var(--tcn-text-body)" }}>{pctFr(pct)}%</span>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test -- CategoryBars`
Expected: all 5 tests PASS. (If the color test in Step 1 is brittle against the exact style-string selector, adjust the selector to match the rendered DOM rather than changing the component — the component's job is the migration, not a new test-hook.)

- [ ] **Step 5: Wire into `page.tsx` and remove dead code**

In `frontend/app/courses/[id]/page.tsx`:
1. Add import: `import { CategoryBars } from "@/components/charts/CategoryBars";`
2. Delete the `CAT_COLORS` constant (currently lines ~15-18).
3. Delete the local `pctFr` function (currently lines ~20-22) — after this task it has no remaining callers in this file (gender's calls were removed in Task 2, category's calls are removed here).
4. Remove the `catTotal`/`categories` derived variables (currently lines ~78-85, the `// ── Répartition par catégorie ──` block).
5. Replace lines ~126-140 (the conditional empty-state / bars markup) with:
   ```tsx
   <CategoryBars categories={summary.categories} total={summary.categories_total} />
   ```
   The surrounding `<Card padding={24}>` and its title div (`Répartition par catégorie`) stay as-is.

- [ ] **Step 6: Run the full frontend test suite**

Run: `npm test`
Expected: all tests PASS, including the existing `app/courses/[id]/page.test.tsx` test "rapporte les pourcentages de catégorie à TOUTES les catégories, pas aux 8 rendues" — unchanged, still exercising the same behavior end-to-end.

- [ ] **Step 7: Verify the production build**

Run: `npm run build`
Expected: succeeds.

- [ ] **Step 8: Commit**

```bash
git add frontend/components/charts/CategoryBars.tsx frontend/components/charts/CategoryBars.test.tsx "frontend/app/courses/[id]/page.tsx"
git commit -m "refactor(frontend): migre les barres catégorie vers d3-scale (#370)"
```

---

### Task 4: Migrate the ranking-evolution chart (PR/lot 3)

**Files:**
- Modify: `frontend/components/tcn/participation-detail/RankingEvolutionChart.tsx` (internal only — no new file, no prop change)
- Test: `frontend/components/tcn/participation-detail/RankingEvolutionChart.test.tsx` (already exists, unmodified — it's the regression guard for this task)

**Interfaces:**
- No change to the component's exported signature (`RankingEvolutionChart({ steps, eventType })`) or to any `data-*` attribute the existing test asserts on.

- [ ] **Step 1: Confirm the existing test suite is green before touching anything**

Run: `npm test -- RankingEvolutionChart`
Expected: all 12 existing tests PASS (this is the safety net for the refactor below — it must stay green throughout).

- [ ] **Step 2: Replace `yOf` and the line path with d3-scale/d3-shape**

In `frontend/components/tcn/participation-detail/RankingEvolutionChart.tsx`, add the import and replace the block currently computing `yOf`, `xOf`, and `line` (currently lines ~68-77):

```tsx
"use client";
import { useState } from "react";
import { scaleLinear } from "d3-scale";
import { line as d3Line, curveMonotoneX } from "d3-shape";
import type { RankingEvolutionStep } from "@/lib/types";
import { splitColumnsFromKeys } from "@/lib/utils/splits";
import { Card } from "../Card";
import { Eyebrow } from "../Eyebrow";
```

Replace:

```tsx
  // Position → ordonnée. `y` croît vers le bas, la meilleure position a le plus
  // petit numéro : la conversion directe met donc bien le 1er en haut.
  const yOf = (position: number) =>
    PAD.top + ((position - top) / Math.max(1, bottom - top)) * PLOT_H;
  const xOf = (index: number) =>
    PAD.left + (PLOT_W / steps.length) * (index + 0.5);

  const line = steps
    .map((step, index) => `${index === 0 ? "M" : "L"} ${xOf(index)} ${yOf(step.scratch_position)}`)
    .join(" ");
```

with:

```tsx
  // Position → ordonnée. Domaine [top, bottom] → pixel [PAD.top, PAD.top+PLOT_H] :
  // la meilleure position (top, la plus petite) tombe en haut du graphique.
  const yScale = scaleLinear().domain([top, bottom]).range([PAD.top, PAD.top + PLOT_H]);
  const yOf = (position: number) => yScale(position);
  const xOf = (index: number) =>
    PAD.left + (PLOT_W / steps.length) * (index + 0.5);

  const linePoints = steps.map((step, index) => ({
    x: xOf(index),
    y: yOf(step.scratch_position),
  }));
  const line =
    d3Line<{ x: number; y: number }>()
      .x((point) => point.x)
      .y((point) => point.y)
      .curve(curveMonotoneX)(linePoints) ?? "";
```

Leave the `ticks` computation (`Array.from({ length: TICKS }, ...)`) untouched — it's the same "evenly-spaced-by-index" business rule as the histogram's Y axis, not a coordinate projection (per Global Constraints); only feed its output through `yOf` for pixel position, which the render code already does unchanged.

- [ ] **Step 3: Run the test to verify the migration preserved behavior**

Run: `npm test -- RankingEvolutionChart`
Expected: all 12 tests still PASS. (`curveMonotoneX` changes the `<path>`'s `d` attribute — a smoother line — but no test asserts on that attribute, only on `data-role`/`data-step`/`data-y` and tooltip text, all unaffected.)

- [ ] **Step 4: Verify the production build**

Run: `npm run build`
Expected: succeeds. This file already has `"use client"` — no RSC boundary change to check here.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/tcn/participation-detail/RankingEvolutionChart.tsx
git commit -m "refactor(frontend): migre l'évolution du rang vers d3-scale et d3-shape (#370)"
```

---

### Task 5: Migrate the monthly-activity chart (PR/lot 4)

**Files:**
- Create: `frontend/components/charts/MonthlyTrend.test.tsx`
- Modify: `frontend/components/charts/MonthlyTrend.tsx` (internal only — no new file, no prop change, stays CSS-flex, not SVG)

**Interfaces:**
- No change to the component's exported signature (`MonthlyTrend({ byMonth })`).

- [ ] **Step 1: Write the characterization test**

Create `frontend/components/charts/MonthlyTrend.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MonthlyTrend } from "./MonthlyTrend";

describe("MonthlyTrend", () => {
  it("affiche un état vide quand aucune donnée mensuelle", () => {
    render(<MonthlyTrend byMonth={{}} />);
    expect(screen.getByText("Pas encore de données mensuelles.")).toBeInTheDocument();
  });

  it("garde une hauteur minimale visible même à zéro résultat", () => {
    const { container } = render(
      <MonthlyTrend byMonth={{ "2026-01": 0, "2026-02": 20 }} />,
    );
    const bars = [...container.querySelectorAll(".rounded-t-sm")] as HTMLElement[];
    expect(bars[0].style.height).toBe("4%");
  });

  it("donne 100% de hauteur au mois du maximum", () => {
    const { container } = render(
      <MonthlyTrend byMonth={{ "2026-01": 0, "2026-02": 20 }} />,
    );
    const bars = [...container.querySelectorAll(".rounded-t-sm")] as HTMLElement[];
    expect(bars[1].style.height).toBe("100%");
  });

  it("ne garde que les 12 derniers mois, triés chronologiquement", () => {
    // 14 mois valides à cheval sur deux années : les clés `YYYY-MM` restent
    // triables lexicographiquement dans le bon ordre chronologique.
    const byMonth = {
      "2025-01": 1, "2025-02": 2, "2025-03": 3, "2025-04": 4,
      "2025-05": 5, "2025-06": 6, "2025-07": 7, "2025-08": 8,
      "2025-09": 9, "2025-10": 10, "2025-11": 11, "2025-12": 12,
      "2026-01": 13, "2026-02": 14,
    };
    const { container } = render(<MonthlyTrend byMonth={byMonth} />);
    const bars = [...container.querySelectorAll(".rounded-t-sm")];
    expect(bars.length).toBe(12);
  });
});
```

- [ ] **Step 2: Run the test against the current implementation to establish the baseline**

Run: `npm test -- MonthlyTrend`
Expected: all 4 tests PASS (this characterizes existing behavior — no implementation change yet).

- [ ] **Step 3: Replace the manual scaling with d3-scale, preserving the clamp**

In `frontend/components/charts/MonthlyTrend.tsx`, add the import and replace the height calculation:

```tsx
import { scaleLinear } from "d3-scale";
import { formatMonthShort, formatMonth } from "@/lib/utils/date";
```

Replace the line:

```tsx
            style={{ height: `${Math.max(4, (value / max) * 100)}%` }}
```

with:

```tsx
            style={{ height: `${Math.max(4, heightScale(value))}%` }}
```

and add, right after `const max = Math.max(1, ...entries.map(([, v]) => v));`:

```tsx
  // d3-scale ne fait que la partie linéaire (0→max sur 0→100) ; le plancher de
  // 4 % pour rester visible à zéro reste un `Math.max` explicite au point
  // d'usage — ce n'est PAS un `range([4, 100])`, qui décalerait toutes les
  // valeurs intermédiaires (`range([4,100])` donne 52 % pour une valeur moitié
  // du max, pas 50 % : deux formules différentes, pas juste deux écritures).
  const heightScale = scaleLinear().domain([0, max]).range([0, 100]);
```

- [ ] **Step 4: Run the test to verify the migration preserved behavior**

Run: `npm test -- MonthlyTrend`
Expected: all 4 tests still PASS — in particular the zero-value bar must still report `4%`, not some other value.

- [ ] **Step 5: Verify the production build**

Run: `npm run build`
Expected: succeeds. `MonthlyTrend` has no `"use client"` today and must still not need one (d3-scale touches no DOM).

- [ ] **Step 6: Commit**

```bash
git add frontend/components/charts/MonthlyTrend.tsx frontend/components/charts/MonthlyTrend.test.tsx
git commit -m "refactor(frontend): migre l'activité mensuelle vers d3-scale (#370)"
```

---

### Task 6: Duplication review and final verification (closes #370)

**Files:** none expected to change — this task is a read-and-decide pass, per the design doc's explicit "no shared helper before it's earned" call.

- [ ] **Step 1: Compare the four `scaleLinear()` usages introduced by Tasks 1-5**

| File | Domain | Range | Guard |
| --- | --- | --- | --- |
| `Histogram.tsx` | `[0, max]` | `[bottom, top]` (190 → 20) | `max > 0 ? ... : () => bottom` |
| `CategoryBars.tsx` | `[0, total]` | `[0, 100]` | `total > 0 ? ... : () => 0` |
| `MonthlyTrend.tsx` | `[0, max]` | `[0, 100]` | none (external `Math.max(4, ...)` clamp) |
| `RankingEvolutionChart.tsx` | `[top, bottom]` | `[PAD.top, PAD.top+PLOT_H]` | none (domain never degenerates, see step 2 of Task 4) |

Read the four files as actually committed (not this table) before deciding — confirm the shapes still hold.

**Correction (post-implementation)**: as actually shipped, `CategoryBars.tsx` (`domain([0, total])`, `range([0, 100])`) and `MonthlyTrend.tsx` (`domain([0, max])`, `range([0, 100])`) DO share the same domain shape (`[0, X]`) and the same range (`[0, 100]`) — the table above understated this. They differ only in the guard: `CategoryBars` has a runtime ternary (`total > 0 ? ... : () => 0`), while `MonthlyTrend` relies on an upstream invariant (`max = Math.max(1, ...)`, computed before the scale, so `max` is never zero and no ternary is needed).

- [ ] **Step 2: Decide on extraction**

Domain+range shape alone isn't a strong enough signal to extract a helper: the two matching rows (`CategoryBars`, `MonthlyTrend`) differ in how they guard the zero case, and the runtime ternary in `CategoryBars` is arguably safer than relying on an upstream invariant holding forever — collapsing them into one helper would mean picking one guard strategy for both, which is a behavior decision dressed as a refactor, not a pure deduplication. Per the earlier decision (no abstraction before a real duplicate appears), the expected outcome is still: **no shared helper** — leave each `scaleLinear()` call inline where it is. A one-line wrapper isn't worth the abstraction here. Only extract a helper if, on reading the actual final code, two calls turn out to be identical in domain, range, **and** guard — in which case add `frontend/lib/charts/scales.ts` exporting that one shared function, update both call sites, add/adjust their tests, and commit as `refactor(frontend): factorise <nom> entre <fichiers> (#370)`.

- [ ] **Step 3: Run the full verification suite**

```bash
cd frontend
npm run lint
npm test
npm run build
```

Expected: all three succeed with zero errors/warnings introduced by this migration.

- [ ] **Step 4: Confirm no dead code remains**

```bash
grep -n "conic-gradient" "app/courses/[id]/page.tsx" || echo "OK: plus de conic-gradient"
grep -n "CAT_COLORS\|function Legend\|function pctFr\|function Histogram" "app/courses/[id]/page.tsx" || echo "OK: rien à nettoyer"
```

Expected: both `echo "OK"` lines print — confirms Tasks 1-3 fully removed the code they were meant to replace, per the "code mort supprimé, pas conservé" acceptance criterion.

- [ ] **Step 5: Final commit (only if Step 2 produced a change)**

If Step 2 concluded "no shared helper" (the expected outcome), there is nothing to commit for this task — #370 is complete as of Task 5's commit. If Step 2 did extract a helper, commit it per the message given in Step 2.
