import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Participation, Stats } from "@/lib/types";

// Charts et hooks Next.js : stubs neutres.
vi.mock("@/components/charts/BarList", () => ({
  BarList: () => <div data-testid="barlist" />,
}));
vi.mock("@/components/charts/MonthlyTrend", () => ({
  MonthlyTrend: () => <div data-testid="monthly" />,
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

import { ClubDashboard } from "./ClubDashboard";

const STATS: Stats = { total: 0, athletes: 0, events: 0, by_type: {}, by_month: {}, recent: [] };

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: over.athlete ?? { id: over.id, nom: "N", prenom: "P", gender: "F", club: "TCN" },
    course: over.course ?? {
      id: over.id,
      name: `Course ${over.id}`,
      event_date: "2026-05-10",
      event_type: "triathlon-m",
      provider: "manuel",
      source_url: "",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: null,
    bib_number: null,
    rank_overall: over.rank_overall ?? null,
    rank_category: over.rank_category ?? null,
    rank_gender: over.rank_gender ?? null,
    total_time: "01:59:00",
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: "2026-05-11T10:00:00Z",
  };
}

// Le filtrage détaillé par mode vit désormais dans PodiumsList.test.tsx : ce
// composant client lit `?rank=…` et recalcule localement (issue #132).
// Ce test se limite au smoke : la section podiums est bien montée et affiche
// les KPI de synthèse.
describe("ClubDashboard — smoke", () => {
  it("rend les 4 KPI de synthèse (Résultats / Athlètes / Épreuves / Podiums)", () => {
    render(
      <ClubDashboard
        stats={STATS}
        participations={[part({ id: 1, rank_overall: 2 })]}
      />,
    );
    expect(screen.getByText("Résultats")).toBeInTheDocument();
    expect(screen.getByText("Athlètes")).toBeInTheDocument();
    expect(screen.getByText("Épreuves")).toBeInTheDocument();
    expect(screen.getByText("Podiums")).toBeInTheDocument();
  });

  it("empty state quand aucune participation", () => {
    render(<ClubDashboard stats={STATS} participations={[]} />);
    expect(screen.getByText("Aucun résultat de club")).toBeInTheDocument();
  });
});
