import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Participation } from "@/lib/types";

let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

import { StatCardsRank } from "./StatCardsRank";

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: over.athlete ?? { id: 1, nom: "N", prenom: "P", gender: "F", club: "TCN" },
    course: over.course ?? {
      id: 10,
      name: "Course",
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
    created_at: null,
  };
}

// Fixture divergente : min-des-trois vs scratch seul divergent — 1 victoire
// en catégorie qui n'existe pas en scratch. Permet de vérifier que le mode
// courant est bien lu depuis l'URL et non un défaut figé.
const PARTS: Participation[] = [
  part({ id: 1, rank_overall: 100, rank_category: 1, rank_gender: 50 }),
  part({ id: 2, rank_overall: 2 }),
];

describe("StatCardsRank — lecture URL et recalcul local", () => {
  it("sans ?rank= : mode scratch (défaut) — compte sur rank_overall", () => {
    searchParams = new URLSearchParams();
    render(<StatCardsRank participations={PARTS} />);
    // Un podium scratch (rank_overall=2), aucune victoire.
    // Trois cartes portent chacune le libellé « scratch ».
    expect(screen.getAllByText("général")).toHaveLength(3);
    // La carte Victoires porte 0, Podiums 1, Top 10 1.
    expect(screen.getByText("Victoires")).toBeInTheDocument();
  });

  it("?rank=category : lit le mode catégorie et recalcule", () => {
    searchParams = new URLSearchParams("rank=category");
    render(<StatCardsRank participations={PARTS} />);
    expect(screen.getAllByText("catégorie")).toHaveLength(3);
    // rank_category=1 → 1 victoire, 1 podium, 1 top 10.
  });

  it("?rank=gender : dédouble F / H", () => {
    searchParams = new URLSearchParams("rank=gender");
    render(<StatCardsRank participations={PARTS} />);
    expect(screen.getAllByText("genre")).toHaveLength(3);
    // Étiquettes F et H présentes une fois par carte.
    expect(screen.getAllByText("F")).toHaveLength(3);
    expect(screen.getAllByText("H")).toHaveLength(3);
  });

  it("?rank=all : mode agrégé", () => {
    searchParams = new URLSearchParams("rank=all");
    render(<StatCardsRank participations={PARTS} />);
    expect(screen.getAllByText("général, genre ou catégorie")).toHaveLength(3);
  });

  it("?rank=foo : retombe silencieusement sur scratch", () => {
    searchParams = new URLSearchParams("rank=foo");
    render(<StatCardsRank participations={PARTS} />);
    expect(screen.getAllByText("général")).toHaveLength(3);
    expect(screen.queryByText("catégorie")).not.toBeInTheDocument();
  });
});
