import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { Participation, Stats } from "@/lib/types";

// Charts et badges internes se contentent d'un DOM inerte — on ne teste ici
// que la liste des podiums selon le rankType passé en prop.
vi.mock("@/components/charts/BarList", () => ({
  BarList: () => <div data-testid="barlist" />,
}));
vi.mock("@/components/charts/MonthlyTrend", () => ({
  MonthlyTrend: () => <div data-testid="monthly" />,
}));

import { ClubDashboard } from "./ClubDashboard";

const STATS: Stats = { total: 0, athletes: 0, events: 0, by_type: {}, by_month: {} };

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

describe("ClubDashboard — filtrage podiums selon rankType (#104)", () => {
  // `ClubDashboard` rend aussi la section « Résultats récents » qui contient
  // ses propres badges de scope via `ResultCard`. On restreint donc chaque
  // assertion à la carte « Podiums & performances » via son titre.
  function podiumsSection(): HTMLElement {
    const title = screen.getByText("Podiums & performances");
    // Le titre vit dans le CardHeader, la liste dans le CardContent du même
    // parent (Card). On remonte au container commun.
    const card = title.closest("[data-slot='card']") as HTMLElement | null;
    if (!card) throw new Error("Section podiums introuvable");
    return card;
  }

  const PARTS = [
    part({ id: 1, rank_overall: 30, rank_category: 1 }), // podium cat seul
    part({ id: 2, rank_overall: 2 }), // podium scratch seul
    part({ id: 3, rank_gender: 1 }), // podium genre seul
  ];

  it("mode scratch : n'affiche que les badges « Général » dans la liste des podiums", () => {
    render(<ClubDashboard stats={STATS} participations={PARTS} rankType="scratch" />);
    const section = within(podiumsSection());
    expect(section.getAllByText("Général").length).toBeGreaterThanOrEqual(1);
    expect(section.queryAllByText("Catégorie")).toHaveLength(0);
    expect(section.queryAllByText("Genre")).toHaveLength(0);
  });

  it("mode category : n'affiche que les badges « Catégorie » dans la liste des podiums", () => {
    render(<ClubDashboard stats={STATS} participations={PARTS} rankType="category" />);
    const section = within(podiumsSection());
    expect(section.getAllByText("Catégorie").length).toBeGreaterThanOrEqual(1);
    expect(section.queryAllByText("Général")).toHaveLength(0);
    expect(section.queryAllByText("Genre")).toHaveLength(0);
  });

  it("mode all : montre le mélange des trois scopes dans la liste des podiums (comportement historique)", () => {
    render(<ClubDashboard stats={STATS} participations={PARTS} rankType="all" />);
    const section = within(podiumsSection());
    expect(section.getAllByText("Général").length).toBeGreaterThanOrEqual(1);
    expect(section.getAllByText("Catégorie").length).toBeGreaterThanOrEqual(1);
    expect(section.getAllByText("Genre").length).toBeGreaterThanOrEqual(1);
  });

  it("mode gender : ne montre que les podiums genre (F et H mélangés)", () => {
    render(<ClubDashboard stats={STATS} participations={PARTS} rankType="gender" />);
    const section = within(podiumsSection());
    expect(section.getAllByText("Genre").length).toBeGreaterThanOrEqual(1);
    expect(section.queryAllByText("Général")).toHaveLength(0);
    expect(section.queryAllByText("Catégorie")).toHaveLength(0);
  });
});
