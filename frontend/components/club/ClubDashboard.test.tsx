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

  // Roster (issue #128, extension) : le décompte de podiums d'un athlète se
  // décompose par scope (général / catégorie / genre) avec l'icône et le
  // tooltip natif du composant PodiumsList — un athlète 1er scratch et 1er
  // catégorie n'agrège plus en « 2 podiums » sans nuance.
  it("roster : décompose les podiums d'un athlète par scope, avec tooltip", () => {
    const parts: Participation[] = [
      // Ath 1 : podium général x1
      part({ id: 1, rank_overall: 2 }),
      // Ath 1 (même id) : podium catégorie x1 sur une autre course
      part({
        id: 2,
        athlete: { id: 1, nom: "N", prenom: "P", gender: "F", club: "TCN" },
        rank_overall: 30,
        rank_category: 1,
      }),
      // Ath 1 : podium genre x1 sur une troisième course
      part({
        id: 3,
        athlete: { id: 1, nom: "N", prenom: "P", gender: "F", club: "TCN" },
        rank_gender: 3,
      }),
    ];
    render(<ClubDashboard stats={STATS} participations={parts} />);
    expect(screen.getByLabelText("1 podium général")).toBeInTheDocument();
    expect(screen.getByLabelText("1 podium de catégorie")).toBeInTheDocument();
    expect(screen.getByLabelText("1 podium de genre")).toBeInTheDocument();
  });

  // Cas mesuré (Hadrien à Mesquer, athlète 8565) : une seule participation
  // podium sur les trois dimensions à la fois — 2e scratch, 1er catégorie,
  // 2e genre. Les trois compteurs de scope sont incrémentés indépendamment.
  it("roster : une participation podium sur plusieurs scopes incrémente chaque compteur", () => {
    const parts: Participation[] = [
      part({ id: 1, rank_overall: 2, rank_category: 1, rank_gender: 2 }),
    ];
    render(<ClubDashboard stats={STATS} participations={parts} />);
    expect(screen.getByLabelText("1 podium général")).toBeInTheDocument();
    expect(screen.getByLabelText("1 podium de catégorie")).toBeInTheDocument();
    expect(screen.getByLabelText("1 podium de genre")).toBeInTheDocument();
  });

  it("roster : aucun badge scope pour un athlète sans podium", () => {
    const parts: Participation[] = [
      part({
        id: 10,
        athlete: { id: 10, nom: "Z", prenom: "Q", gender: "M", club: "TCN" },
        rank_overall: 50,
      }),
    ];
    render(<ClubDashboard stats={STATS} participations={parts} />);
    expect(screen.queryByLabelText(/podium général/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/podium de catégorie/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/podium de genre/)).not.toBeInTheDocument();
  });
});
