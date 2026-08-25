import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Participation } from "@/lib/types";

let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

import { ClubPodiumKpi } from "./ClubPodiumKpi";

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: over.athlete ?? { id: over.id, nom: "N", prenom: "P", gender: "F", club: "TCN" },
    course: over.course ?? {
      id: over.id,
      name: `C${over.id}`,
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
    total_time: "01:00:00",
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
  };
}

// Fixture divergente : 1 podium scratch, 1 podium catégorie, 1 podium genre.
// - En scratch → 1 podium.
// - En category → 1 podium.
// - En gender → 1 podium.
// - En all → 3 podiums (chaque participation touche un scope différent).
const PARTS: Participation[] = [
  part({ id: 1, rank_overall: 2 }),
  part({ id: 2, rank_category: 3 }),
  part({ id: 3, rank_gender: 1 }),
];

describe("ClubPodiumKpi — recalcul selon ?rank= (#104, #132)", () => {
  it("sans ?rank= (défaut scratch) : 1 podium", () => {
    searchParams = new URLSearchParams();
    render(<ClubPodiumKpi participations={PARTS} />);
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("Podiums")).toBeInTheDocument();
  });

  it("?rank=category : 1 podium", () => {
    searchParams = new URLSearchParams("rank=category");
    render(<ClubPodiumKpi participations={PARTS} />);
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("?rank=gender : 1 podium", () => {
    searchParams = new URLSearchParams("rank=gender");
    render(<ClubPodiumKpi participations={PARTS} />);
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("?rank=all : 3 podiums (min-des-trois, chaque participation compte)", () => {
    searchParams = new URLSearchParams("rank=all");
    render(<ClubPodiumKpi participations={PARTS} />);
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("?rank=foo (valeur inconnue) : retombe sur scratch", () => {
    searchParams = new URLSearchParams("rank=foo");
    render(<ClubPodiumKpi participations={PARTS} />);
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  // #488 (PROF-3) : le KPI et le roster comptent les podiums différemment et
  // les deux sont justes. Faute de le dire, basculer le toggle faisait bouger
  // un nombre et pas l'autre. La portée voyage donc avec le chiffre.
  it("nomme la portée du décompte, mode par mode (PROF-3, #488)", () => {
    searchParams = new URLSearchParams();
    const { unmount } = render(<ClubPodiumKpi participations={PARTS} />);
    expect(screen.getByText("général")).toBeInTheDocument();
    unmount();

    searchParams = new URLSearchParams("rank=category");
    const b = render(<ClubPodiumKpi participations={PARTS} />);
    expect(screen.getByText("catégorie")).toBeInTheDocument();
    b.unmount();

    searchParams = new URLSearchParams("rank=gender");
    const c = render(<ClubPodiumKpi participations={PARTS} />);
    expect(screen.getByText("genre")).toBeInTheDocument();
    c.unmount();

    searchParams = new URLSearchParams("rank=all");
    render(<ClubPodiumKpi participations={PARTS} />);
    expect(screen.getByText("général, genre ou catégorie")).toBeInTheDocument();
  });
});
