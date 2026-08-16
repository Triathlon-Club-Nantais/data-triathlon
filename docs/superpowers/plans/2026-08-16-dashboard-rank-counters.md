# Compteurs de rang du dashboard calculés en backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop shipping up to 5000 raw `Participation` rows in the `/dashboard` RSC payload — move the Victoires/Podiums/Top10 aggregation (currently done client-side in `StatCardsRank`) into `stats_service.get_stats`, and give `/ajouter`'s prefetched `listEvents` call the same short-revalidate window `/dashboard` and `/club` already have.

**Architecture:** `stats_service.get_stats` already loads the full filtered `Participation` list (`parts`) in Python to build `by_type`/`by_month`/`recent` — a new private helper computes the 4 rank-mode counters (scratch/category/all/gender) on that same list, added as `rank_counters` on the existing `/stats` response (no new route). `StatCardsRank` stops receiving `participations: Participation[]` and instead receives the precomputed `rankCounters`, picking the bucket for the current `?rank=` — the pushState-driven, network-free toggle (#132/#328) is unchanged. `dashboard/page.tsx` drops its `apiServer.listParticipations(...)` call entirely. `/ajouter`'s `listEvents()` gets `{ revalidateSeconds: SHORT_REVALIDATE_SECONDS }`, same pattern as #352.

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy (backend, pytest); Next.js 16 App Router / TypeScript / Vitest + RTL (frontend).

**Spec:** `docs/superpowers/specs/2026-08-16-dashboard-rank-counters-design.md`

## Global Constraints

- No new backend route — `rank_counters` is an added field on the existing `GET /stats` response (Principe IV: additive only, nothing removed/renamed).
- `/club` is out of scope and must not change (its `participations` feed real row-level display, not just an aggregate — see spec).
- The gender bucket counts **only** athletes whose `gender` (case-insensitive) is exactly `"F"` or `"M"` — this mirrors the current frontend behavior in `club-aggregate.ts` exactly (athletes with any other value, e.g. `"H"`, are excluded from gender-mode counts today); this plan preserves that behavior, it does not "fix" it.
- Ranks are only counted when non-null and `>= 1`, matching current frontend semantics (`rank != null && rank >= 1`).
- `?rank=` toggle stays a client-only `pushState` recompute with **zero** network request — the 4 modes are computed together, once, server-side.

---

### Task 1: Backend — `rank_counters` on `GET /stats`

**Files:**
- Modify: `backend/app/services/stats_service.py:1-71` (imports + `get_stats`, new helper)
- Test: `backend/tests/test_services/test_stats_service.py`

**Interfaces:**
- Produces: `stats_service.get_stats(...)` return dict gains a `"rank_counters"` key, shape:
  ```python
  {
      "scratch":  {"victories": int, "podiums": int, "top10": int},
      "category": {"victories": int, "podiums": int, "top10": int},
      "all":      {"victories": int, "podiums": int, "top10": int},
      "gender": {
          "women": {"victories": int, "podiums": int, "top10": int},
          "men":   {"victories": int, "podiums": int, "top10": int},
      },
  }
  ```
  Present on **every** call to `get_stats`, including the empty-result early return.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_services/test_stats_service.py` (near the top, after `_seed`/before `test_list_events_counts_tcn` — anywhere at module level works, place after `test_get_stats_filtre_par_saison`):

```python
def _participation_rang(
    db, *, athlete_gender="", rank_overall=None, rank_category=None, rank_gender=None
):
    """Une participation isolée, sur sa propre épreuve, pour ne pas polluer les
    autres tests de rang (chaque appel crée son propre athlète/course)."""
    unique = f"{rank_overall}-{rank_category}-{rank_gender}-{athlete_gender}-{id(object())}"
    athlete = athlete_repository.get_or_create(
        db, nom="RANG", prenom=unique, gender=athlete_gender, club="TCN"
    )
    course = course_repository.get_or_create(
        db, name=f"Course rang {unique}", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(
        db,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number="1",
        club="TCN",
        rank_overall=rank_overall,
        rank_category=rank_category,
        rank_gender=rank_gender,
    )
    db.flush()


def test_get_stats_rank_counters_vide_sans_participation(db_session):
    stats = stats_service.get_stats(db_session)
    assert stats["rank_counters"] == {
        "scratch": {"victories": 0, "podiums": 0, "top10": 0},
        "category": {"victories": 0, "podiums": 0, "top10": 0},
        "all": {"victories": 0, "podiums": 0, "top10": 0},
        "gender": {
            "women": {"victories": 0, "podiums": 0, "top10": 0},
            "men": {"victories": 0, "podiums": 0, "top10": 0},
        },
    }


def test_get_stats_rank_counters_scratch_et_category_independants(db_session):
    # Victoire scratch (rank_overall=1) mais hors top10 en catégorie (rank_category=15).
    _participation_rang(db_session, rank_overall=1, rank_category=15)
    # Podium en catégorie (rank_category=3) mais hors classement scratch (rank_overall=None).
    _participation_rang(db_session, rank_category=3)

    stats = stats_service.get_stats(db_session)
    rc = stats["rank_counters"]

    assert rc["scratch"] == {"victories": 1, "podiums": 1, "top10": 1}
    assert rc["category"] == {"victories": 0, "podiums": 1, "top10": 1}


def test_get_stats_rank_counters_emboitement_victoires_podiums_top10(db_session):
    """victoires ≤ podiums ≤ top10, même invariant que côté front (issue #77)."""
    _participation_rang(db_session, rank_overall=1)
    _participation_rang(db_session, rank_overall=3)
    _participation_rang(db_session, rank_overall=10)
    _participation_rang(db_session, rank_overall=200)

    scratch = stats_service.get_stats(db_session)["rank_counters"]["scratch"]
    assert scratch == {"victories": 1, "podiums": 2, "top10": 3}


def test_get_stats_rank_counters_all_prend_le_min_des_trois(db_session):
    # rank_overall=50 mais rank_category=1 : le mode "all" doit capter la victoire.
    _participation_rang(db_session, rank_overall=50, rank_category=1, rank_gender=20)

    rc = stats_service.get_stats(db_session)["rank_counters"]
    assert rc["all"] == {"victories": 1, "podiums": 1, "top10": 1}
    assert rc["scratch"] == {"victories": 0, "podiums": 0, "top10": 0}


def test_get_stats_rank_counters_gender_ventile_f_h(db_session):
    _participation_rang(db_session, athlete_gender="F", rank_gender=1)
    _participation_rang(db_session, athlete_gender="M", rank_gender=2)
    _participation_rang(db_session, athlete_gender="f", rank_gender=8)  # casse ignorée

    rc = stats_service.get_stats(db_session)["rank_counters"]["gender"]
    assert rc["women"] == {"victories": 1, "podiums": 1, "top10": 2}
    assert rc["men"] == {"victories": 0, "podiums": 1, "top10": 1}


def test_get_stats_rank_counters_gender_ignore_les_genres_non_f_m(db_session):
    """Comportement préservé du front (`club-aggregate.ts`) : seuls "F"/"M"
    comptent, un athlète "H" n'entre dans aucun des deux compteurs."""
    _participation_rang(db_session, athlete_gender="H", rank_gender=1)

    rc = stats_service.get_stats(db_session)["rank_counters"]["gender"]
    assert rc["women"] == {"victories": 0, "podiums": 0, "top10": 0}
    assert rc["men"] == {"victories": 0, "podiums": 0, "top10": 0}


def test_get_stats_rank_counters_ignore_les_rangs_nuls_ou_absents(db_session):
    _participation_rang(db_session, rank_overall=None)
    _participation_rang(db_session, rank_overall=0)  # jamais valide, garde `>= 1`

    rc = stats_service.get_stats(db_session)["rank_counters"]["scratch"]
    assert rc == {"victories": 0, "podiums": 0, "top10": 0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_services/test_stats_service.py -k rank_counters -v`
Expected: FAIL — `KeyError: 'rank_counters'` on every test.

- [ ] **Step 3: Implement `_rank_counters` and wire it into `get_stats`**

In `backend/app/services/stats_service.py`, add the helper (place it right before `get_stats`, after the `_athlete_key` helper at line 16):

```python
def _bucket() -> dict:
    return {"victories": 0, "podiums": 0, "top10": 0}


def _accumule(bucket: dict, rang: int | None) -> None:
    if rang is None or rang < 1:
        return
    if rang <= 1:
        bucket["victories"] += 1
    if rang <= 3:
        bucket["podiums"] += 1
    if rang <= 10:
        bucket["top10"] += 1


def _meilleur_rang(rangs: list[int | None]) -> int | None:
    valides = [r for r in rangs if r is not None and r >= 1]
    return min(valides) if valides else None


def _rank_counters(parts) -> dict:
    """Compteurs Victoires/Podiums/Top10 des 4 modes de rang du dashboard.

    Calculés en une passe sur les participations déjà chargées par
    `get_stats` — aucune requête supplémentaire. Miroir du calcul
    auparavant fait côté client par `rankCounters`
    (`frontend/lib/utils/club-aggregate.ts`) : le comportement de chaque
    mode, y compris la ventilation genre limitée à "F"/"M", est repris à
    l'identique (#376 déplace le calcul, ne le change pas).
    """
    scratch, category, tous = _bucket(), _bucket(), _bucket()
    genre = {"women": _bucket(), "men": _bucket()}

    for p in parts:
        _accumule(scratch, p.rank_overall)
        _accumule(category, p.rank_category)
        _accumule(tous, _meilleur_rang([p.rank_overall, p.rank_gender, p.rank_category]))

        g = (p.athlete.gender or "").upper() if p.athlete else ""
        if g == "F":
            _accumule(genre["women"], p.rank_gender)
        elif g == "M":
            _accumule(genre["men"], p.rank_gender)

    return {"scratch": scratch, "category": category, "all": tous, "gender": genre}
```

Then modify `get_stats` (lines 18-71) so **both** the empty-result early return and the normal return include `rank_counters`:

```python
def get_stats(
    db: Session,
    *,
    club_only: bool = False,
    seasons: list[int] | None = None,
    federal_only: bool = False,
) -> dict:
    """Stats agrégées : total, athlètes, épreuves, répartition par type/mois, récents."""
    parts = participation_repository.for_stats(
        db, club_only=club_only, seasons=seasons, federal_only=federal_only
    )
    if not parts:
        return {
            "total": 0, "athletes": 0, "events": 0, "by_type": {}, "by_month": {}, "recent": [],
            "rank_counters": _rank_counters([]),
        }

    athlete_set = {p.athlete_id for p in parts}
    event_set = {p.course_id for p in parts}
    by_type: Counter[str] = Counter()
    by_month: Counter[str] = Counter()
    for p in parts:
        course = p.course
        if course and course.event_type:
            by_type[course.event_type] += 1
        if course and course.event_date:
            by_month[str(course.event_date)[:7]] += 1  # YYYY-MM

    recent = sorted(
        (p for p in parts if p.created_at),
        key=lambda p: p.created_at,
        reverse=True,
    )[:20]

    return {
        "total": len(parts),
        "athletes": len(athlete_set),
        "events": len(event_set),
        "by_type": dict(sorted(by_type.items(), key=lambda x: -x[1])),
        "by_month": dict(sorted(by_month.items())),
        "recent": [
            {
                "id": p.id,
                "athlete_name": p.athlete.nom if p.athlete else "",
                "athlete_firstname": p.athlete.prenom if p.athlete else "",
                "club": p.club or "",
                "event_name": p.course.name if p.course else "",
                "event_type": p.course.event_type if p.course else "",
                "event_date": p.course.event_date.isoformat()
                if p.course and p.course.event_date
                else None,
                "total_time": p.total_time or "",
                "scraped_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in recent
        ],
        "rank_counters": _rank_counters(parts),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_services/test_stats_service.py -v`
Expected: PASS — all tests in the file, including the new `rank_counters` ones and every pre-existing test (they only assert other keys, unaffected by the addition).

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff check app/services/stats_service.py tests/test_services/test_stats_service.py
git add backend/app/services/stats_service.py backend/tests/test_services/test_stats_service.py
git commit -m "$(cat <<'EOF'
feat(backend): calcule rank_counters dans stats_service.get_stats (#376)

Les 4 modes de rang du dashboard (scratch/catégorie/tous/genre) sont
désormais calculés en une passe sur les participations déjà chargées
par get_stats, sans requête supplémentaire. Prépare la suppression de
l'envoi des participations brutes au front pour ce seul usage.
EOF
)"
```

---

### Task 2: Frontend — `StatCardsRank` lit `rankCounters` au lieu de `participations`

**Files:**
- Modify: `frontend/lib/types.ts:142-149` (`Stats` interface)
- Modify: `frontend/components/dashboard/StatCardsRank.tsx` (full rewrite of the exported component)
- Test: `frontend/components/dashboard/StatCardsRank.test.tsx` (full rewrite)

**Interfaces:**
- Consumes: nothing from Task 1 directly (frontend/backend are separate builds) — but the shape of `DashboardRankCounters` defined here **must** match the JSON produced by `stats_service._rank_counters` in Task 1 (`{scratch, category, all: {victories, podiums, top10}, gender: {women, men}}`).
- Produces: `export interface RankCountersBucket { victories: number; podiums: number; top10: number }` and `export interface DashboardRankCounters { scratch: RankCountersBucket; category: RankCountersBucket; all: RankCountersBucket; gender: { women: RankCountersBucket; men: RankCountersBucket } }` in `frontend/lib/types.ts`, plus `Stats.rank_counters: DashboardRankCounters`. `StatCardsRank` now takes `{ rankCounters: DashboardRankCounters }` instead of `{ participations: Participation[] }` — Task 3 relies on this new prop name and type.

- [ ] **Step 1: Write the failing test**

Replace the full contents of `frontend/components/dashboard/StatCardsRank.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { DashboardRankCounters } from "@/lib/types";

let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

import { StatCardsRank } from "./StatCardsRank";

// Valeurs volontairement distinctes par mode, pour vérifier que le bon
// mode est bien sélectionné et non un autre par erreur d'indexation.
const COUNTERS: DashboardRankCounters = {
  scratch: { victories: 0, podiums: 1, top10: 1 },
  category: { victories: 1, podiums: 1, top10: 1 },
  all: { victories: 1, podiums: 2, top10: 2 },
  gender: {
    women: { victories: 0, podiums: 0, top10: 1 },
    men: { victories: 0, podiums: 1, top10: 1 },
  },
};

describe("StatCardsRank — sélection du bucket selon ?rank=", () => {
  it("sans ?rank= : mode scratch (défaut)", () => {
    searchParams = new URLSearchParams();
    render(<StatCardsRank rankCounters={COUNTERS} />);
    expect(screen.getAllByText("général")).toHaveLength(3);
  });

  it("?rank=category : affiche les compteurs catégorie", () => {
    searchParams = new URLSearchParams("rank=category");
    render(<StatCardsRank rankCounters={COUNTERS} />);
    expect(screen.getAllByText("catégorie")).toHaveLength(3);
  });

  it("?rank=gender : dédouble F / H", () => {
    searchParams = new URLSearchParams("rank=gender");
    render(<StatCardsRank rankCounters={COUNTERS} />);
    expect(screen.getAllByText("genre")).toHaveLength(3);
    expect(screen.getAllByText("F")).toHaveLength(3);
    expect(screen.getAllByText("H")).toHaveLength(3);
  });

  it("?rank=all : mode agrégé", () => {
    searchParams = new URLSearchParams("rank=all");
    render(<StatCardsRank rankCounters={COUNTERS} />);
    expect(screen.getAllByText("général, genre ou catégorie")).toHaveLength(3);
  });

  it("?rank=foo : retombe silencieusement sur scratch", () => {
    searchParams = new URLSearchParams("rank=foo");
    render(<StatCardsRank rankCounters={COUNTERS} />);
    expect(screen.getAllByText("général")).toHaveLength(3);
    expect(screen.queryByText("catégorie")).not.toBeInTheDocument();
  });

  it("recalcule sur un changement de paramètre, sans remontage", () => {
    // Propriété dont dépend #328 : le sélecteur écrit l'URL par
    // `history.pushState`, donc le composant n'est jamais remonté.
    searchParams = new URLSearchParams();
    const { rerender } = render(<StatCardsRank rankCounters={COUNTERS} />);
    expect(screen.getAllByText("général")).toHaveLength(3);

    searchParams = new URLSearchParams("rank=category");
    rerender(<StatCardsRank rankCounters={COUNTERS} />);

    expect(screen.getAllByText("catégorie")).toHaveLength(3);
    expect(screen.queryByText("général")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/dashboard/StatCardsRank.test.tsx`
Expected: FAIL — `StatCardsRank` still expects a `participations` prop; type/runtime mismatch (`rankCounters` is `undefined`, component throws reading `rankCounters.gender`/`rankCounters[rankType]`).

- [ ] **Step 3: Add the types and rewrite the component**

In `frontend/lib/types.ts`, replace the `Stats` interface (lines 142-149) with:

```ts
export interface RankCountersBucket {
  victories: number;
  podiums: number;
  top10: number;
}

export interface DashboardRankCounters {
  scratch: RankCountersBucket;
  category: RankCountersBucket;
  all: RankCountersBucket;
  gender: { women: RankCountersBucket; men: RankCountersBucket };
}

export interface Stats {
  total: number;
  athletes: number;
  events: number;
  by_type: Record<string, number>;
  by_month: Record<string, number>;
  recent: RecentItem[];
  rank_counters: DashboardRankCounters;
}
```

Replace the full contents of `frontend/components/dashboard/StatCardsRank.tsx`:

```tsx
"use client";
import type { ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import { StatCard } from "@/components/tcn";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
import { rankTypeLabel } from "@/lib/labels";
import type { DashboardRankCounters } from "@/lib/types";

const TrophyIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tcn-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 4h12v3a6 6 0 0 1-12 0V4z" /><path d="M6 5H3v2a3 3 0 0 0 3 3" /><path d="M18 5h3v2a3 3 0 0 1-3 3" /><path d="M9 17h6" /><path d="M12 13v4" /><path d="M8 21h8" /></svg>
);
const PodiumIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tcn-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="4" width="6" height="17" /><rect x="2" y="10" width="6" height="11" /><rect x="16" y="8" width="6" height="13" /></svg>
);
const Top10Icon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tcn-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="9" r="6" /><path d="M12 6v3l2 1" /><path d="M9 14l-2 7 5-3 5 3-2-7" /></svg>
);

// Rendu dédoublé F / H pour le mode gender (#104 US3). L'espacement passe par
// des marges plutôt que le `gap` du flex : le `gap` fait partie de la plage
// sélectionnable et peignait une bande orange dans le vide entre les libellés
// et leurs chiffres, une marge reste hors de la sélection (#375).
function GenderPair({ women, men }: { women: number; men: number }): ReactNode {
  return (
    <span style={{ display: "inline-flex", alignItems: "baseline", fontFamily: "var(--tcn-font-display)" }}>
      <span style={{ display: "inline-flex", alignItems: "baseline" }}>
        <span style={{ fontSize: 20, fontWeight: 700, color: "var(--tcn-text-muted)", marginRight: 6 }}>F</span>
        <span>{women}</span>
      </span>
      <span style={{ display: "inline-flex", alignItems: "baseline", marginLeft: 18 }}>
        <span style={{ fontSize: 20, fontWeight: 700, color: "var(--tcn-text-muted)", marginRight: 6 }}>H</span>
        <span>{men}</span>
      </span>
    </span>
  );
}

/**
 * Les 3 cartes « Victoires / Podiums / Top 10 » côté client.
 *
 * Les compteurs des 4 modes sont calculés **une fois** côté backend
 * (`stats_service.get_stats`, champ `rank_counters`) — ce composant ne fait
 * plus que choisir le bucket courant selon `?rank=…`, sans recalcul ni
 * re-fetch (#132/#328 restent vrais : aucun réseau au changement de mode).
 * Avant #376, ce composant recevait les participations brutes du club (jusqu'à
 * 5000 lignes) pour ce seul calcul — déplacé en backend, la page n'a plus à
 * les charger du tout.
 */
export function StatCardsRank({ rankCounters }: { rankCounters: DashboardRankCounters }) {
  const sp = useSearchParams();
  const rankType = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);
  const rankLabel = rankTypeLabel(rankType, { form: "long" });

  if (rankType === "gender") {
    const { women, men } = rankCounters.gender;
    return (
      <>
        <StatCard label="Victoires" value={<GenderPair women={women.victories} men={men.victories} />} delta={rankLabel} icon={<TrophyIcon />} />
        <StatCard label="Podiums" value={<GenderPair women={women.podiums} men={men.podiums} />} delta={rankLabel} icon={<PodiumIcon />} />
        <StatCard label="Top 10" value={<GenderPair women={women.top10} men={men.top10} />} delta={rankLabel} icon={<Top10Icon />} />
      </>
    );
  }
  const counters = rankCounters[rankType];
  return (
    <>
      <StatCard label="Victoires" value={counters.victories} delta={rankLabel} icon={<TrophyIcon />} />
      <StatCard label="Podiums" value={counters.podiums} delta={rankLabel} icon={<PodiumIcon />} />
      <StatCard label="Top 10" value={counters.top10} delta={rankLabel} icon={<Top10Icon />} />
    </>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/dashboard/StatCardsRank.test.tsx`
Expected: PASS — all 6 tests.

- [ ] **Step 5: Type-check and commit**

```bash
cd frontend && npx tsc --noEmit
git add frontend/lib/types.ts frontend/components/dashboard/StatCardsRank.tsx frontend/components/dashboard/StatCardsRank.test.tsx
git commit -m "$(cat <<'EOF'
refactor(frontend): StatCardsRank lit rank_counters au lieu de participations (#376)

Le composant ne recalcule plus les compteurs sur les participations
brutes du club : il sélectionne le bucket précalculé par le backend
selon ?rank=, sans changer le comportement au clic (#132/#328).
EOF
)"
```

---

### Task 3: Frontend — `/dashboard` arrête de charger les participations brutes

**Files:**
- Modify: `frontend/app/dashboard/page.tsx:1-47`
- Test: `frontend/app/dashboard/page.test.tsx`

**Interfaces:**
- Consumes: `StatCardsRank` from Task 2 — now takes `{ rankCounters: DashboardRankCounters }`; `Stats.rank_counters` (`DashboardRankCounters`) from Task 2's `lib/types.ts` edit.
- Produces: nothing further downstream (leaf page).

- [ ] **Step 1: Write the failing test — update `frontend/app/dashboard/page.test.tsx`**

Replace the mock setup and `STATS`/`PARTICIPATIONS` fixtures at the top of the file (lines 1-50) with:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const getStats = vi.fn();
const listEvents = vi.fn();
const listSeasons = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
    getStats: (opts: unknown, fetchOpts?: unknown) => getStats(opts, fetchOpts),
    listEvents: (filters: unknown, fetchOpts?: unknown) => listEvents(filters, fetchOpts),
    listSeasons: (opts: unknown, fetchOpts?: unknown) => listSeasons(opts, fetchOpts),
  },
  SHORT_REVALIDATE_SECONDS: 30,
}));

// SeasonSelector et DisciplineToggle sont des composants client
// (useRouter/usePathname/useSearchParams).
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(),
}));

import DashboardPage from "./page";

const ZERO_BUCKET = { victories: 0, podiums: 0, top10: 0 };
const STATS = {
  total: 42,
  athletes: 10,
  events: 5,
  by_type: { "Triathlon S": 30, "Duathlon M": 12 },
  by_month: {},
  recent: [],
  rank_counters: {
    scratch: ZERO_BUCKET,
    category: ZERO_BUCKET,
    all: ZERO_BUCKET,
    gender: { women: ZERO_BUCKET, men: ZERO_BUCKET },
  },
};
const EVENTS_PAGE = { items: [], total_events: 5, total_participations: 42 };
const SEASONS = [
  { start_year: 2026, label: "Saison 2026", event_count: 5, participation_count: 42, is_current: true },
  { start_year: 2025, label: "Saison 2025", event_count: 3, participation_count: 20, is_current: false },
];

beforeEach(() => {
  vi.clearAllMocks();
  getStats.mockResolvedValue(STATS);
  listEvents.mockResolvedValue(EVENTS_PAGE);
  listSeasons.mockResolvedValue(SEASONS);
});
```

Then, further down the file:
- In the test `"force la portée club sur tous les appels API, même sans ?scope=club"`, remove the `listParticipations` assertion (lines 66-69 of the original), keeping only the `getStats`/`listEvents` ones.
- Rename and update `"demande une fenêtre de revalidation courte sur les quatre appels (#352)"` to:

```tsx
  it("demande une fenêtre de revalidation courte sur les trois appels (#352)", async () => {
    await renderDashboard({});

    expect(getStats).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
    expect(listEvents).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
    expect(listSeasons).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
  });
```

  `listParticipations` no longer exists on the mocked `apiServer` module (it
  was dropped from the mock in Step 1). If `page.tsx` still called it, that
  call would throw `TypeError: apiServer.listParticipations is not a
  function` inside `renderDashboard`, failing **every** test in this file —
  that's the regression guard for "the raw fetch is gone", no separate test
  needed for it.

- In the final `describe("DashboardPage — sélecteur de type de rang", ...)` block, replace its single test with:

```tsx
describe("DashboardPage — sélecteur de type de rang", () => {
  it("monte le StatCardsRank avec le mode par défaut (libellé « général »)", async () => {
    await renderDashboard({});
    expect(screen.getAllByText("général").length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByText("général, genre ou catégorie")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run app/dashboard/page.test.tsx`
Expected: FAIL — `page.tsx` still calls `apiServer.listParticipations`, which no longer exists on the mocked module (`TypeError: apiServer.listParticipations is not a function`), and still passes a `participations` prop `StatCardsRank` no longer accepts.

- [ ] **Step 3: Update `frontend/app/dashboard/page.tsx`**

Replace lines 1-47 (imports through the end of the data-fetching block) with:

```tsx
import Link from "next/link";
import { apiServer, SHORT_REVALIDATE_SECONDS } from "@/lib/api/server";
import { SCOPE_CLUB, federalOnlyFromParam } from "@/lib/scope";
import { DisciplineToggle } from "@/components/layout/DisciplineToggle";
import { RankTypeToggle } from "@/components/layout/RankTypeToggle";
import { SeasonSelector } from "@/components/dashboard/SeasonSelector";
import { StatCardsRank } from "@/components/dashboard/StatCardsRank";
import { currentSeason, parseSeasonsParam, seasonSelectionLabel } from "@/lib/utils/season";
import { StatCard, Card, Eyebrow, FormatChip } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { aggregateDisciplines, formatToken, pctFr } from "@/lib/utils/format";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  // Page d'accueil = vitrine du club : portée TCN forcée, pas de choix « Tous »
  // (validé par Vincent, issue #6). Le paramètre `?scope` est volontairement
  // ignoré, mais on lit `?seasons` pour le sélecteur de saison (issue #7) et
  // `?sports` pour le filtre fédéral/hors-fédération (issue #76).
  const sp = await searchParams;

  // Calcul de la sélection de saisons depuis l'URL, avec fallback sur la saison en cours
  const fromUrl = parseSeasonsParam(sp.seasons);
  const selected = fromUrl.length > 0 ? fromUrl : [currentSeason()];
  const federal_only = federalOnlyFromParam(sp.sports);

  // Fenêtre de revalidation courte (#352) : les trois appels rejouaient
  // l'intégralité du rendu serveur à chaque visite (`cache: "no-store"`),
  // pour un coût que le sondage du 2026-08-14 chiffre à 1,5-1,8 s une fois
  // les N+1 corrigés (#350/#351) — un `revalidate` masque ce coût pour
  // l'écrasante majorité des visites, sans retarder la visibilité d'un
  // import (batch) au-delà de ce qu'un visiteur tolère.
  const revalidateOpts = { revalidateSeconds: SHORT_REVALIDATE_SECONDS };
  const [stats, eventsPage, seasons] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB, seasons: selected, federal_only }, revalidateOpts),
    apiServer.listEvents(
      { scope: SCOPE_CLUB, seasons: selected, federal_only, page_size: 200 },
      revalidateOpts,
    ),
    apiServer.listSeasons({ scope: SCOPE_CLUB, federal_only }, revalidateOpts),
  ]);

  const disciplines = aggregateDisciplines(stats.by_type);
  const topEvents = [...eventsPage.items].sort((a, b) => b.total - a.total).slice(0, 6);
```

The rest of the file (the JSX return, from `return (` onward) is unchanged **except** the `StatCardsRank` usage:

```tsx
        <StatCard variant="hero" label="Dossards enregistrés" value={stats.total.toLocaleString("fr-FR")} delta={`${stats.athletes} athlètes · ${stats.events} épreuves`} />
        <StatCardsRank rankCounters={stats.rank_counters} />
```

(same line position as the current `<StatCardsRank participations={participations} />`, just the prop swapped.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run app/dashboard/page.test.tsx`
Expected: PASS — all tests.

- [ ] **Step 5: Type-check, full frontend suite, and commit**

```bash
cd frontend && npx tsc --noEmit && npm test
git add frontend/app/dashboard/page.tsx frontend/app/dashboard/page.test.tsx
git commit -m "$(cat <<'EOF'
perf(frontend): /dashboard n'embarque plus les participations brutes (#376)

apiServer.listParticipations (jusqu'à 5000 lignes) est supprimé de
/dashboard : StatCardsRank lit désormais stats.rank_counters, calculé
en backend (#376). Le payload RSC de la page ne contient plus que les
compteurs agrégés pour ce composant.
EOF
)"
```

---

### Task 4: Frontend — fenêtre de revalidation courte sur `/ajouter`

**Files:**
- Modify: `frontend/app/ajouter/page.tsx:1-17`
- Create: `frontend/app/ajouter/page.test.tsx`

**Interfaces:**
- Consumes: `SHORT_REVALIDATE_SECONDS` (already exported by `frontend/lib/api/server.ts`, unchanged — used since #352).
- Produces: nothing further downstream.

- [ ] **Step 1: Write the failing test**

Create `frontend/app/ajouter/page.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

const listEvents = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
    listEvents: (filters: unknown, fetchOpts?: unknown) => listEvents(filters, fetchOpts),
  },
  SHORT_REVALIDATE_SECONDS: 30,
}));

// TcnScrapeForm est un composant client lourd (routeur, requêtes, SSE) sans
// rapport avec ce qui est testé ici — le comportement de son propre fichier
// est couvert par ses propres tests.
vi.mock("@/components/scrape/TcnScrapeForm", () => ({
  TcnScrapeForm: () => null,
}));

import AjouterPage from "./page";

beforeEach(() => {
  vi.clearAllMocks();
  listEvents.mockResolvedValue({ items: [], total_events: 0, total_participations: 0 });
});

describe("AjouterPage", () => {
  it("demande une fenêtre de revalidation courte sur listEvents (#376)", async () => {
    const ui = await AjouterPage();
    render(ui);

    expect(listEvents).toHaveBeenCalledWith(
      { page_size: 6, sort: "imported_desc" },
      { revalidateSeconds: 30 },
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run app/ajouter/page.test.tsx`
Expected: FAIL — `listEvents` is called with only one argument (`{ page_size: 6, sort: "imported_desc" }`), no second argument, so `toHaveBeenCalledWith` fails on the missing `{ revalidateSeconds: 30 }`.

- [ ] **Step 3: Update `frontend/app/ajouter/page.tsx`**

Change the import line and the `listEvents` call:

```tsx
import { apiServer, SHORT_REVALIDATE_SECONDS } from "@/lib/api/server";
```

```tsx
  // « Derniers résultats enregistrés » (#201) : tri par date d'import, pas par
  // date d'épreuve, sans quoi une épreuve ancienne qu'on vient d'importer
  // resterait invisible sous 6 épreuves à venir déjà en base. Fenêtre de
  // revalidation courte (#376) : ce lien est prefetché en continu par le
  // bouton « + » de la navigation globale, présent sur toutes les pages.
  const events = await apiServer
    .listEvents({ page_size: 6, sort: "imported_desc" }, { revalidateSeconds: SHORT_REVALIDATE_SECONDS })
    .catch(() => null);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run app/ajouter/page.test.tsx`
Expected: PASS.

- [ ] **Step 5: Type-check, full frontend suite, and commit**

```bash
cd frontend && npx tsc --noEmit && npm test
git add frontend/app/ajouter/page.tsx frontend/app/ajouter/page.test.tsx
git commit -m "$(cat <<'EOF'
perf(frontend): revalidate court sur listEvents de /ajouter (#376)

Ce lien est prefetché par le bouton « + » de la navigation globale sur
toutes les pages ; il n'avait aucune fenêtre de cache (`no-store`),
contrairement à /dashboard et /club depuis #352. Même patron ici.
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:** backend `rank_counters` (Task 1) ✓; frontend drops raw participations on `/dashboard` (Tasks 2-3) ✓; `/ajouter` revalidate (Task 4) ✓; `/club` untouched (no task touches it, matches "hors périmètre") ✓.
- **Type consistency:** `DashboardRankCounters` (Task 2, `lib/types.ts`) is used identically in `StatCardsRank.tsx` (Task 2) and `dashboard/page.tsx` (Task 3, via `stats.rank_counters`) — same field names (`scratch`/`category`/`all`/`gender`/`women`/`men`/`victories`/`podiums`/`top10`) as the Python dict built in Task 1's `_rank_counters`.
- **Ordering:** Task 2 must land before Task 3 (page consumes the new `StatCardsRank` prop). Task 1 and Task 4 are independent of the others and of each other.
