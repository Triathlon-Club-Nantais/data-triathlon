# frontend-v2 (Next.js / shadcn/ui) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Réécrire le frontend (`frontend-v2/`) en Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui, consommant l'API **backend-v2** versionnée `/api/v1` (modèle normalisé Athlete/Course/Participation), à parité fonctionnelle complète avec l'ancien `frontend/`.

**Architecture :** Rendu **hybride** — Server Components pour les pages en lecture (listes, fiches), Client Components + TanStack Query pour l'interactif (formulaires, import SSE, feed). Les filtres vivent dans l'URL (`searchParams`), pas de state global. Le frontend parle au backend via les **rewrites Next** en client et via `fetch` absolu en RSC.

**Tech Stack :** Next.js 15 (React 19), TypeScript strict, Tailwind CSS, shadcn/ui (Radix + lucide-react), TanStack Query v5, react-hook-form + zod, next-themes, sonner, react-leaflet, Vitest + @testing-library/react + jsdom. Package manager : `npm`.

---

## Contrats API (source de vérité : schémas Pydantic backend-v2)

Ces faits sont vérifiés dans le code backend-v2 ; ne pas les ré-inventer.

- **Base URL** : `/api/v1` (montée dans `app/main.py`).
- **`splits`** : dict `{segment: temps}` dont les clés sont `swim`, `t1`, `bike`, `t2`, `run` (suffixe `_time` retiré, segments vides omis). Source : `app/services/mapping.py:build_splits`.
- **`ParticipationOut`** imbrique `athlete: AthleteBrief` et `course: CourseBrief` (plus de champ plat `swim_time`). Source : `app/schemas/participation.py`.
- **`AthleteBrief`** : `{ id, nom, prenom, gender, club }` (`club: str | null`).
- **`CourseBrief`** : `{ id, name, event_date, event_type, provider, source_url, is_relay }` (`event_date: str | null` ISO date).
- **SSE phases** (`POST /scrape/event/stream`, lignes `data: {json}\n\n`) : `{phase:"scraping",message}` → `{phase:"saving",total,imported,skipped,progress}` (émis tous les 20) → `{phase:"done",imported,skipped,total}` | `{phase:"error",message}`. Source : `app/services/import_service.py:iter_import_event`.
- **`GET /athletes/{id}`** → `{ athlete: AthleteBrief, participations: ParticipationOut[] }`.
- **`GET /courses/{id}`** → `{ course: CourseBrief, participations: ParticipationOut[] }`.
- **`GET /stats`** → `{ total, athletes, events, by_type: {type:count}, by_month: {"YYYY-MM":count}, recent: RecentItem[] }` où `RecentItem = { id, athlete_name, athlete_firstname, club, event_name, event_type, event_date, total_time, scraped_at }`.
- **`GET /stats/events-geo`** → `GeoEvent[]` : `{ event_name, event_date, event_type, count, tcn_count, lat, lon }`.
- **`GET /courses/events`** → `EventOut[]` : `{ event_name, event_date, event_type, total, tcn_count }`.
- **`POST /scrape`** body `{url, bib?}` → `ScrapedPreview` (forme **plate** : `athlete_name, athlete_firstname, club, category, gender, bib_number, event_name, event_date, event_type, rank_overall, rank_category, rank_gender, total_time, swim_time, t1_time, bike_time, t2_time, run_time, is_relay, provider, source_url, raw_data`).
- **`GET /scrape/detect?url=`** → `{ provider }`.
- **`POST /participations`** body = `ParticipationCreate` (forme plate, même champs segments `swim_time…`) → `ParticipationOut`.
- **`GET /participations`** query : `name, event_type, event_name, club, date_from, date_to, page, page_size` → `ParticipationOut[]`.
- **`DELETE /participations/{id}`** → 204.
- **Admin** : `GET /admin/pending-providers` → `{id,url,provider_hint,reported_at}[]` ; `POST` body `{url}` ; `DELETE /admin/pending-providers/{id}` → 204.
- **Erreurs** : le backend renvoie `{ detail: "..." }` sur erreur (handlers d'exception).

---

## File Structure

```
frontend-v2/
  app/
    layout.tsx                  # <Providers> + <AppHeader> + <Toaster>, lang="fr"
    globals.css                 # Tailwind + tokens shadcn
    page.tsx                    # redirect → /dashboard
    providers.tsx               # 'use client' : QueryClientProvider + ThemeProvider
    ajouter/page.tsx            # 'use client' : ScrapeForm + ImportProgress + ManualResultForm
    resultats/page.tsx          # RSC : liste filtrée (searchParams) + EventGroup (client)
    resultats/loading.tsx
    athletes/[id]/page.tsx      # RSC : fiche athlète + participations
    courses/[id]/page.tsx       # RSC : fiche course + participants
    club/page.tsx               # RSC initial : ClubStats (client) + AthleteDialog
    dashboard/page.tsx          # RSC KPIs + LiveFeed (client polling)
    carte/page.tsx              # client-only : MapView dynamique (ssr:false)
    admin/page.tsx              # RSC list + PendingProvidersTable (client actions)
    error.tsx                   # error boundary global
  components/
    ui/                         # primitives shadcn (générées)
    layout/AppHeader.tsx        # nav + Command (recherche) + filtre club + thème
    layout/ClubFilterToggle.tsx # 'use client' : toggle cookie tcn-only
    layout/GlobalSearch.tsx     # 'use client' : Command → /resultats?name=
    layout/ThemeToggle.tsx
    results/ResultCard.tsx
    results/SportBadge.tsx
    results/EventGroup.tsx      # 'use client' : Accordion groupé par épreuve
    results/ResultsFilters.tsx  # 'use client' : filtres → searchParams
    scrape/ProviderDetector.tsx
    scrape/ScrapeForm.tsx
    scrape/ImportProgress.tsx
    scrape/ManualResultForm.tsx
    club/ClubStats.tsx
    club/AthleteDialog.tsx
    dashboard/Kpis.tsx
    dashboard/LiveFeed.tsx
    admin/PendingProvidersTable.tsx
    map/MapView.tsx             # 'use client' : react-leaflet
  lib/
    types.ts                    # miroir des schémas Pydantic
    constants.ts                # EVENT_TYPE_LABELS + options
    cn.ts                       # helper className (shadcn)
    api/server.ts               # fetch RSC (API_URL absolu)
    api/client.ts               # fetch navigateur (rewrites /api/v1)
    api/sse.ts                  # importEventStream (AsyncGenerator)
    queries/keys.ts             # query keys TanStack
    queries/participations.ts   # useParticipations, useDeleteParticipation
    queries/stats.ts            # useStats
    queries/admin.ts            # usePendingProviders, useMarkHandled
    utils/time.ts               # formatHms, secondsFromHms
    utils/date.ts               # formatDate, timeAgo, formatMonth
    utils/club.ts               # isTCN
    utils/splits.ts             # splitSegments(eventType, splits)
  hooks/
    useImportStream.ts          # 'use client' : pilote l'import SSE
    useDebounce.ts
  test/setup.ts                 # config Vitest + jest-dom
  vitest.config.ts
  next.config.ts
  components.json               # shadcn
  tsconfig.json / tsconfig.json
  .env.local.example
  README.md
```

---

## PHASE 0 — Scaffold & socle

### Task 1: Initialiser le projet Next.js + dépendances

**Files:**
- Create: `frontend-v2/` (généré par create-next-app)

- [ ] **Step 1: Générer l'app Next.js**

Run (depuis la racine du repo) :

```bash
npx create-next-app@latest frontend-v2 \
  --ts --tailwind --eslint --app --src-dir=false \
  --import-alias "@/*" --use-npm --no-turbopack
```

Expected: dossier `frontend-v2/` créé avec `app/`, `tailwind.config.ts` (ou config Tailwind v4), `tsconfig.json`, `package.json`.

- [ ] **Step 2: Installer les dépendances applicatives**

Run (depuis `frontend-v2/`) :

```bash
cd frontend-v2
npm install @tanstack/react-query @tanstack/react-query-devtools \
  react-hook-form zod @hookform/resolvers next-themes sonner \
  lucide-react react-leaflet leaflet
npm install -D @types/leaflet vitest @testing-library/react \
  @testing-library/jest-dom @testing-library/user-event jsdom \
  @vitejs/plugin-react
```

Expected: installation sans erreur ; `package.json` liste ces paquets.

- [ ] **Step 3: Initialiser shadcn/ui**

Run (depuis `frontend-v2/`) :

```bash
npx shadcn@latest init -d
```

Expected: `components.json` créé, `lib/utils.ts` (helper `cn`) créé, `globals.css` mis à jour avec les tokens. (`-d` accepte les défauts : style, base color, CSS variables.)

- [ ] **Step 4: Ajouter les primitives shadcn nécessaires**

Run (depuis `frontend-v2/`) :

```bash
npx shadcn@latest add button card table badge dialog input label \
  select form accordion tabs progress command popover sonner \
  skeleton dropdown-menu separator
```

Expected: fichiers créés sous `components/ui/`.

- [ ] **Step 5: Vérifier le build de base**

Run: `npm run build`
Expected: build réussit (page d'accueil par défaut). Si Tailwind v4 vs v3 pose souci, suivre ce que `shadcn init` a généré (cf. spec §11).

- [ ] **Step 6: Commit**

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon
git add frontend-v2
git commit -m "feat(frontend-v2): scaffold Next.js + shadcn/ui + dépendances"
```

---

### Task 2: Configurer Vitest

**Files:**
- Create: `frontend-v2/vitest.config.ts`
- Create: `frontend-v2/test/setup.ts`
- Modify: `frontend-v2/package.json` (script `test`)

- [ ] **Step 1: Écrire `vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./test/setup.ts"],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, ".") },
  },
});
```

- [ ] **Step 2: Écrire `test/setup.ts`**

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 3: Ajouter le script de test**

Dans `frontend-v2/package.json`, ajouter dans `"scripts"` :

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 4: Test fumée pour valider la config**

Create `frontend-v2/test/smoke.test.ts` :

```ts
import { describe, it, expect } from "vitest";

describe("vitest setup", () => {
  it("fonctionne", () => {
    expect(1 + 1).toBe(2);
  });
});
```

Run: `npm test`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/vitest.config.ts frontend-v2/test frontend-v2/package.json
git commit -m "test(frontend-v2): configuration Vitest + RTL"
```

---

### Task 3: Configurer les rewrites Next et l'environnement

**Files:**
- Modify/Create: `frontend-v2/next.config.ts`
- Create: `frontend-v2/.env.local.example`

- [ ] **Step 1: Écrire `next.config.ts`**

Les appels client passent par `/api/v1/*` (même origine) ; Next les réécrit vers le backend, ce qui évite le CORS en dev.

```ts
import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8001";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` },
    ];
  },
};

export default nextConfig;
```

- [ ] **Step 2: Écrire `.env.local.example`**

```bash
# URL interne du backend pour les rewrites Next (client) ET le fetch RSC (serveur)
BACKEND_URL=http://localhost:8001
# URL absolue utilisée par les Server Components (peut différer en prod)
API_URL=http://localhost:8001
```

- [ ] **Step 3: Créer `.env.local` local**

```bash
cp frontend-v2/.env.local.example frontend-v2/.env.local
```

Expected: fichier `.env.local` présent (ignoré par git via le `.gitignore` de create-next-app).

- [ ] **Step 4: Vérifier le build**

Run: `cd frontend-v2 && npm run build`
Expected: build OK (rewrites n'empêchent pas le build).

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/next.config.ts frontend-v2/.env.local.example
git commit -m "feat(frontend-v2): rewrites /api → backend + variables d'env"
```

---

### Task 4: Types TypeScript (miroir Pydantic)

**Files:**
- Create: `frontend-v2/lib/types.ts`

- [ ] **Step 1: Écrire `lib/types.ts`**

```ts
// Miroir des schémas Pydantic backend-v2. Source de vérité : app/schemas/*.py.

export interface AthleteBrief {
  id: number;
  nom: string;
  prenom: string;
  gender: string;
  club: string | null;
}

export interface CourseBrief {
  id: number;
  name: string;
  event_date: string | null; // ISO date "YYYY-MM-DD"
  event_type: string;
  provider: string;
  source_url: string;
  is_relay: boolean;
}

// Clés possibles de splits : "swim" | "t1" | "bike" | "t2" | "run"
export type Splits = Record<string, string>;

export interface Participation {
  id: number;
  athlete: AthleteBrief;
  course: CourseBrief;
  club: string | null;
  category: string | null;
  bib_number: string | null;
  rank_overall: number | null;
  rank_category: number | null;
  rank_gender: number | null;
  total_time: string | null;
  status: string;
  splits: Splits | null;
  created_at: string | null;
}

export interface EventOut {
  event_name: string;
  event_date: string | null;
  event_type: string;
  total: number;
  tcn_count: number;
}

export interface GeoEvent {
  event_name: string;
  event_date: string | null;
  event_type: string;
  count: number;
  tcn_count: number;
  lat: number;
  lon: number;
}

export interface RecentItem {
  id: number;
  athlete_name: string;
  athlete_firstname: string;
  club: string;
  event_name: string;
  event_type: string;
  event_date: string | null;
  total_time: string;
  scraped_at: string | null;
}

export interface Stats {
  total: number;
  athletes: number;
  events: number;
  by_type: Record<string, number>;
  by_month: Record<string, number>;
  recent: RecentItem[];
}

// Forme plate renvoyée par POST /scrape et attendue par POST /participations.
export interface ScrapedPreview {
  provider: string;
  source_url: string;
  athlete_name: string;
  athlete_firstname: string;
  club: string;
  category: string;
  gender: string;
  bib_number: string;
  event_name: string;
  event_date: string | null;
  event_type: string;
  rank_overall: number | null;
  rank_category: number | null;
  rank_gender: number | null;
  total_time: string;
  swim_time: string;
  t1_time: string;
  bike_time: string;
  t2_time: string;
  run_time: string;
  is_relay: boolean;
  raw_data: Record<string, unknown>;
}

export interface ImportResult {
  imported: number;
  skipped: number;
  cached?: boolean;
}

// Événements du flux SSE d'import.
export type ImportProgressEvent =
  | { phase: "scraping"; message: string }
  | { phase: "saving"; total: number; imported: number; skipped: number; progress: number }
  | { phase: "done"; imported: number; skipped: number; total: number; cached?: boolean }
  | { phase: "error"; message: string };

export interface PendingProvider {
  id: number;
  url: string;
  provider_hint: string;
  reported_at: string | null;
}

export interface AthleteDetail {
  athlete: AthleteBrief;
  participations: Participation[];
}

export interface CourseDetail {
  course: CourseBrief;
  participations: Participation[];
}

export interface ParticipationFilters {
  name?: string;
  event_type?: string;
  event_name?: string;
  club?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}
```

- [ ] **Step 2: Vérifier le typage**

Run: `cd frontend-v2 && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 3: Commit**

```bash
git add frontend-v2/lib/types.ts
git commit -m "feat(frontend-v2): types TS miroir des schémas API v1"
```

---

### Task 5: Constantes (types d'épreuves)

**Files:**
- Create: `frontend-v2/lib/constants.ts`

- [ ] **Step 1: Écrire `lib/constants.ts`** (porté de `frontend/src/constants.js`)

```ts
export const EVENT_TYPE_LABELS: Record<string, string> = {
  "triathlon-s": "Triathlon S",
  "triathlon-m": "Triathlon M",
  "triathlon-l": "Triathlon L",
  "triathlon-xl": "Triathlon XL",
  "duathlon-xs": "Duathlon XS",
  "duathlon-s": "Duathlon S",
  "duathlon-m": "Duathlon M",
  "duathlon-l": "Duathlon L",
  duathlon: "Duathlon",
  "swimrun-s": "SwimRun S",
  "swimrun-m": "SwimRun M",
  "swimrun-l": "SwimRun L",
  swimrun: "SwimRun",
  aquathlon: "Aquathlon",
  aquarun: "Aquarun",
  "bike-run": "Bike & Run",
};

export const EVENT_TYPE_OPTIONS: { value: string; label: string }[] =
  Object.entries(EVENT_TYPE_LABELS).map(([value, label]) => ({ value, label }));

export function eventTypeLabel(type: string | null | undefined): string {
  if (!type) return "";
  return EVENT_TYPE_LABELS[type] ?? type;
}
```

- [ ] **Step 2: Vérifier le typage**

Run: `cd frontend-v2 && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 3: Commit**

```bash
git add frontend-v2/lib/constants.ts
git commit -m "feat(frontend-v2): constantes types d'épreuves"
```

---

## PHASE 1 — Utilitaires (TDD pur)

### Task 6: `utils/club.ts` (isTCN)

**Files:**
- Create: `frontend-v2/lib/utils/club.ts`
- Test: `frontend-v2/lib/utils/club.test.ts`

- [ ] **Step 1: Écrire le test (échoue)**

```ts
import { describe, it, expect } from "vitest";
import { isTCN } from "./club";

describe("isTCN", () => {
  it("reconnaît les variantes du club nantais", () => {
    expect(isTCN("TCN")).toBe(true);
    expect(isTCN("Triathlon Club Nantais")).toBe(true);
    expect(isTCN("Nantais Triathlon")).toBe(true);
  });
  it("est insensible à la casse", () => {
    expect(isTCN("triathlon club nant")).toBe(true);
  });
  it("renvoie false pour un autre club ou vide", () => {
    expect(isTCN("Stade Rennais")).toBe(false);
    expect(isTCN("")).toBe(false);
    expect(isTCN(null)).toBe(false);
  });
});
```

- [ ] **Step 2: Lancer le test (échoue)**

Run: `cd frontend-v2 && npx vitest run lib/utils/club.test.ts`
Expected: FAIL (`isTCN` introuvable).

- [ ] **Step 3: Implémenter `club.ts`** (porté de `app/core/club.py`)

```ts
const TCN_KEYWORDS = ["nantais", "tcn", "triathlon club nant"];

export function isTCN(club: string | null | undefined): boolean {
  if (!club) return false;
  const low = club.toLowerCase();
  return TCN_KEYWORDS.some((k) => low.includes(k));
}
```

- [ ] **Step 4: Lancer le test (passe)**

Run: `cd frontend-v2 && npx vitest run lib/utils/club.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/lib/utils/club.ts frontend-v2/lib/utils/club.test.ts
git commit -m "feat(frontend-v2): util isTCN (TDD)"
```

---

### Task 7: `utils/date.ts` (formatDate, timeAgo, formatMonth)

**Files:**
- Create: `frontend-v2/lib/utils/date.ts`
- Test: `frontend-v2/lib/utils/date.test.ts`

- [ ] **Step 1: Écrire le test (échoue)**

```ts
import { describe, it, expect, vi, afterEach } from "vitest";
import { formatDate, timeAgo, formatMonth } from "./date";

describe("formatDate", () => {
  it("formate une date ISO en fr-FR", () => {
    expect(formatDate("2026-03-15")).toBe("15/03/2026");
  });
  it("renvoie une chaîne vide si null", () => {
    expect(formatDate(null)).toBe("");
  });
});

describe("formatMonth", () => {
  it("formate YYYY-MM en mois/année français", () => {
    expect(formatMonth("2026-03")).toBe("mars 2026");
  });
});

describe("timeAgo", () => {
  afterEach(() => vi.useRealTimers());
  it("renvoie aujourd'hui pour maintenant", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-07T12:00:00Z"));
    expect(timeAgo("2026-06-07T08:00:00Z")).toBe("aujourd'hui");
  });
  it("renvoie hier pour la veille", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-07T12:00:00Z"));
    expect(timeAgo("2026-06-06T08:00:00Z")).toBe("hier");
  });
  it("renvoie une chaîne vide si null", () => {
    expect(timeAgo(null)).toBe("");
  });
});
```

- [ ] **Step 2: Lancer le test (échoue)**

Run: `cd frontend-v2 && npx vitest run lib/utils/date.test.ts`
Expected: FAIL (module introuvable).

- [ ] **Step 3: Implémenter `date.ts`** (porté de `ResultCard.jsx`)

```ts
export function formatDate(d: string | null | undefined): string {
  if (!d) return "";
  const m = String(d).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString("fr-FR");
  return String(d);
}

export function formatMonth(ym: string | null | undefined): string {
  if (!ym) return "";
  const m = String(ym).match(/^(\d{4})-(\d{2})/);
  if (!m) return String(ym);
  return new Date(+m[1], +m[2] - 1, 1).toLocaleDateString("fr-FR", {
    month: "long",
    year: "numeric",
  });
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86400000);
  if (days <= 0) return "aujourd'hui";
  if (days === 1) return "hier";
  if (days < 30) return `il y a ${days} j`;
  if (days < 365) return `il y a ${Math.floor(days / 30)} mois`;
  const years = Math.floor(days / 365);
  return `il y a ${years} an${years > 1 ? "s" : ""}`;
}
```

- [ ] **Step 4: Lancer le test (passe)**

Run: `cd frontend-v2 && npx vitest run lib/utils/date.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/lib/utils/date.ts frontend-v2/lib/utils/date.test.ts
git commit -m "feat(frontend-v2): utils date (formatDate, timeAgo, formatMonth) (TDD)"
```

---

### Task 8: `utils/splits.ts` (ordre des segments par sport)

C'est le cœur de l'adaptation au modèle normalisé : `ResultCard` lit `p.splits` (dict) au lieu des champs plats. La fonction renvoie une liste ordonnée de segments à afficher selon le type d'épreuve.

**Files:**
- Create: `frontend-v2/lib/utils/splits.ts`
- Test: `frontend-v2/lib/utils/splits.test.ts`

- [ ] **Step 1: Écrire le test (échoue)**

```ts
import { describe, it, expect } from "vitest";
import { splitSegments } from "./splits";

describe("splitSegments", () => {
  it("triathlon : natation, T1, vélo, T2, course", () => {
    const splits = { swim: "00:20:00", t1: "00:01:00", bike: "01:00:00", t2: "00:00:45", run: "00:35:00" };
    const segs = splitSegments("triathlon-m", splits);
    expect(segs.map((s) => s.label)).toEqual(["Natation", "T1", "Vélo", "T2", "Course"]);
    expect(segs[0].time).toBe("00:20:00");
    expect(segs[1].small).toBe(true); // T1 = transition
  });

  it("duathlon : Course 1, T1, Vélo, T2, Course 2", () => {
    const splits = { swim: "00:18:00", t1: "00:01:00", bike: "00:40:00", t2: "00:00:50", run: "00:20:00" };
    const segs = splitSegments("duathlon-s", splits);
    expect(segs.map((s) => s.label)).toEqual(["Course 1", "T1", "Vélo", "T2", "Course 2"]);
  });

  it("bike-run : Vélo, Course", () => {
    const segs = splitSegments("bike-run", { bike: "00:30:00", run: "00:20:00" });
    expect(segs.map((s) => s.label)).toEqual(["Vélo", "Course"]);
  });

  it("aquathlon : Natation, Course", () => {
    const segs = splitSegments("aquathlon", { swim: "00:10:00", run: "00:20:00" });
    expect(segs.map((s) => s.label)).toEqual(["Natation", "Course"]);
  });

  it("aquarun : Natation, T1, Course", () => {
    const segs = splitSegments("aquarun", { swim: "00:10:00", t1: "00:01:00", run: "00:20:00" });
    expect(segs.map((s) => s.label)).toEqual(["Natation", "T1", "Course"]);
  });

  it("omet les segments sans temps", () => {
    const segs = splitSegments("triathlon-m", { swim: "00:20:00", run: "00:35:00" });
    expect(segs.map((s) => s.label)).toEqual(["Natation", "Course"]);
  });

  it("renvoie un tableau vide si splits est null", () => {
    expect(splitSegments("triathlon-m", null)).toEqual([]);
  });
});
```

- [ ] **Step 2: Lancer le test (échoue)**

Run: `cd frontend-v2 && npx vitest run lib/utils/splits.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implémenter `splits.ts`**

```ts
import type { Splits } from "@/lib/types";

export interface Segment {
  key: string;
  label: string;
  time: string;
  color: string;
  small?: boolean;
}

// Schéma (clé du dict splits → libellé + couleur) par famille de sport.
// Clés possibles : swim, t1, bike, t2, run (cf. mapping.py build_splits).
type SchemaEntry = { key: string; label: string; color: string; small?: boolean };

const SWIM = "#3b82f6";
const RUN = "#10b981";
const BIKE = "#f59e0b";
const TRANS = "#94a3b8";

const SCHEMAS: Record<string, SchemaEntry[]> = {
  duathlon: [
    { key: "swim", label: "Course 1", color: RUN },
    { key: "t1", label: "T1", color: TRANS, small: true },
    { key: "bike", label: "Vélo", color: BIKE },
    { key: "t2", label: "T2", color: TRANS, small: true },
    { key: "run", label: "Course 2", color: RUN },
  ],
  "bike-run": [
    { key: "bike", label: "Vélo", color: BIKE },
    { key: "run", label: "Course", color: RUN },
  ],
  aquathlon: [
    { key: "swim", label: "Natation", color: SWIM },
    { key: "run", label: "Course", color: RUN },
  ],
  aquarun: [
    { key: "swim", label: "Natation", color: SWIM },
    { key: "t1", label: "T1", color: TRANS, small: true },
    { key: "run", label: "Course", color: RUN },
  ],
  triathlon: [
    { key: "swim", label: "Natation", color: SWIM },
    { key: "t1", label: "T1", color: TRANS, small: true },
    { key: "bike", label: "Vélo", color: BIKE },
    { key: "t2", label: "T2", color: TRANS, small: true },
    { key: "run", label: "Course", color: RUN },
  ],
};

function schemaFor(eventType: string): SchemaEntry[] {
  const type = eventType || "";
  if (type.startsWith("duathlon")) return SCHEMAS.duathlon;
  if (type === "bike-run") return SCHEMAS["bike-run"];
  if (type === "aquathlon") return SCHEMAS.aquathlon;
  if (type === "aquarun") return SCHEMAS.aquarun;
  return SCHEMAS.triathlon; // triathlon + swimrun + défaut
}

export function splitSegments(
  eventType: string,
  splits: Splits | null | undefined,
): Segment[] {
  if (!splits) return [];
  return schemaFor(eventType)
    .filter((s) => splits[s.key])
    .map((s) => ({ ...s, time: splits[s.key] }));
}
```

- [ ] **Step 4: Lancer le test (passe)**

Run: `cd frontend-v2 && npx vitest run lib/utils/splits.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/lib/utils/splits.ts frontend-v2/lib/utils/splits.test.ts
git commit -m "feat(frontend-v2): splitSegments adaptatif par sport (TDD)"
```

---

### Task 9: `utils/time.ts` + `hooks/useDebounce.ts`

**Files:**
- Create: `frontend-v2/lib/utils/time.ts`
- Test: `frontend-v2/lib/utils/time.test.ts`
- Create: `frontend-v2/hooks/useDebounce.ts`

- [ ] **Step 1: Écrire le test (échoue)**

```ts
import { describe, it, expect } from "vitest";
import { secondsFromHms } from "./time";

describe("secondsFromHms", () => {
  it("convertit HH:MM:SS en secondes", () => {
    expect(secondsFromHms("01:00:00")).toBe(3600);
    expect(secondsFromHms("00:01:30")).toBe(90);
  });
  it("gère MM:SS", () => {
    expect(secondsFromHms("02:30")).toBe(150);
  });
  it("renvoie null si vide ou invalide", () => {
    expect(secondsFromHms("")).toBeNull();
    expect(secondsFromHms("abc")).toBeNull();
  });
});
```

- [ ] **Step 2: Lancer le test (échoue)**

Run: `cd frontend-v2 && npx vitest run lib/utils/time.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implémenter `time.ts`**

```ts
/** Convertit "HH:MM:SS" ou "MM:SS" en secondes ; null si invalide. */
export function secondsFromHms(value: string | null | undefined): number | null {
  if (!value) return null;
  const parts = value.split(":").map((p) => Number(p));
  if (parts.some((n) => Number.isNaN(n))) return null;
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return null;
}
```

- [ ] **Step 4: Lancer le test (passe)**

Run: `cd frontend-v2 && npx vitest run lib/utils/time.test.ts`
Expected: PASS.

- [ ] **Step 5: Implémenter `hooks/useDebounce.ts`**

```ts
"use client";
import { useEffect, useState } from "react";

export function useDebounce<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend-v2/lib/utils/time.ts frontend-v2/lib/utils/time.test.ts frontend-v2/hooks/useDebounce.ts
git commit -m "feat(frontend-v2): util time + hook useDebounce (TDD)"
```

---

## PHASE 2 — Couches data (API client/serveur + SSE + queries)

### Task 10: `lib/api/client.ts` (fetch navigateur)

**Files:**
- Create: `frontend-v2/lib/api/client.ts`

- [ ] **Step 1: Écrire `lib/api/client.ts`**

Le client passe par les rewrites Next : chemins relatifs `/api/v1/*`.

```ts
import type {
  AthleteDetail,
  CourseDetail,
  EventOut,
  GeoEvent,
  ImportResult,
  Participation,
  ParticipationFilters,
  PendingProvider,
  ScrapedPreview,
  Stats,
} from "@/lib/types";

const BASE = "/api/v1";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Erreur réseau");
  }
  if (res.status === 204) return null as T;
  return res.json() as Promise<T>;
}

function toQuery(filters: Record<string, unknown>): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  });
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export const apiClient = {
  scrape: (url: string, bib: string | null = null) =>
    request<ScrapedPreview>("/scrape", {
      method: "POST",
      body: JSON.stringify({ url, bib }),
    }),

  detectProvider: (url: string) =>
    request<{ provider: string }>(`/scrape/detect${toQuery({ url })}`),

  importEvent: (url: string) =>
    request<ImportResult>("/scrape/event", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  saveParticipation: (data: Partial<ScrapedPreview>) =>
    request<Participation>("/participations", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listParticipations: (filters: ParticipationFilters = {}) =>
    request<Participation[]>(`/participations${toQuery(filters)}`),

  deleteParticipation: (id: number) =>
    request<null>(`/participations/${id}`, { method: "DELETE" }),

  getAthlete: (id: number) => request<AthleteDetail>(`/athletes/${id}`),
  getCourse: (id: number) => request<CourseDetail>(`/courses/${id}`),

  listEvents: (filters: ParticipationFilters = {}) =>
    request<EventOut[]>(`/courses/events${toQuery(filters)}`),

  getStats: (club?: string) => request<Stats>(`/stats${toQuery({ club })}`),
  getEventsGeo: (club?: string) =>
    request<GeoEvent[]>(`/stats/events-geo${toQuery({ club })}`),

  listPendingProviders: () =>
    request<PendingProvider[]>("/admin/pending-providers"),
  reportPendingProvider: (url: string) =>
    request<PendingProvider>("/admin/pending-providers", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  markProviderHandled: (id: number) =>
    request<null>(`/admin/pending-providers/${id}`, { method: "DELETE" }),
};
```

- [ ] **Step 2: Vérifier le typage**

Run: `cd frontend-v2 && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 3: Commit**

```bash
git add frontend-v2/lib/api/client.ts
git commit -m "feat(frontend-v2): client API navigateur (/api/v1)"
```

---

### Task 11: `lib/api/server.ts` (fetch RSC)

**Files:**
- Create: `frontend-v2/lib/api/server.ts`

- [ ] **Step 1: Écrire `lib/api/server.ts`**

Côté serveur, on ne peut pas utiliser de chemin relatif : on cible `API_URL` absolu. Données vivantes → `cache: "no-store"`.

```ts
import type {
  AthleteDetail,
  CourseDetail,
  EventOut,
  Participation,
  ParticipationFilters,
  PendingProvider,
  Stats,
} from "@/lib/types";

const API_URL = process.env.API_URL || "http://localhost:8001";
const BASE = `${API_URL}/api/v1`;

async function serverFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Erreur API (${res.status})`);
  }
  return res.json() as Promise<T>;
}

function toQuery(filters: Record<string, unknown>): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  });
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export const apiServer = {
  listParticipations: (filters: ParticipationFilters = {}) =>
    serverFetch<Participation[]>(`/participations${toQuery(filters)}`),
  getAthlete: (id: number) => serverFetch<AthleteDetail>(`/athletes/${id}`),
  getCourse: (id: number) => serverFetch<CourseDetail>(`/courses/${id}`),
  listEvents: (filters: ParticipationFilters = {}) =>
    serverFetch<EventOut[]>(`/courses/events${toQuery(filters)}`),
  getStats: (club?: string) => serverFetch<Stats>(`/stats${toQuery({ club })}`),
  listPendingProviders: () =>
    serverFetch<PendingProvider[]>("/admin/pending-providers"),
};
```

- [ ] **Step 2: Vérifier le typage**

Run: `cd frontend-v2 && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 3: Commit**

```bash
git add frontend-v2/lib/api/server.ts
git commit -m "feat(frontend-v2): client API serveur (RSC, no-store)"
```

---

### Task 12: `lib/api/sse.ts` (importEventStream) — TDD

**Files:**
- Create: `frontend-v2/lib/api/sse.ts`
- Test: `frontend-v2/lib/api/sse.test.ts`

- [ ] **Step 1: Écrire le test (échoue)**

On teste le parsing du flux : on simule un `Response` dont le `body` est un `ReadableStream` découpant les frames `data:` arbitrairement (même au milieu d'un objet).

```ts
import { describe, it, expect, vi } from "vitest";
import { importEventStream } from "./sse";
import type { ImportProgressEvent } from "@/lib/types";

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let i = 0;
  return new ReadableStream({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i++]));
      } else {
        controller.close();
      }
    },
  });
}

describe("importEventStream", () => {
  it("parse des frames SSE découpées sur plusieurs chunks", async () => {
    const chunks = [
      'data: {"phase":"scraping","mess',
      'age":"x"}\n\n',
      'data: {"phase":"saving","total":40,"imported":20,"skipped":0,"progress":20}\n\n',
      'data: {"phase":"done","imported":40,"skipped":0,"total":40}\n\n',
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      body: streamFromChunks(chunks),
    } as unknown as Response));

    const events: ImportProgressEvent[] = [];
    for await (const ev of importEventStream("http://x/race")) events.push(ev);

    expect(events.map((e) => e.phase)).toEqual(["scraping", "saving", "done"]);
    expect(events[2]).toMatchObject({ phase: "done", imported: 40 });
    vi.unstubAllGlobals();
  });

  it("lève une erreur si la réponse n'est pas ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false } as Response));
    await expect(async () => {
      for await (const _ of importEventStream("http://x")) { /* noop */ }
    }).rejects.toThrow();
    vi.unstubAllGlobals();
  });
});
```

- [ ] **Step 2: Lancer le test (échoue)**

Run: `cd frontend-v2 && npx vitest run lib/api/sse.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implémenter `sse.ts`** (porté de `client.js:importEventStream`)

```ts
import type { ImportProgressEvent } from "@/lib/types";

const BASE = "/api/v1";

export async function* importEventStream(
  url: string,
): AsyncGenerator<ImportProgressEvent> {
  const res = await fetch(`${BASE}/scrape/event/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok || !res.body) {
    throw new Error("Erreur lors du démarrage de l'import");
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const part of parts) {
      if (part.startsWith("data: ")) {
        try {
          yield JSON.parse(part.slice(6)) as ImportProgressEvent;
        } catch {
          /* frame incomplète ou bruit : ignorer */
        }
      }
    }
  }
}
```

- [ ] **Step 4: Lancer le test (passe)**

Run: `cd frontend-v2 && npx vitest run lib/api/sse.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/lib/api/sse.ts frontend-v2/lib/api/sse.test.ts
git commit -m "feat(frontend-v2): parsing SSE importEventStream (TDD)"
```

---

### Task 13: `hooks/useImportStream.ts`

**Files:**
- Create: `frontend-v2/hooks/useImportStream.ts`

- [ ] **Step 1: Implémenter le hook**

```ts
"use client";
import { useCallback, useRef, useState } from "react";
import { importEventStream } from "@/lib/api/sse";
import type { ImportProgressEvent } from "@/lib/types";

export interface ImportState {
  running: boolean;
  phase: ImportProgressEvent["phase"] | "idle";
  message: string;
  total: number;
  progress: number;
  imported: number;
  skipped: number;
  cached: boolean;
  error: string | null;
}

const INITIAL: ImportState = {
  running: false,
  phase: "idle",
  message: "",
  total: 0,
  progress: 0,
  imported: 0,
  skipped: 0,
  cached: false,
  error: null,
};

export function useImportStream() {
  const [state, setState] = useState<ImportState>(INITIAL);
  const activeRef = useRef(false);

  const start = useCallback(async (url: string) => {
    if (activeRef.current) return;
    activeRef.current = true;
    setState({ ...INITIAL, running: true, phase: "scraping", message: "Récupération des participants…" });
    try {
      for await (const ev of importEventStream(url)) {
        if (ev.phase === "scraping") {
          setState((s) => ({ ...s, phase: "scraping", message: ev.message }));
        } else if (ev.phase === "saving") {
          setState((s) => ({
            ...s,
            phase: "saving",
            total: ev.total,
            progress: ev.progress,
            imported: ev.imported,
            skipped: ev.skipped,
          }));
        } else if (ev.phase === "done") {
          setState((s) => ({
            ...s,
            running: false,
            phase: "done",
            total: ev.total,
            progress: ev.total,
            imported: ev.imported,
            skipped: ev.skipped,
            cached: Boolean(ev.cached),
          }));
        } else if (ev.phase === "error") {
          setState((s) => ({ ...s, running: false, phase: "error", error: ev.message }));
        }
      }
    } catch (e) {
      setState((s) => ({ ...s, running: false, phase: "error", error: (e as Error).message }));
    } finally {
      activeRef.current = false;
    }
  }, []);

  const reset = useCallback(() => setState(INITIAL), []);

  return { state, start, reset };
}
```

- [ ] **Step 2: Vérifier le typage**

Run: `cd frontend-v2 && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 3: Commit**

```bash
git add frontend-v2/hooks/useImportStream.ts
git commit -m "feat(frontend-v2): hook useImportStream (pilote l'import SSE)"
```

---

### Task 14: Query keys + hooks TanStack

**Files:**
- Create: `frontend-v2/lib/queries/keys.ts`
- Create: `frontend-v2/lib/queries/participations.ts`
- Create: `frontend-v2/lib/queries/stats.ts`
- Create: `frontend-v2/lib/queries/admin.ts`

- [ ] **Step 1: Écrire `keys.ts`**

```ts
import type { ParticipationFilters } from "@/lib/types";

export const queryKeys = {
  participations: (filters: ParticipationFilters = {}) =>
    ["participations", filters] as const,
  stats: (club?: string) => ["stats", club ?? null] as const,
  pendingProviders: () => ["pending-providers"] as const,
};
```

- [ ] **Step 2: Écrire `participations.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "./keys";
import type { ParticipationFilters, ScrapedPreview } from "@/lib/types";

export function useParticipations(filters: ParticipationFilters = {}, enabled = true) {
  return useQuery({
    queryKey: queryKeys.participations(filters),
    queryFn: () => apiClient.listParticipations(filters),
    enabled,
  });
}

export function useSaveParticipation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<ScrapedPreview>) => apiClient.saveParticipation(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["participations"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useDeleteParticipation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient.deleteParticipation(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["participations"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}
```

- [ ] **Step 3: Écrire `stats.ts`**

```ts
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "./keys";

export function useStats(club?: string) {
  return useQuery({
    queryKey: queryKeys.stats(club),
    queryFn: () => apiClient.getStats(club),
  });
}

/** Feed live : participations récentes, rafraîchies toutes les 15 s. */
export function useLiveFeed(club?: string) {
  return useQuery({
    queryKey: ["live-feed", club ?? null],
    queryFn: () => apiClient.listParticipations({ club, page_size: 20 }),
    refetchInterval: 15000,
  });
}
```

- [ ] **Step 4: Écrire `admin.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "./keys";

export function usePendingProviders() {
  return useQuery({
    queryKey: queryKeys.pendingProviders(),
    queryFn: () => apiClient.listPendingProviders(),
  });
}

export function useMarkProviderHandled() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient.markProviderHandled(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.pendingProviders() }),
  });
}
```

- [ ] **Step 5: Vérifier le typage**

Run: `cd frontend-v2 && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 6: Commit**

```bash
git add frontend-v2/lib/queries
git commit -m "feat(frontend-v2): hooks TanStack Query (participations, stats, admin)"
```

---

## PHASE 3 — Socle UI (Providers, layout, header)

### Task 15: Providers (QueryClient + ThemeProvider)

**Files:**
- Create: `frontend-v2/app/providers.tsx`

- [ ] **Step 1: Écrire `providers.tsx`**

```tsx
"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState, type ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
        {children}
      </ThemeProvider>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 2: Vérifier le typage**

Run: `cd frontend-v2 && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 3: Commit**

```bash
git add frontend-v2/app/providers.tsx
git commit -m "feat(frontend-v2): Providers (QueryClient + ThemeProvider)"
```

---

### Task 16: ThemeToggle + ClubFilterToggle (cookie)

Le filtre club est persisté en **cookie** `tcn-only` (lisible côté RSC), pas en localStorage.

**Files:**
- Create: `frontend-v2/components/layout/ThemeToggle.tsx`
- Create: `frontend-v2/components/layout/ClubFilterToggle.tsx`
- Create: `frontend-v2/lib/club-cookie.ts`

- [ ] **Step 1: Écrire `lib/club-cookie.ts`** (lecture serveur)

```ts
import { cookies } from "next/headers";

export const CLUB_COOKIE = "tcn-only";

/** true si le filtre « membres TCN uniquement » est actif (lu côté RSC). */
export async function isClubFilterActive(): Promise<boolean> {
  const store = await cookies();
  return store.get(CLUB_COOKIE)?.value === "1";
}

/** Valeur de filtre club à passer à l'API quand le toggle est actif. */
export const TCN_CLUB_FILTER = "nantais";
```

- [ ] **Step 2: Écrire `ThemeToggle.tsx`**

```tsx
"use client";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Changer de thème"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
    >
      <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
      <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
    </Button>
  );
}
```

- [ ] **Step 3: Écrire `ClubFilterToggle.tsx`**

```tsx
"use client";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Users } from "lucide-react";
import { CLUB_COOKIE } from "@/lib/club-cookie";

export function ClubFilterToggle({ active }: { active: boolean }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function toggle() {
    const next = active ? "0" : "1";
    document.cookie = `${CLUB_COOKIE}=${next}; path=/; max-age=31536000`;
    startTransition(() => router.refresh());
  }

  return (
    <Button
      variant={active ? "default" : "outline"}
      size="sm"
      onClick={toggle}
      disabled={pending}
    >
      <Users className="mr-2 h-4 w-4" />
      {active ? "Membres TCN" : "Tous"}
    </Button>
  );
}
```

- [ ] **Step 4: Vérifier le typage**

Run: `cd frontend-v2 && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/components/layout/ThemeToggle.tsx frontend-v2/components/layout/ClubFilterToggle.tsx frontend-v2/lib/club-cookie.ts
git commit -m "feat(frontend-v2): switch thème + filtre club (cookie RSC)"
```

---

### Task 17: GlobalSearch (Command) + AppHeader

**Files:**
- Create: `frontend-v2/components/layout/GlobalSearch.tsx`
- Create: `frontend-v2/components/layout/AppHeader.tsx`

- [ ] **Step 1: Écrire `GlobalSearch.tsx`**

```tsx
"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "@/components/ui/command";

export function GlobalSearch() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  function submit() {
    const q = value.trim();
    setOpen(false);
    setValue("");
    if (q) router.push(`/resultats?name=${encodeURIComponent(q)}`);
  }

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        <Search className="mr-2 h-4 w-4" />
        Rechercher un athlète…
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput
          placeholder="Nom d'un athlète…"
          value={value}
          onValueChange={setValue}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        <CommandList>
          <CommandEmpty>Appuyez sur Entrée pour rechercher.</CommandEmpty>
          <CommandGroup heading="Recherche">
            <CommandItem onSelect={submit}>
              Rechercher « {value} » dans les résultats
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  );
}
```

- [ ] **Step 2: Écrire `AppHeader.tsx`** (Server Component qui lit le cookie)

```tsx
import Link from "next/link";
import { isClubFilterActive } from "@/lib/club-cookie";
import { ThemeToggle } from "./ThemeToggle";
import { ClubFilterToggle } from "./ClubFilterToggle";
import { GlobalSearch } from "./GlobalSearch";

const NAV = [
  { href: "/dashboard", label: "Tableau de bord" },
  { href: "/resultats", label: "Résultats" },
  { href: "/club", label: "Club" },
  { href: "/carte", label: "Carte" },
  { href: "/ajouter", label: "Ajouter" },
  { href: "/admin", label: "Admin" },
];

export async function AppHeader() {
  const clubActive = await isClubFilterActive();
  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
        <Link href="/dashboard" className="font-bold">
          TCN Résultats
        </Link>
        <nav className="hidden gap-4 md:flex">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <GlobalSearch />
          <ClubFilterToggle active={clubActive} />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 3: Vérifier le typage**

Run: `cd frontend-v2 && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 4: Commit**

```bash
git add frontend-v2/components/layout/GlobalSearch.tsx frontend-v2/components/layout/AppHeader.tsx
git commit -m "feat(frontend-v2): header (nav + recherche Command + toggles)"
```

---

### Task 18: Layout racine + redirection + error boundary

**Files:**
- Modify: `frontend-v2/app/layout.tsx`
- Modify: `frontend-v2/app/page.tsx`
- Create: `frontend-v2/app/error.tsx`

- [ ] **Step 1: Écrire `app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { AppHeader } from "@/components/layout/AppHeader";
import { Toaster } from "@/components/ui/sonner";

export const metadata: Metadata = {
  title: "TCN — Résultats triathlon",
  description: "Résultats de compétition des membres du Triathlon Club Nantais",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <Providers>
          {/* @ts-expect-error Async Server Component */}
          <AppHeader />
          <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
          <Toaster richColors position="top-right" />
        </Providers>
      </body>
    </html>
  );
}
```

> Note : sur Next 15 / React 19, le commentaire `@ts-expect-error` peut être inutile ; si `tsc` signale qu'il est inutilisé, le retirer.

- [ ] **Step 2: Écrire `app/page.tsx`**

```tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/dashboard");
}
```

- [ ] **Step 3: Écrire `app/error.tsx`**

```tsx
"use client";
import { Button } from "@/components/ui/button";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4 py-20 text-center">
      <h2 className="text-lg font-semibold">Une erreur est survenue</h2>
      <p className="text-sm text-muted-foreground">{error.message}</p>
      <Button onClick={reset}>Réessayer</Button>
    </div>
  );
}
```

- [ ] **Step 4: Vérifier le build**

Run: `cd frontend-v2 && npm run build`
Expected: build OK ; `/` redirige vers `/dashboard` (les pages cibles seront créées plus tard — créer des placeholders si le build échoue sur routes manquantes : non, redirect ne casse pas le build). Si `/dashboard` n'existe pas encore, créer temporairement `app/dashboard/page.tsx` retournant `<div/>` (sera remplacé en Phase 6).

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/app/layout.tsx frontend-v2/app/page.tsx frontend-v2/app/error.tsx
git commit -m "feat(frontend-v2): layout racine + redirection + error boundary"
```

---

## PHASE 4 — Composants partagés (SportBadge, ResultCard, EventGroup)

### Task 19: SportBadge

**Files:**
- Create: `frontend-v2/components/results/SportBadge.tsx`
- Test: `frontend-v2/components/results/SportBadge.test.tsx`

- [ ] **Step 1: Écrire le test (échoue)**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SportBadge } from "./SportBadge";

describe("SportBadge", () => {
  it("affiche le libellé lisible du type", () => {
    render(<SportBadge type="triathlon-m" />);
    expect(screen.getByText("Triathlon M")).toBeInTheDocument();
  });
  it("retombe sur le type brut si inconnu", () => {
    render(<SportBadge type="xyz" />);
    expect(screen.getByText("xyz")).toBeInTheDocument();
  });
  it("ne rend rien si type vide", () => {
    const { container } = render(<SportBadge type="" />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Lancer le test (échoue)**

Run: `cd frontend-v2 && npx vitest run components/results/SportBadge.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implémenter `SportBadge.tsx`**

```tsx
import { Badge } from "@/components/ui/badge";
import { eventTypeLabel } from "@/lib/constants";

export function SportBadge({ type }: { type: string | null | undefined }) {
  if (!type) return null;
  return <Badge variant="secondary">{eventTypeLabel(type)}</Badge>;
}
```

- [ ] **Step 4: Lancer le test (passe)**

Run: `cd frontend-v2 && npx vitest run components/results/SportBadge.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/components/results/SportBadge.tsx frontend-v2/components/results/SportBadge.test.tsx
git commit -m "feat(frontend-v2): SportBadge (TDD)"
```

---

### Task 20: ResultCard (splits adaptatifs depuis p.splits)

**Files:**
- Create: `frontend-v2/components/results/ResultCard.tsx`
- Test: `frontend-v2/components/results/ResultCard.test.tsx`

- [ ] **Step 1: Écrire le test (échoue)**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResultCard } from "./ResultCard";
import type { Participation } from "@/lib/types";

const base: Participation = {
  id: 1,
  athlete: { id: 9, nom: "Dupont", prenom: "Marie", gender: "F", club: "TCN" },
  course: {
    id: 3,
    name: "Triathlon de Nantes",
    event_date: "2026-05-10",
    event_type: "triathlon-m",
    provider: "klikego",
    source_url: "http://x",
    is_relay: false,
  },
  club: "TCN",
  category: "S4",
  bib_number: "42",
  rank_overall: 12,
  rank_category: 2,
  rank_gender: 3,
  total_time: "02:15:30",
  status: "finisher",
  splits: { swim: "00:25:00", t1: "00:01:10", bike: "01:05:00", t2: "00:00:50", run: "00:43:30" },
  created_at: "2026-05-11T10:00:00Z",
};

describe("ResultCard", () => {
  it("affiche le nom complet (prénom + nom) et le temps total", () => {
    render(<ResultCard result={base} />);
    expect(screen.getByText("Marie Dupont")).toBeInTheDocument();
    expect(screen.getByText("02:15:30")).toBeInTheDocument();
  });

  it("affiche les segments triathlon depuis p.splits", () => {
    render(<ResultCard result={base} />);
    expect(screen.getByText("Natation")).toBeInTheDocument();
    expect(screen.getByText("Vélo")).toBeInTheDocument();
    expect(screen.getByText("Course")).toBeInTheDocument();
    expect(screen.getByText("00:25:00")).toBeInTheDocument();
  });

  it("adapte les libellés pour un duathlon", () => {
    const dua: Participation = {
      ...base,
      course: { ...base.course, event_type: "duathlon-s" },
      splits: { swim: "00:18:00", bike: "00:40:00", run: "00:20:00" },
    };
    render(<ResultCard result={dua} />);
    expect(screen.getByText("Course 1")).toBeInTheDocument();
    expect(screen.getByText("Course 2")).toBeInTheDocument();
  });

  it("n'affiche pas de bloc splits si splits est null", () => {
    render(<ResultCard result={{ ...base, splits: null }} />);
    expect(screen.queryByText("Natation")).not.toBeInTheDocument();
  });

  it("appelle onDelete après confirmation", async () => {
    const onDelete = vi.fn();
    render(<ResultCard result={base} onDelete={onDelete} />);
    const btn = screen.getByRole("button", { name: /supprimer/i });
    await userEvent.click(btn);
    await userEvent.click(screen.getByRole("button", { name: /confirmer/i }));
    expect(onDelete).toHaveBeenCalledWith(1);
  });
});
```

- [ ] **Step 2: Lancer le test (échoue)**

Run: `cd frontend-v2 && npx vitest run components/results/ResultCard.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implémenter `ResultCard.tsx`**

```tsx
"use client";
import { useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SportBadge } from "./SportBadge";
import { splitSegments } from "@/lib/utils/splits";
import { formatDate, timeAgo } from "@/lib/utils/date";
import type { Participation } from "@/lib/types";

export function ResultCard({
  result,
  onDelete,
}: {
  result: Participation;
  onDelete?: (id: number) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const a = result.athlete;
  const c = result.course;
  const fullName = [a?.prenom, a?.nom].filter(Boolean).join(" ") || "Athlète inconnu";
  const segments = splitSegments(c?.event_type ?? "", result.splits);

  function handleDelete() {
    if (!onDelete) return;
    if (confirming) {
      onDelete(result.id);
    } else {
      setConfirming(true);
      setTimeout(() => setConfirming(false), 3000);
    }
  }

  return (
    <Card>
      <CardContent className="space-y-3 p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <Link href={`/athletes/${a.id}`} className="text-lg font-bold hover:underline">
              {fullName}
            </Link>
            <div className="mt-1 flex flex-wrap gap-2 text-sm text-muted-foreground">
              {result.club && <span>{result.club}</span>}
              {result.category && <Badge variant="outline">{result.category}</Badge>}
              {a?.gender && <Badge variant="outline">{a.gender}</Badge>}
            </div>
          </div>
          <div className="flex items-center gap-3">
            {result.total_time && (
              <span className="font-mono text-xl font-extrabold">{result.total_time}</span>
            )}
            {onDelete && (
              <Button
                variant={confirming ? "destructive" : "ghost"}
                size="sm"
                onClick={handleDelete}
                aria-label={confirming ? "Confirmer la suppression" : "Supprimer"}
              >
                {confirming ? "Confirmer ?" : "×"}
              </Button>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 border-b pb-3 text-sm">
          <Link href={`/courses/${c.id}`} className="font-semibold hover:underline">
            {c?.name || "Épreuve inconnue"}
          </Link>
          <SportBadge type={c?.event_type} />
          {c?.event_date && (
            <span className="text-muted-foreground">{formatDate(c.event_date)}</span>
          )}
          {result.bib_number && (
            <span className="text-muted-foreground">#{result.bib_number}</span>
          )}
          {c?.is_relay && <Badge variant="destructive">Relais</Badge>}
        </div>

        {(result.rank_overall || result.rank_category || result.rank_gender) && (
          <div className="flex gap-6">
            {result.rank_overall != null && <Rank label="Général" value={result.rank_overall} />}
            {result.rank_gender != null && <Rank label="Genre" value={result.rank_gender} />}
            {result.rank_category != null && <Rank label="Catégorie" value={result.rank_category} />}
          </div>
        )}

        {segments.length > 0 && (
          <div className="flex flex-wrap gap-3 rounded-md bg-muted px-4 py-3">
            {segments.map((s) => (
              <div
                key={s.key}
                className="flex min-w-[60px] flex-col items-center"
                style={{ opacity: s.small ? 0.6 : 1 }}
              >
                <span className="text-xs font-bold uppercase" style={{ color: s.color }}>
                  {s.label}
                </span>
                <span className="font-mono text-sm font-semibold">{s.time}</span>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <a href={c?.source_url} target="_blank" rel="noopener noreferrer" className="hover:underline">
            Source ({c?.provider})
          </a>
          {result.created_at && <span>Ajouté {timeAgo(result.created_at)}</span>}
        </div>
      </CardContent>
    </Card>
  );
}

function Rank({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center">
      <span className="text-[11px] font-semibold uppercase text-muted-foreground">{label}</span>
      <span className="text-xl font-extrabold">{value}e</span>
    </div>
  );
}
```

- [ ] **Step 4: Lancer le test (passe)**

Run: `cd frontend-v2 && npx vitest run components/results/ResultCard.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/components/results/ResultCard.tsx frontend-v2/components/results/ResultCard.test.tsx
git commit -m "feat(frontend-v2): ResultCard avec splits adaptatifs (TDD)"
```

---

### Task 21: EventGroup (regroupement par épreuve)

**Files:**
- Create: `frontend-v2/components/results/EventGroup.tsx`

- [ ] **Step 1: Implémenter `EventGroup.tsx`**

Regroupe une liste de participations par `course.name` + `event_date` dans des `Accordion` ; chaque groupe affiche le compte et le sous-compte TCN.

```tsx
"use client";
import { useMemo } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { ResultCard } from "./ResultCard";
import { SportBadge } from "./SportBadge";
import { formatDate } from "@/lib/utils/date";
import { isTCN } from "@/lib/utils/club";
import type { Participation } from "@/lib/types";

interface Group {
  key: string;
  name: string;
  date: string | null;
  type: string;
  items: Participation[];
  tcnCount: number;
}

export function EventGroup({
  participations,
  onDelete,
}: {
  participations: Participation[];
  onDelete?: (id: number) => void;
}) {
  const groups = useMemo<Group[]>(() => {
    const map = new Map<string, Group>();
    for (const p of participations) {
      const name = p.course?.name ?? "Épreuve inconnue";
      const date = p.course?.event_date ?? null;
      const key = `${name}||${date ?? ""}`;
      let g = map.get(key);
      if (!g) {
        g = { key, name, date, type: p.course?.event_type ?? "", items: [], tcnCount: 0 };
        map.set(key, g);
      }
      g.items.push(p);
      if (isTCN(p.club)) g.tcnCount += 1;
    }
    return [...map.values()].sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""));
  }, [participations]);

  if (groups.length === 0) {
    return <p className="py-10 text-center text-muted-foreground">Aucun résultat.</p>;
  }

  return (
    <Accordion type="multiple" className="space-y-2">
      {groups.map((g) => (
        <AccordionItem key={g.key} value={g.key} className="rounded-md border px-4">
          <AccordionTrigger>
            <div className="flex flex-1 flex-wrap items-center gap-3 pr-4 text-left">
              <span className="font-semibold">{g.name}</span>
              <SportBadge type={g.type} />
              {g.date && <span className="text-sm text-muted-foreground">{formatDate(g.date)}</span>}
              <Badge variant="secondary" className="ml-auto">
                {g.items.length} résultat{g.items.length > 1 ? "s" : ""}
              </Badge>
              {g.tcnCount > 0 && <Badge>{g.tcnCount} TCN</Badge>}
            </div>
          </AccordionTrigger>
          <AccordionContent className="space-y-3 pt-2">
            {g.items.map((p) => (
              <ResultCard key={p.id} result={p} onDelete={onDelete} />
            ))}
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
```

- [ ] **Step 2: Vérifier le typage**

Run: `cd frontend-v2 && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 3: Commit**

```bash
git add frontend-v2/components/results/EventGroup.tsx
git commit -m "feat(frontend-v2): EventGroup (regroupement par épreuve)"
```

---

## PHASE 5 — Page « Ajouter » (scrape + import SSE + saisie manuelle)

### Task 22: ProviderDetector

**Files:**
- Create: `frontend-v2/components/scrape/ProviderDetector.tsx`

- [ ] **Step 1: Implémenter `ProviderDetector.tsx`**

Détecte le provider d'une URL (debounce) ; affiche un badge. Signale le provider via callback (utile pour basculer en saisie manuelle si `playwright`/inconnu).

```tsx
"use client";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import { useDebounce } from "@/hooks/useDebounce";
import { Badge } from "@/components/ui/badge";

const SUPPORTED = ["klikego", "breizhchrono", "timepulse", "wiclax", "prolivesport", "sportinnovation"];

export function ProviderDetector({
  url,
  onDetected,
}: {
  url: string;
  onDetected?: (provider: string) => void;
}) {
  const debounced = useDebounce(url, 400);
  const [provider, setProvider] = useState<string | null>(null);

  useEffect(() => {
    if (!debounced || !debounced.startsWith("http")) {
      setProvider(null);
      return;
    }
    let cancelled = false;
    apiClient
      .detectProvider(debounced)
      .then((r) => {
        if (cancelled) return;
        setProvider(r.provider);
        onDetected?.(r.provider);
      })
      .catch(() => !cancelled && setProvider(null));
    return () => {
      cancelled = true;
    };
  }, [debounced, onDetected]);

  if (!provider) return null;
  const supported = SUPPORTED.includes(provider);
  return (
    <Badge variant={supported ? "default" : "destructive"}>
      {supported ? `Fournisseur : ${provider}` : `Non supporté (${provider}) — saisie manuelle`}
    </Badge>
  );
}
```

- [ ] **Step 2: Vérifier le typage**

Run: `cd frontend-v2 && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 3: Commit**

```bash
git add frontend-v2/components/scrape/ProviderDetector.tsx
git commit -m "feat(frontend-v2): ProviderDetector (détection provider debounce)"
```

---

### Task 23: ImportProgress (barre SSE)

**Files:**
- Create: `frontend-v2/components/scrape/ImportProgress.tsx`

- [ ] **Step 1: Implémenter `ImportProgress.tsx`**

```tsx
"use client";
import { Progress } from "@/components/ui/progress";
import type { ImportState } from "@/hooks/useImportStream";

export function ImportProgress({ state }: { state: ImportState }) {
  if (state.phase === "idle") return null;

  const pct = state.total > 0 ? Math.round((state.progress / state.total) * 100) : 0;

  return (
    <div className="space-y-2 rounded-md border p-4 text-sm">
      {state.phase === "scraping" && <p>{state.message || "Récupération des participants…"}</p>}
      {state.phase === "saving" && (
        <>
          <div className="flex justify-between">
            <span>Import en cours… {state.progress}/{state.total}</span>
            <span className="text-muted-foreground">
              {state.imported} importés · {state.skipped} ignorés
            </span>
          </div>
          <Progress value={pct} />
        </>
      )}
      {state.phase === "done" && (
        <p className="text-green-600 dark:text-green-400">
          {state.cached
            ? `Déjà à jour (${state.skipped} participants en cache).`
            : `Import terminé : ${state.imported} ajoutés, ${state.skipped} ignorés.`}
        </p>
      )}
      {state.phase === "error" && (
        <p className="text-destructive">{state.error || "Erreur lors de l'import."}</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Vérifier le typage**

Run: `cd frontend-v2 && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 3: Commit**

```bash
git add frontend-v2/components/scrape/ImportProgress.tsx
git commit -m "feat(frontend-v2): ImportProgress (barre SSE)"
```

---

### Task 24: ManualResultForm (react-hook-form + zod)

**Files:**
- Create: `frontend-v2/components/scrape/ManualResultForm.tsx`

- [ ] **Step 1: Implémenter `ManualResultForm.tsx`**

Saisie manuelle d'un résultat quand le provider n'est pas supporté. Soumet une `Partial<ScrapedPreview>` (forme plate attendue par `POST /participations`).

```tsx
"use client";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EVENT_TYPE_OPTIONS } from "@/lib/constants";
import type { ScrapedPreview } from "@/lib/types";

const schema = z.object({
  athlete_firstname: z.string().min(1, "Prénom requis"),
  athlete_name: z.string().min(1, "Nom requis"),
  gender: z.string().optional().default(""),
  club: z.string().optional().default(""),
  event_name: z.string().min(1, "Épreuve requise"),
  event_date: z.string().optional().default(""),
  event_type: z.string().min(1, "Type requis"),
  bib_number: z.string().optional().default(""),
  category: z.string().optional().default(""),
  total_time: z.string().optional().default(""),
  swim_time: z.string().optional().default(""),
  t1_time: z.string().optional().default(""),
  bike_time: z.string().optional().default(""),
  t2_time: z.string().optional().default(""),
  run_time: z.string().optional().default(""),
  source_url: z.string().optional().default(""),
});

type ManualForm = z.infer<typeof schema>;

export function ManualResultForm({
  defaultUrl = "",
  onSubmit,
  submitting,
}: {
  defaultUrl?: string;
  onSubmit: (data: Partial<ScrapedPreview>) => void;
  submitting?: boolean;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ManualForm>({
    resolver: zodResolver(schema),
    defaultValues: { source_url: defaultUrl, provider: "manuel" } as Partial<ManualForm>,
  });

  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={handleSubmit((data) =>
        onSubmit({ ...data, provider: "manuel", event_date: data.event_date || null }),
      )}
    >
      <Field label="Prénom" error={errors.athlete_firstname?.message}>
        <Input {...register("athlete_firstname")} />
      </Field>
      <Field label="Nom" error={errors.athlete_name?.message}>
        <Input {...register("athlete_name")} />
      </Field>
      <Field label="Genre"><Input {...register("gender")} placeholder="M / F" /></Field>
      <Field label="Club"><Input {...register("club")} /></Field>
      <Field label="Épreuve" error={errors.event_name?.message}>
        <Input {...register("event_name")} />
      </Field>
      <Field label="Date"><Input type="date" {...register("event_date")} /></Field>
      <Field label="Type d'épreuve" error={errors.event_type?.message}>
        <select className="h-9 rounded-md border bg-background px-2" {...register("event_type")}>
          <option value="">—</option>
          {EVENT_TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </Field>
      <Field label="Dossard"><Input {...register("bib_number")} /></Field>
      <Field label="Catégorie"><Input {...register("category")} /></Field>
      <Field label="Temps total"><Input {...register("total_time")} placeholder="HH:MM:SS" /></Field>
      <Field label="Natation"><Input {...register("swim_time")} placeholder="HH:MM:SS" /></Field>
      <Field label="T1"><Input {...register("t1_time")} /></Field>
      <Field label="Vélo"><Input {...register("bike_time")} /></Field>
      <Field label="T2"><Input {...register("t2_time")} /></Field>
      <Field label="Course"><Input {...register("run_time")} /></Field>
      <div className="sm:col-span-2">
        <Button type="submit" disabled={submitting}>
          {submitting ? "Enregistrement…" : "Enregistrer le résultat"}
        </Button>
      </div>
    </form>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <Label>{label}</Label>
      {children}
      {error && <span className="text-xs text-destructive">{error}</span>}
    </div>
  );
}
```

- [ ] **Step 2: Vérifier le typage**

Run: `cd frontend-v2 && npx tsc --noEmit`
Expected: aucune erreur. (Si TS se plaint de `provider` absent du schéma dans `defaultValues`, retirer la propriété `provider` du cast et ne la passer qu'au `onSubmit`.)

- [ ] **Step 3: Commit**

```bash
git add frontend-v2/components/scrape/ManualResultForm.tsx
git commit -m "feat(frontend-v2): ManualResultForm (react-hook-form + zod)"
```

---

### Task 25: ScrapeForm (preview → édition → save)

**Files:**
- Create: `frontend-v2/components/scrape/ScrapeForm.tsx`

- [ ] **Step 1: Implémenter `ScrapeForm.tsx`**

Flux : saisir URL → scrape → preview éditable (champs plats) → save (`POST /participations`) → déclenche l'import épreuve en arrière-plan (SSE). Si le scrape échoue ou provider non supporté → propose la saisie manuelle (+ signalement admin).

```tsx
"use client";
import { useState, useCallback } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { useSaveParticipation } from "@/lib/queries/participations";
import { useImportStream } from "@/hooks/useImportStream";
import { ProviderDetector } from "./ProviderDetector";
import { ImportProgress } from "./ImportProgress";
import { ManualResultForm } from "./ManualResultForm";
import type { ScrapedPreview } from "@/lib/types";

export function ScrapeForm() {
  const [url, setUrl] = useState("");
  const [bib, setBib] = useState("");
  const [preview, setPreview] = useState<ScrapedPreview | null>(null);
  const [scraping, setScraping] = useState(false);
  const [manual, setManual] = useState(false);

  const save = useSaveParticipation();
  const importStream = useImportStream();

  const scrape = useCallback(async () => {
    setScraping(true);
    setManual(false);
    try {
      const result = await apiClient.scrape(url, bib || null);
      setPreview(result);
    } catch (e) {
      toast.error((e as Error).message);
      setManual(true);
      apiClient.reportPendingProvider(url).catch(() => {});
    } finally {
      setScraping(false);
    }
  }, [url, bib]);

  const persist = useCallback(
    async (data: Partial<ScrapedPreview>) => {
      try {
        await save.mutateAsync(data);
        toast.success("Résultat enregistré.");
        setPreview(null);
        // Import épreuve en arrière-plan (SSE) à partir de l'URL source.
        const eventUrl = data.source_url || url;
        if (eventUrl) importStream.start(eventUrl);
      } catch (e) {
        toast.error((e as Error).message);
      }
    },
    [save, url, importStream],
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-4 p-5">
          <div className="flex flex-col gap-1">
            <Label>URL de chronométrage</Label>
            <Input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://…"
            />
            <ProviderDetector url={url} />
          </div>
          <div className="flex items-end gap-3">
            <div className="flex flex-col gap-1">
              <Label>Dossard (optionnel)</Label>
              <Input value={bib} onChange={(e) => setBib(e.target.value)} className="w-32" />
            </div>
            <Button onClick={scrape} disabled={!url || scraping}>
              {scraping ? "Analyse…" : "Analyser"}
            </Button>
            <Button variant="outline" onClick={() => setManual((m) => !m)}>
              Saisie manuelle
            </Button>
          </div>
        </CardContent>
      </Card>

      {preview && !manual && (
        <Card>
          <CardContent className="space-y-4 p-5">
            <h3 className="font-semibold">Prévisualisation — vérifiez puis enregistrez</h3>
            <PreviewEditor preview={preview} onChange={setPreview} />
            <Button onClick={() => persist(preview)} disabled={save.isPending}>
              {save.isPending ? "Enregistrement…" : "Enregistrer"}
            </Button>
          </CardContent>
        </Card>
      )}

      {manual && (
        <Card>
          <CardContent className="space-y-4 p-5">
            <h3 className="font-semibold">Saisie manuelle</h3>
            <ManualResultForm defaultUrl={url} onSubmit={persist} submitting={save.isPending} />
          </CardContent>
        </Card>
      )}

      <ImportProgress state={importStream.state} />
    </div>
  );
}

/** Éditeur minimal des champs clés de la preview avant enregistrement. */
function PreviewEditor({
  preview,
  onChange,
}: {
  preview: ScrapedPreview;
  onChange: (p: ScrapedPreview) => void;
}) {
  const set = (k: keyof ScrapedPreview, v: string) => onChange({ ...preview, [k]: v });
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Labeled label="Prénom"><Input value={preview.athlete_firstname} onChange={(e) => set("athlete_firstname", e.target.value)} /></Labeled>
      <Labeled label="Nom"><Input value={preview.athlete_name} onChange={(e) => set("athlete_name", e.target.value)} /></Labeled>
      <Labeled label="Club"><Input value={preview.club} onChange={(e) => set("club", e.target.value)} /></Labeled>
      <Labeled label="Catégorie"><Input value={preview.category} onChange={(e) => set("category", e.target.value)} /></Labeled>
      <Labeled label="Épreuve"><Input value={preview.event_name} onChange={(e) => set("event_name", e.target.value)} /></Labeled>
      <Labeled label="Temps total"><Input value={preview.total_time} onChange={(e) => set("total_time", e.target.value)} /></Labeled>
    </div>
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <Label>{label}</Label>
      {children}
    </div>
  );
}
```

- [ ] **Step 2: Vérifier le typage**

Run: `cd frontend-v2 && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 3: Commit**

```bash
git add frontend-v2/components/scrape/ScrapeForm.tsx
git commit -m "feat(frontend-v2): ScrapeForm (preview → save → import SSE)"
```

---

### Task 26: Page `/ajouter`

**Files:**
- Create: `frontend-v2/app/ajouter/page.tsx`

- [ ] **Step 1: Écrire la page**

```tsx
import { ScrapeForm } from "@/components/scrape/ScrapeForm";

export default function AjouterPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Ajouter un résultat</h1>
      <p className="text-muted-foreground">
        Collez l'URL de chronométrage d'une épreuve. Le résultat de l'athlète est
        prévisualisé, puis tous les participants sont importés en arrière-plan.
      </p>
      <ScrapeForm />
    </div>
  );
}
```

- [ ] **Step 2: Vérifier le build**

Run: `cd frontend-v2 && npm run build`
Expected: build OK.

- [ ] **Step 3: Commit**

```bash
git add frontend-v2/app/ajouter/page.tsx
git commit -m "feat(frontend-v2): page /ajouter"
```

---

## PHASE 6 — Résultats + deep-links

### Task 27: ResultsFilters (filtres → searchParams)

**Files:**
- Create: `frontend-v2/components/results/ResultsFilters.tsx`
- Test: `frontend-v2/components/results/ResultsFilters.test.tsx`

- [ ] **Step 1: Écrire le test (échoue)**

On teste la construction de l'URL à partir des filtres via une fonction pure `buildResultsQuery`.

```tsx
import { describe, it, expect } from "vitest";
import { buildResultsQuery } from "./ResultsFilters";

describe("buildResultsQuery", () => {
  it("ignore les champs vides", () => {
    expect(buildResultsQuery({ name: "marie", event_type: "" })).toBe("name=marie");
  });
  it("encode plusieurs filtres", () => {
    const qs = buildResultsQuery({ name: "x", event_type: "triathlon-m", club: "nantais" });
    expect(qs).toContain("name=x");
    expect(qs).toContain("event_type=triathlon-m");
    expect(qs).toContain("club=nantais");
  });
  it("renvoie une chaîne vide si tout est vide", () => {
    expect(buildResultsQuery({})).toBe("");
  });
});
```

- [ ] **Step 2: Lancer le test (échoue)**

Run: `cd frontend-v2 && npx vitest run components/results/ResultsFilters.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implémenter `ResultsFilters.tsx`**

```tsx
"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EVENT_TYPE_OPTIONS } from "@/lib/constants";

export function buildResultsQuery(filters: Record<string, string | undefined>): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v && v !== "") params.set(k, v);
  });
  return params.toString();
}

export function ResultsFilters() {
  const router = useRouter();
  const sp = useSearchParams();
  const [name, setName] = useState(sp.get("name") ?? "");
  const [eventType, setEventType] = useState(sp.get("event_type") ?? "");
  const [dateFrom, setDateFrom] = useState(sp.get("date_from") ?? "");
  const [dateTo, setDateTo] = useState(sp.get("date_to") ?? "");

  function apply() {
    const qs = buildResultsQuery({
      name,
      event_type: eventType,
      date_from: dateFrom,
      date_to: dateTo,
    });
    router.push(`/resultats${qs ? `?${qs}` : ""}`);
  }

  function reset() {
    setName("");
    setEventType("");
    setDateFrom("");
    setDateTo("");
    router.push("/resultats");
  }

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-md border p-4">
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium">Nom</label>
        <Input value={name} onChange={(e) => setName(e.target.value)} className="w-48" />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium">Type</label>
        <select
          className="h-9 rounded-md border bg-background px-2"
          value={eventType}
          onChange={(e) => setEventType(e.target.value)}
        >
          <option value="">Tous</option>
          {EVENT_TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium">Du</label>
        <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium">Au</label>
        <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
      </div>
      <Button onClick={apply}>Filtrer</Button>
      <Button variant="ghost" onClick={reset}>Réinitialiser</Button>
    </div>
  );
}
```

- [ ] **Step 4: Lancer le test (passe)**

Run: `cd frontend-v2 && npx vitest run components/results/ResultsFilters.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/components/results/ResultsFilters.tsx frontend-v2/components/results/ResultsFilters.test.tsx
git commit -m "feat(frontend-v2): ResultsFilters (filtres → searchParams) (TDD)"
```

---

### Task 28: ResultsList (client, suppression) + page `/resultats`

**Files:**
- Create: `frontend-v2/components/results/ResultsList.tsx`
- Create: `frontend-v2/app/resultats/page.tsx`
- Create: `frontend-v2/app/resultats/loading.tsx`

- [ ] **Step 1: Implémenter `ResultsList.tsx`** (client : gère la suppression via mutation)

```tsx
"use client";
import { toast } from "sonner";
import { EventGroup } from "./EventGroup";
import { useDeleteParticipation } from "@/lib/queries/participations";
import { useRouter } from "next/navigation";
import type { Participation } from "@/lib/types";

export function ResultsList({ initial }: { initial: Participation[] }) {
  const del = useDeleteParticipation();
  const router = useRouter();

  async function onDelete(id: number) {
    try {
      await del.mutateAsync(id);
      toast.success("Résultat supprimé.");
      router.refresh();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return <EventGroup participations={initial} onDelete={onDelete} />;
}
```

- [ ] **Step 2: Écrire `app/resultats/page.tsx`** (RSC : lit `searchParams`, fetch serveur)

```tsx
import { apiServer } from "@/lib/api/server";
import { isClubFilterActive, TCN_CLUB_FILTER } from "@/lib/club-cookie";
import { ResultsFilters } from "@/components/results/ResultsFilters";
import { ResultsList } from "@/components/results/ResultsList";
import type { ParticipationFilters } from "@/lib/types";

export default async function ResultatsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const clubActive = await isClubFilterActive();

  const filters: ParticipationFilters = {
    name: sp.name,
    event_type: sp.event_type,
    event_name: sp.event_name,
    date_from: sp.date_from,
    date_to: sp.date_to,
    club: clubActive ? TCN_CLUB_FILTER : undefined,
    page_size: 500,
  };

  const participations = await apiServer.listParticipations(filters);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Résultats</h1>
      <ResultsFilters />
      <ResultsList initial={participations} />
    </div>
  );
}
```

- [ ] **Step 3: Écrire `app/resultats/loading.tsx`**

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-40" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}
```

- [ ] **Step 4: Vérifier le build**

Run: `cd frontend-v2 && npm run build`
Expected: build OK.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/components/results/ResultsList.tsx frontend-v2/app/resultats
git commit -m "feat(frontend-v2): page /resultats (RSC + filtres URL + suppression)"
```

---

### Task 29: Pages `/athletes/[id]` et `/courses/[id]`

**Files:**
- Create: `frontend-v2/app/athletes/[id]/page.tsx`
- Create: `frontend-v2/app/courses/[id]/page.tsx`

- [ ] **Step 1: Écrire `app/athletes/[id]/page.tsx`**

```tsx
import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { ResultCard } from "@/components/results/ResultCard";

export default async function AthletePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let data;
  try {
    data = await apiServer.getAthlete(Number(id));
  } catch {
    notFound();
  }
  const { athlete, participations } = data;
  const fullName = [athlete.prenom, athlete.nom].filter(Boolean).join(" ");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{fullName}</h1>
        <p className="text-muted-foreground">
          {athlete.club ?? "Sans club"} · {participations.length} résultat
          {participations.length > 1 ? "s" : ""}
        </p>
      </div>
      <div className="space-y-3">
        {participations.map((p) => (
          <ResultCard key={p.id} result={p} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Écrire `app/courses/[id]/page.tsx`**

```tsx
import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { ResultCard } from "@/components/results/ResultCard";
import { SportBadge } from "@/components/results/SportBadge";
import { formatDate } from "@/lib/utils/date";

export default async function CoursePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let data;
  try {
    data = await apiServer.getCourse(Number(id));
  } catch {
    notFound();
  }
  const { course, participations } = data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold">{course.name}</h1>
        <SportBadge type={course.event_type} />
        {course.event_date && (
          <span className="text-muted-foreground">{formatDate(course.event_date)}</span>
        )}
      </div>
      <p className="text-muted-foreground">
        {participations.length} participant{participations.length > 1 ? "s" : ""}
      </p>
      <div className="space-y-3">
        {participations.map((p) => (
          <ResultCard key={p.id} result={p} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Vérifier le build**

Run: `cd frontend-v2 && npm run build`
Expected: build OK.

- [ ] **Step 4: Commit**

```bash
git add frontend-v2/app/athletes frontend-v2/app/courses
git commit -m "feat(frontend-v2): fiches /athletes/[id] et /courses/[id] (RSC)"
```

---

## PHASE 7 — Club + Dashboard + feed

### Task 30: AthleteDialog

**Files:**
- Create: `frontend-v2/components/club/AthleteDialog.tsx`

- [ ] **Step 1: Implémenter `AthleteDialog.tsx`**

Modale affichant les participations d'un athlète (chargées à la volée via le client).

```tsx
"use client";
import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiClient } from "@/lib/api/client";
import { ResultCard } from "@/components/results/ResultCard";
import { Skeleton } from "@/components/ui/skeleton";
import type { AthleteDetail } from "@/lib/types";

export function AthleteDialog({
  athleteId,
  open,
  onOpenChange,
}: {
  athleteId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [data, setData] = useState<AthleteDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || athleteId == null) return;
    setLoading(true);
    setData(null);
    apiClient
      .getAthlete(athleteId)
      .then(setData)
      .finally(() => setLoading(false));
  }, [athleteId, open]);

  const name = data ? [data.athlete.prenom, data.athlete.nom].filter(Boolean).join(" ") : "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[80vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{name || "Athlète"}</DialogTitle>
        </DialogHeader>
        {loading && <Skeleton className="h-32 w-full" />}
        {data && (
          <div className="space-y-3">
            {data.participations.map((p) => (
              <ResultCard key={p.id} result={p} />
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Vérifier le typage**

Run: `cd frontend-v2 && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 3: Commit**

```bash
git add frontend-v2/components/club/AthleteDialog.tsx
git commit -m "feat(frontend-v2): AthleteDialog (modale participations)"
```

---

### Task 31: ClubStats + page `/club`

**Files:**
- Create: `frontend-v2/components/club/ClubStats.tsx`
- Create: `frontend-v2/app/club/page.tsx`

- [ ] **Step 1: Implémenter `ClubStats.tsx`**

Affiche les KPIs club + répartition par type/mois + récents. `stats` est fourni par le RSC parent.

```tsx
"use client";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { eventTypeLabel } from "@/lib/constants";
import { formatMonth } from "@/lib/utils/date";
import type { Stats } from "@/lib/types";

export function ClubStats({ stats }: { stats: Stats }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Kpi label="Résultats" value={stats.total} />
        <Kpi label="Athlètes" value={stats.athletes} />
        <Kpi label="Épreuves" value={stats.events} />
      </div>

      <Tabs defaultValue="type">
        <TabsList>
          <TabsTrigger value="type">Par type</TabsTrigger>
          <TabsTrigger value="month">Par mois</TabsTrigger>
        </TabsList>
        <TabsContent value="type">
          <DistributionList
            entries={Object.entries(stats.by_type)}
            labeller={(k) => eventTypeLabel(k)}
          />
        </TabsContent>
        <TabsContent value="month">
          <DistributionList
            entries={Object.entries(stats.by_month)}
            labeller={(k) => formatMonth(k)}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="text-3xl font-extrabold">{value}</div>
        <div className="text-sm text-muted-foreground">{label}</div>
      </CardContent>
    </Card>
  );
}

function DistributionList({
  entries,
  labeller,
}: {
  entries: [string, number][];
  labeller: (key: string) => string;
}) {
  const max = Math.max(1, ...entries.map(([, v]) => v));
  return (
    <div className="space-y-2 pt-3">
      {entries.map(([key, value]) => (
        <div key={key} className="flex items-center gap-3">
          <span className="w-40 shrink-0 text-sm">{labeller(key)}</span>
          <div className="h-3 flex-1 overflow-hidden rounded bg-muted">
            <div className="h-full bg-primary" style={{ width: `${(value / max) * 100}%` }} />
          </div>
          <span className="w-10 text-right text-sm font-medium">{value}</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Écrire `app/club/page.tsx`** (RSC : fetch stats, respecte le filtre club)

```tsx
import { apiServer } from "@/lib/api/server";
import { isClubFilterActive, TCN_CLUB_FILTER } from "@/lib/club-cookie";
import { ClubStats } from "@/components/club/ClubStats";

export default async function ClubPage() {
  const clubActive = await isClubFilterActive();
  const stats = await apiServer.getStats(clubActive ? TCN_CLUB_FILTER : undefined);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Statistiques du club</h1>
      <ClubStats stats={stats} />
    </div>
  );
}
```

- [ ] **Step 3: Vérifier le build**

Run: `cd frontend-v2 && npm run build`
Expected: build OK.

- [ ] **Step 4: Commit**

```bash
git add frontend-v2/components/club/ClubStats.tsx frontend-v2/app/club/page.tsx
git commit -m "feat(frontend-v2): page /club (stats + répartitions)"
```

---

### Task 32: Kpis + LiveFeed + page `/dashboard`

**Files:**
- Create: `frontend-v2/components/dashboard/Kpis.tsx`
- Create: `frontend-v2/components/dashboard/LiveFeed.tsx`
- Create: `frontend-v2/app/dashboard/page.tsx` (remplace le placeholder de la Task 18)

- [ ] **Step 1: Implémenter `Kpis.tsx`**

```tsx
import { Card, CardContent } from "@/components/ui/card";
import type { Stats } from "@/lib/types";

export function Kpis({ stats }: { stats: Stats }) {
  const items = [
    { label: "Résultats importés", value: stats.total },
    { label: "Athlètes", value: stats.athletes },
    { label: "Épreuves", value: stats.events },
  ];
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {items.map((it) => (
        <Card key={it.label}>
          <CardContent className="p-5">
            <div className="text-3xl font-extrabold">{it.value}</div>
            <div className="text-sm text-muted-foreground">{it.label}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Implémenter `LiveFeed.tsx`** (client, polling 15 s)

```tsx
"use client";
import { useLiveFeed } from "@/lib/queries/stats";
import { ResultCard } from "@/components/results/ResultCard";
import { Skeleton } from "@/components/ui/skeleton";

export function LiveFeed({ club }: { club?: string }) {
  const { data, isLoading } = useLiveFeed(club);

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (!data || data.length === 0) {
    return <p className="text-muted-foreground">Aucun résultat récent.</p>;
  }
  return (
    <div className="space-y-3">
      {data.map((p) => (
        <ResultCard key={p.id} result={p} />
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Écrire `app/dashboard/page.tsx`**

```tsx
import { apiServer } from "@/lib/api/server";
import { isClubFilterActive, TCN_CLUB_FILTER } from "@/lib/club-cookie";
import { Kpis } from "@/components/dashboard/Kpis";
import { LiveFeed } from "@/components/dashboard/LiveFeed";

export default async function DashboardPage() {
  const clubActive = await isClubFilterActive();
  const club = clubActive ? TCN_CLUB_FILTER : undefined;
  const stats = await apiServer.getStats(club);

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Tableau de bord</h1>
      <Kpis stats={stats} />
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Derniers résultats</h2>
        <LiveFeed club={club} />
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Vérifier le build**

Run: `cd frontend-v2 && npm run build`
Expected: build OK.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/components/dashboard frontend-v2/app/dashboard/page.tsx
git commit -m "feat(frontend-v2): page /dashboard (KPIs + LiveFeed polling)"
```

---

## PHASE 8 — Carte

### Task 33: MapView + page `/carte`

**Files:**
- Create: `frontend-v2/components/map/MapView.tsx`
- Create: `frontend-v2/app/carte/page.tsx`

- [ ] **Step 1: Implémenter `MapView.tsx`** (react-leaflet, client-only ; porté de `EventHeatmap.jsx`)

```tsx
"use client";
import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { apiClient } from "@/lib/api/client";
import { eventTypeLabel } from "@/lib/constants";
import { formatMonth } from "@/lib/utils/date";
import type { GeoEvent } from "@/lib/types";

// Corrige les chemins d'icônes cassés par les bundlers (icônes via CDN).
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

function FitBounds({ events }: { events: GeoEvent[] }) {
  const map = useMap();
  useEffect(() => {
    if (events.length === 0) return;
    const bounds = L.latLngBounds(events.map((e) => [e.lat, e.lon]));
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 9 });
  }, [events, map]);
  return null;
}

export function MapView({ club }: { club?: string }) {
  const [events, setEvents] = useState<GeoEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    apiClient
      .getEventsGeo(club)
      .then(setEvents)
      .catch(() => setError("Impossible de charger la carte"))
      .finally(() => setLoading(false));
  }, [club]);

  if (loading) return <p className="py-10 text-center text-muted-foreground">Géolocalisation des courses…</p>;
  if (error) return <p className="py-10 text-center text-destructive">{error}</p>;
  if (events.length === 0)
    return <p className="py-10 text-center text-muted-foreground">Aucune course géolocalisée.</p>;

  const maxCount = Math.max(...events.map((e) => e.count), 1);

  return (
    <MapContainer center={[47.2, -1.5]} zoom={7} scrollWheelZoom={false} className="h-[480px] w-full rounded-md">
      <TileLayer
        attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        maxZoom={13}
      />
      {events.map((ev, i) => {
        const radius = Math.max(10, Math.min(40, 10 + (ev.count / maxCount) * 30));
        const hasTCN = ev.tcn_count > 0;
        return (
          <CircleMarker
            key={`${ev.event_name}-${i}`}
            center={[ev.lat, ev.lon]}
            radius={radius}
            pathOptions={{
              fillColor: hasTCN ? "#3b82f6" : "#94a3b8",
              color: hasTCN ? "#1d4ed8" : "#64748b",
              weight: hasTCN ? 2 : 1,
              fillOpacity: 0.55,
            }}
          >
            <Popup>
              <div className="min-w-[180px]">
                <b>{ev.event_name}</b>
                {ev.event_type && <div className="text-muted-foreground">{eventTypeLabel(ev.event_type)}</div>}
                {ev.event_date && <div className="text-xs">{formatMonth(ev.event_date.slice(0, 7))}</div>}
                <div>
                  {ev.count} participant{ev.count > 1 ? "s" : ""}
                </div>
                {hasTCN && (
                  <div className="font-semibold text-blue-600">
                    {ev.tcn_count} membre{ev.tcn_count > 1 ? "s" : ""} TCN
                  </div>
                )}
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
      <FitBounds events={events} />
    </MapContainer>
  );
}
```

- [ ] **Step 2: Écrire `app/carte/page.tsx`** (charge MapView en `ssr:false`)

```tsx
"use client";
import dynamic from "next/dynamic";

const MapView = dynamic(() => import("@/components/map/MapView").then((m) => m.MapView), {
  ssr: false,
  loading: () => <p className="py-10 text-center text-muted-foreground">Chargement de la carte…</p>,
});

export default function CartePage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Carte des épreuves</h1>
      <MapView />
    </div>
  );
}
```

- [ ] **Step 3: Vérifier le build**

Run: `cd frontend-v2 && npm run build`
Expected: build OK (pas d'erreur d'hydratation Leaflet grâce à `ssr:false`).

- [ ] **Step 4: Commit**

```bash
git add frontend-v2/components/map/MapView.tsx frontend-v2/app/carte/page.tsx
git commit -m "feat(frontend-v2): page /carte (react-leaflet client-only)"
```

---

## PHASE 9 — Admin

### Task 34: PendingProvidersTable + page `/admin`

**Files:**
- Create: `frontend-v2/components/admin/PendingProvidersTable.tsx`
- Create: `frontend-v2/app/admin/page.tsx`

- [ ] **Step 1: Implémenter `PendingProvidersTable.tsx`**

```tsx
"use client";
import { toast } from "sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { usePendingProviders, useMarkProviderHandled } from "@/lib/queries/admin";
import { formatDate } from "@/lib/utils/date";

export function PendingProvidersTable() {
  const { data, isLoading } = usePendingProviders();
  const mark = useMarkProviderHandled();

  if (isLoading) return <p className="text-muted-foreground">Chargement…</p>;
  if (!data || data.length === 0) {
    return <p className="text-muted-foreground">Aucun fournisseur signalé.</p>;
  }

  async function handle(id: number) {
    try {
      await mark.mutateAsync(id);
      toast.success("Marqué comme traité.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>URL</TableHead>
          <TableHead>Indice</TableHead>
          <TableHead>Signalé le</TableHead>
          <TableHead></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map((p) => (
          <TableRow key={p.id}>
            <TableCell className="max-w-xs truncate">
              <a href={p.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                {p.url}
              </a>
            </TableCell>
            <TableCell>{p.provider_hint}</TableCell>
            <TableCell>{formatDate(p.reported_at)}</TableCell>
            <TableCell>
              <Button size="sm" variant="outline" onClick={() => handle(p.id)} disabled={mark.isPending}>
                Traité
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 2: Écrire `app/admin/page.tsx`**

```tsx
import { PendingProvidersTable } from "@/components/admin/PendingProvidersTable";

export default function AdminPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Administration</h1>
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Fournisseurs non supportés signalés</h2>
        <PendingProvidersTable />
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Vérifier le build**

Run: `cd frontend-v2 && npm run build`
Expected: build OK.

- [ ] **Step 4: Commit**

```bash
git add frontend-v2/components/admin/PendingProvidersTable.tsx frontend-v2/app/admin/page.tsx
git commit -m "feat(frontend-v2): page /admin (fournisseurs signalés)"
```

---

## PHASE 10 — Finitions, vérification & déploiement

### Task 35: Suite de tests complète + lint

**Files:** (aucun nouveau ; vérification)

- [ ] **Step 1: Lancer toute la suite de tests**

Run: `cd frontend-v2 && npm test`
Expected: PASS pour tous les fichiers `*.test.ts(x)` (club, date, splits, time, sse, SportBadge, ResultCard, ResultsFilters).

- [ ] **Step 2: Lint + typage**

Run: `cd frontend-v2 && npm run lint && npx tsc --noEmit`
Expected: aucune erreur. Corriger les avertissements bloquants.

- [ ] **Step 3: Build de production**

Run: `cd frontend-v2 && npm run build`
Expected: build OK ; toutes les routes (`/dashboard`, `/resultats`, `/athletes/[id]`, `/courses/[id]`, `/club`, `/carte`, `/ajouter`, `/admin`) compilées.

- [ ] **Step 4: Commit** (si des corrections ont été nécessaires)

```bash
git add -A frontend-v2
git commit -m "test(frontend-v2): suite verte + lint + build prod"
```

---

### Task 36: Vérification manuelle end-to-end

**Files:** (aucun ; procédure documentée)

- [ ] **Step 1: Démarrer le backend-v2**

Run (terminal 1, depuis `backend-v2/`, venv activé) :

```bash
uvicorn app.main:app --reload --port 8001
```

Expected: API up sur `http://localhost:8001`, `/docs` accessible.

- [ ] **Step 2: Démarrer le frontend**

Run (terminal 2, depuis `frontend-v2/`) :

```bash
npm run dev
```

Expected: Next sur `http://localhost:3000`, rewrites `/api/*` → 8001.

- [ ] **Step 3: Parcours manuel** (cocher chaque étape)

Vérifier dans le navigateur :
- `/ajouter` → saisie manuelle d'un résultat → toast succès.
- Le résultat apparaît dans `/resultats` (regroupé par épreuve).
- Clic sur le nom → `/athletes/[id]` affiche la fiche + splits adaptatifs.
- Clic sur l'épreuve → `/courses/[id]` affiche les participants.
- `/club` montre les KPIs et répartitions.
- `/dashboard` montre les KPIs + le feed.
- `/carte` affiche la carte (si des épreuves sont géocodées).
- Toggle « Membres TCN » dans le header → les listes/stats se rechargent filtrées.
- Switch thème clair/sombre fonctionne.

- [ ] **Step 4: (Si écart constaté)** ouvrir un debug ciblé via superpowers:systematic-debugging, corriger, recommiter.

---

### Task 37: README + config Vercel + dépréciation frontend

**Files:**
- Create: `frontend-v2/README.md`
- Modify: `frontend/README.md` (ou en-tête `App.jsx`) pour signaler la dépréciation
- Modify: `AGENTS.md` (section frontend → pointer vers frontend-v2)

- [ ] **Step 1: Écrire `frontend-v2/README.md`**

```markdown
# frontend-v2 — TCN Résultats (Next.js)

Frontend Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui consommant
l'API backend-v2 `/api/v1`.

## Développement

```bash
cp .env.local.example .env.local   # BACKEND_URL / API_URL → backend-v2
npm install
npm run dev                        # http://localhost:3000 (rewrites /api → :8001)
```

Backend requis : `uvicorn app.main:app --port 8001` depuis `backend-v2/`.

## Scripts

- `npm run dev` — serveur de dev
- `npm run build` — build production (typage strict + RSC)
- `npm test` — tests Vitest + RTL
- `npm run lint` — ESLint

## Déploiement (Vercel)

- Projet Vercel pointant sur `frontend-v2/`.
- Variables d'environnement :
  - `BACKEND_URL` — URL interne du backend Render (rewrites client).
  - `API_URL` — URL du backend pour les Server Components.
- CORS : ajouter le domaine Vercel à `CORS_ORIGINS` du backend-v2.
```

- [ ] **Step 2: Marquer `frontend/` comme déprécié**

Ajouter en tête de `frontend/README.md` (ou créer le fichier) la ligne :

```markdown
> ⚠️ **Déprécié** — remplacé par `frontend-v2/` (Next.js). Conservé pour référence.
```

- [ ] **Step 3: Mettre à jour `AGENTS.md`**

Dans la section « Architecture frontend » d'`AGENTS.md`, ajouter une note pointant vers `frontend-v2/` comme frontend actif (Next.js) et marquant `frontend/` comme déprécié. (Édition ciblée, garder le reste.)

- [ ] **Step 4: Commit**

```bash
git add frontend-v2/README.md frontend/README.md AGENTS.md
git commit -m "docs(frontend-v2): README + config Vercel + dépréciation frontend"
```

---

### Task 38: Finalisation de la branche

- [ ] **Step 1: Vérification finale**

Run: `cd frontend-v2 && npm test && npm run lint && npm run build`
Expected: tout vert.

- [ ] **Step 2: Intégrer le travail**

Utiliser superpowers:finishing-a-development-branch pour décider merge / PR / cleanup.

---

## Self-Review (effectuée)

**1. Couverture du spec :**
- TS strict, types miroir Pydantic → Task 4. ✓
- Rendu hybride RSC + TanStack Query → Tasks 11/14/15 + pages RSC. ✓
- Parité : Ajouter (scrape+SSE+manuel) → Tasks 22-26 ; Résultats + deep-links → Tasks 27-29 ; Club+Dashboard+feed → Tasks 30-32 ; Carte → Task 33 ; Admin → Task 34. ✓
- Recherche globale `Command` → Task 17 ; filtre club cookie → Task 16 ; switch thème → Task 16. ✓
- Filtres = searchParams → Tasks 27/28. ✓
- SSE porté en AsyncGenerator → Task 12 ; ImportProgress → Task 23. ✓
- Splits adaptatifs depuis `p.splits` → Task 8 + Task 20. ✓
- Leaflet `ssr:false` → Task 33. ✓
- Tests Vitest (splits, filtres, SSE, isTCN) → Tasks 6/8/12/27. ✓
- Déploiement Vercel + CORS + dépréciation → Task 37. ✓
- i18n FR → tout le contenu UI en français. ✓

**2. Placeholders :** aucun « TBD/TODO » ; code complet dans chaque step.

**3. Cohérence des types :** `splitSegments(eventType, splits)` (Task 8) utilisé tel quel dans ResultCard (Task 20) ; clés splits `swim/t1/bike/t2/run` cohérentes avec `mapping.py`. `apiClient`/`apiServer` méthodes nommées identiquement entre définition (Tasks 10/11) et usages (pages/hooks). `ImportState` défini en Task 13, consommé en Task 23. `buildResultsQuery` défini et testé en Task 27.

**Note d'exécution :** sur Next 15 / React 19, ajuster les annotations `Promise<...>` de `params`/`searchParams` si la version installée diffère (create-next-app génère la bonne signature — suivre ce qu'il produit). Vérifier `npx tsc --noEmit` après chaque page.
