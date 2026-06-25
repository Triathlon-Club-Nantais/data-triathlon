# Page Résultats : liste cliquable vers la fiche course — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer l'accordéon de `/resultats` par une table de lignes-liens au style « page athlète » (TCN Design System) qui navigue vers `/courses/[id]`, et retirer la suppression de résultat de cette page.

**Architecture :** Réécriture du seul composant Client `components/results/EventList.tsx`. On conserve sa logique de données (`useInfiniteEvents`, scroll infini, tri via l'URL) et on remplace son rendu shadcn `Accordion` par une `Card` TCN enveloppant des lignes `<Link className="tcn-rowlink">`. Le composant `EventParticipations` (monté uniquement par l'accordéon) devient orphelin et est supprimé.

**Tech Stack :** Next.js 16 (App Router), TypeScript strict, React Query, composants `@/components/tcn` (`Card`, `Badge`, `FormatChip`), helpers `eventTypeLabel` / `formatToken` / `formatDate`, classe CSS `tcn-rowlink`. Tests Vitest + RTL.

## Global Constraints

- **Langue** : UI, commentaires et textes en **français** (avec accents).
- **Frontend uniquement** : aucune modification backend, API, ni de la fiche `/courses/[id]`.
- **TS strict + RSC** : `npm run build` doit passer ; `EventList` reste un Client Component (`"use client"`).
- **Suppression d'un résultat** : retirée de cette page, **non** portée sur `/courses/[id]` ni `RaceFinishers`. Le hook `useDeleteParticipation` (défini dans `lib/queries/participations.ts`) **reste en place** (réutilisable par la future page d'admin) ; seul son usage dans `EventList` est retiré.
- **Ne pas supprimer** `components/results/SportBadge.tsx` (encore utilisé par `ResultCard` et `ClubDashboard`) ni `ResultCard.tsx`.
- Commits : Conventional Commits, terminés par la ligne `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Toutes les commandes frontend s'exécutent depuis `frontend/`.

---

### Task 1: Réécrire `EventList` en table de lignes-liens TCN

Cœur du livrable. On met d'abord à jour le test pour décrire le nouveau rendu (un lien par épreuve vers `/courses/[id]`, plus d'accordéon, plus de suppression), on le voit échouer, puis on réécrit le composant.

**Files:**
- Modify: `frontend/components/results/EventList.tsx` (réécriture complète)
- Test: `frontend/components/results/EventList.test.tsx` (réécriture des assertions)

**Interfaces:**
- Consomme (inchangé) :
  - `useInfiniteEvents(filters: ParticipationFilters, initial?: EventPage)` → `{ data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading }` (depuis `@/lib/queries/events`).
  - `EventOut` = `{ id: number; event_name: string; event_date: string | null; event_type: string; is_relay: boolean; distance_km?: number | null; total: number; tcn_count: number }` (depuis `@/lib/types`).
  - `Card` (prop `padding`, `style`), `Badge` (props `variant`, `count`), `FormatChip` (depuis `@/components/tcn`).
  - `eventTypeLabel(type)` (`@/lib/constants`), `formatToken(eventType, distanceKm)` (`@/lib/utils/format`), `formatDate(date)` (`@/lib/utils/date`).
- Produit : composant `EventList({ filters, initial })` exporté, signature **inchangée** (consommé par `app/resultats/page.tsx`, aucune modif requise côté page).

- [ ] **Step 1: Réécrire le test pour le nouveau rendu (échec attendu)**

Remplacer **tout** le contenu de `frontend/components/results/EventList.test.tsx` par :

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const eventsMock = vi.hoisted(() => ({
  value: {} as ReturnType<typeof Object>,
}));

vi.mock("@/lib/queries/events", () => ({
  EVENTS_PAGE_SIZE: 30,
  useInfiniteEvents: () => eventsMock.value,
}));

import { EventList } from "./EventList";

function setEvents(value: unknown) {
  eventsMock.value = value as never;
}

function renderList(filters = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <EventList filters={filters} />
    </QueryClientProvider>,
  );
}

describe("EventList", () => {
  it("rend chaque épreuve comme un lien vers sa fiche course", () => {
    setEvents({
      data: {
        pages: [
          {
            items: [
              {
                id: 14,
                event_name: "Tri de Nantes",
                event_type: "triathlon-m",
                event_date: "2026-05-16",
                is_relay: false,
                total: 42,
                tcn_count: 3,
              },
            ],
            total_events: 1,
            total_participations: 42,
          },
        ],
      },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });

    renderList();

    const link = screen.getByRole("link", { name: /Tri de Nantes/ });
    expect(link).toHaveAttribute("href", "/courses/14");
    // Métadonnées conservées dans la ligne.
    expect(link).toHaveTextContent("Triathlon M");
    expect(link).toHaveTextContent("42 résultats");
    expect(link).toHaveTextContent("3");
  });

  it("n'affiche plus de bouton de suppression ni d'accordéon", () => {
    setEvents({
      data: {
        pages: [
          {
            items: [
              {
                id: 14,
                event_name: "Tri de Nantes",
                event_type: "triathlon-m",
                event_date: "2026-05-16",
                is_relay: false,
                total: 42,
                tcn_count: 3,
              },
            ],
            total_events: 1,
            total_participations: 42,
          },
        ],
      },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });

    renderList();

    expect(screen.queryByRole("button", { name: /supprimer/i })).toBeNull();
  });

  it("affiche un état vide quand aucune épreuve", () => {
    setEvents({
      data: { pages: [{ items: [], total_events: 0, total_participations: 0 }] },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });

    renderList();
    expect(screen.getByText("Aucun résultat")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `npm test -- EventList`
Expected: FAIL — le rendu actuel (accordéon) n'expose pas de `link` « Tri de Nantes » avec `href="/courses/14"`.

- [ ] **Step 3: Réécrire `EventList.tsx`**

Remplacer **tout** le contenu de `frontend/components/results/EventList.tsx` par :

```tsx
"use client";
import { useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, Badge, FormatChip } from "@/components/tcn";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useInfiniteEvents } from "@/lib/queries/events";
import { eventTypeLabel } from "@/lib/constants";
import { formatToken } from "@/lib/utils/format";
import { formatDate } from "@/lib/utils/date";
import type { EventPage, ParticipationFilters } from "@/lib/types";

const SORT_OPTIONS = [
  { value: "date_desc", label: "Date (récent)" },
  { value: "date_asc", label: "Date (ancien)" },
  { value: "name", label: "Nom" },
];

// Date | Épreuve | Type | Format | Résultats | TCN | →
const COLS = "120px 1fr 150px 90px 110px 90px 28px";

export function EventList({
  filters,
  initial,
}: {
  filters: ParticipationFilters;
  initial?: EventPage;
}) {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } = useInfiniteEvents(
    filters,
    initial,
  );
  const router = useRouter();
  const sp = useSearchParams();
  const sentinel = useRef<HTMLDivElement | null>(null);

  const events = data?.pages.flatMap((p) => p.items) ?? [];

  // Scroll infini : charge la page suivante quand la sentinelle entre dans le viewport.
  useEffect(() => {
    const el = sentinel.current;
    if (!el || !hasNextPage) return;
    const io = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting && !isFetchingNextPage) fetchNextPage();
    });
    io.observe(el);
    return () => io.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  function setSort(value: string) {
    const params = new URLSearchParams(sp.toString());
    params.set("sort", value);
    router.push(`/resultats?${params.toString()}`);
  }

  const currentSort = sp.get("sort") ?? "date_desc";

  if (!isLoading && events.length === 0) {
    return (
      <EmptyState
        title="Aucun résultat"
        description="Importez une épreuve depuis une URL de chronométrage pour voir apparaître les résultats ici."
      />
    );
  }

  return (
    <Card padding={0} style={{ overflow: "hidden" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "20px 26px 16px",
        }}
      >
        <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)" }}>
          Toutes les épreuves
        </div>
        <Select value={currentSort} onValueChange={(v) => setSort(v as string)}>
          <SelectTrigger className="h-9 w-44">
            <SelectValue>
              {(v) => SORT_OPTIONS.find((o) => o.value === v)?.label ?? "Trier"}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: COLS,
          gap: "0 18px",
          padding: "0 26px 12px",
          fontSize: 12,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: ".04em",
          color: "var(--tcn-text-faint)",
          borderBottom: "1px solid var(--tcn-border)",
        }}
      >
        <div>Date</div>
        <div>Épreuve</div>
        <div>Type</div>
        <div>Format</div>
        <div>Résultats</div>
        <div>TCN</div>
        <div></div>
      </div>

      {events.map((ev) => (
        <Link
          key={ev.id}
          href={`/courses/${ev.id}`}
          className="tcn-rowlink"
          style={{
            display: "grid",
            gridTemplateColumns: COLS,
            gap: "0 18px",
            alignItems: "center",
            padding: "15px 26px",
            borderBottom: "1px solid var(--tcn-border-faint)",
          }}
        >
          <div style={{ fontSize: 14, color: "var(--tcn-text-muted)", fontWeight: 600 }}>
            {formatDate(ev.event_date)}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
            <span style={{ fontSize: 15, color: "var(--tcn-ink)", fontWeight: 700 }}>{ev.event_name}</span>
            {ev.is_relay && <Badge variant="orange">Relais</Badge>}
          </div>
          <div style={{ fontSize: 14, color: "var(--tcn-text-body)" }}>{eventTypeLabel(ev.event_type)}</div>
          <div>
            <FormatChip>{formatToken(ev.event_type, ev.distance_km)}</FormatChip>
          </div>
          <div style={{ fontSize: 14, color: "var(--tcn-text-body)" }}>
            {ev.total} résultat{ev.total > 1 ? "s" : ""}
          </div>
          <div>
            {ev.tcn_count > 0 ? (
              <Badge count>{ev.tcn_count}</Badge>
            ) : (
              <span style={{ color: "var(--tcn-text-faint)" }}>—</span>
            )}
          </div>
          <div style={{ textAlign: "right", color: "var(--tcn-text-disabled)", fontSize: 16 }}>→</div>
        </Link>
      ))}

      <div ref={sentinel} aria-hidden />
      {isFetchingNextPage && (
        <p style={{ padding: 16, textAlign: "center", fontSize: 14, color: "var(--tcn-text-faint)" }}>
          Chargement…
        </p>
      )}
    </Card>
  );
}
```

Notes pour l'implémenteur :
- On a **supprimé** les imports `Accordion*`, `SportBadge`, `EventParticipations`, `useQueryClient`, `useDeleteParticipation`, `toast`, et la fonction `onDelete` : plus aucune participation n'est rendue ici.
- `Badge variant="orange"` rend le chip « Relais » ; `Badge count` rend le compteur TCN rond.
- Le tri (`Select`) migre dans l'entête de la `Card` (à droite), comme la fiche athlète.

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `npm test -- EventList`
Expected: PASS (3 tests verts).

- [ ] **Step 5: Vérifier lint + build (TS strict)**

Run: `npm run lint && npm run build`
Expected: 0 erreur ESLint ; build prod OK. En particulier, aucune erreur « unused import » résiduelle dans `EventList.tsx`.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/results/EventList.tsx frontend/components/results/EventList.test.tsx
git commit -m "$(printf 'feat(frontend): page résultats en table de liens vers la fiche course\n\nRemplace l\\47accordéon par une Card TCN de lignes tcn-rowlink (style page\nathlète) vers /courses/[id]. Retire le rendu inline des participations et\nla suppression de résultat de cette page (refs #8).\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 2: Supprimer le composant orphelin `EventParticipations`

Après la Task 1, `EventParticipations` n'est plus monté nulle part. On le supprime pour ne pas laisser de code mort.

**Files:**
- Delete: `frontend/components/results/EventParticipations.tsx`

**Interfaces:**
- Consomme : néant (cleanup pur).
- Produit : néant.

- [ ] **Step 1: Confirmer l'absence d'autre importateur**

Run: `cd frontend && grep -rln "EventParticipations" --include="*.tsx" --include="*.ts" . | grep -v node_modules`
Expected: une seule ligne — `components/results/EventParticipations.tsx` (le fichier lui-même). Si un autre fichier apparaît, **stop** : ne pas supprimer, investiguer cet usage.

- [ ] **Step 2: Supprimer le fichier**

Run: `cd frontend && git rm components/results/EventParticipations.tsx`
Expected: le fichier est retiré de l'index.

- [ ] **Step 3: Vérifier la suite de tests + build complets**

Run: `cd frontend && npm test && npm run build`
Expected: tous les tests Vitest verts ; build prod OK (aucune référence cassée à `EventParticipations`).

- [ ] **Step 4: Commit**

```bash
git commit -m "$(printf 'refactor(frontend): supprime EventParticipations devenu orphelin\n\nPlus monté depuis le passage de la page résultats en liste de liens.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Self-Review

**Couverture de la spec** (`docs/superpowers/specs/2026-06-24-resultats-liste-cliquable-design.md`) :
- Suppression de l'accordéon + `EventParticipations` → Task 1 (Step 3) + Task 2. ✅
- Lignes-liens style page athlète (`Card`, `tcn-rowlink`, colonnes Date/Épreuve/Type/Format/Résultats/TCN/→, badge Relais) → Task 1 (Step 3). ✅
- Conservation tri / scroll infini / `EmptyState` / état de chargement → conservés dans le code de la Task 1. ✅
- Suppression du delete inline retirée de cette page, hook `useDeleteParticipation` conservé pour la future page admin → Task 1 + Global Constraints. ✅
- `SportBadge` / `ResultCard` non touchés → Global Constraints. ✅
- Tests mis à jour (lien vers `/courses/[id]`, plus d'accordéon, plus de suppression, EmptyState) → Task 1 (Step 1). ✅
- Aucune modif backend / API / fiche course → Global Constraints. ✅

**Scan placeholders :** aucun TBD/TODO ; tout le code est fourni intégralement (test + composant).

**Cohérence des types :** `EventList({ filters, initial })` inchangé (consommé tel quel par `app/resultats/page.tsx`). `EventOut` utilisé conformément à `lib/types.ts`. Props `Card`/`Badge`/`FormatChip` conformes aux composants `@/components/tcn`.

## Execution Handoff

Plan complet et sauvegardé dans `docs/superpowers/plans/2026-06-25-resultats-liste-cliquable.md`. Deux options d'exécution :

1. **Subagent-Driven (recommandé)** — un subagent neuf par tâche, revue entre les tâches, itération rapide.
2. **Inline Execution** — exécution des tâches dans cette session via executing-plans, par lots avec points de contrôle.
