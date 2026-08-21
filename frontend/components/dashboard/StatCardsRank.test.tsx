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

// WCAG 4.1.3 (#477) : la bascule recalcule en mémoire (#328), sans navigation
// ni re-fetch — rien ne signale le changement à un lecteur d'écran.
describe("StatCardsRank — annonce du changement (#477)", () => {
  it("annonce les compteurs du mode courant dans une région role=status", () => {
    searchParams = new URLSearchParams();
    render(<StatCardsRank rankCounters={COUNTERS} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Classement général : 0 victoire, 1 podium, 1 top 10",
    );
  });

  it("réannonce au changement de mode", () => {
    searchParams = new URLSearchParams();
    const { rerender } = render(<StatCardsRank rankCounters={COUNTERS} />);

    searchParams = new URLSearchParams("rank=category");
    rerender(<StatCardsRank rankCounters={COUNTERS} />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Classement catégorie : 1 victoire, 1 podium, 1 top 10",
    );
  });

  it("annonce le total F+H en mode genre, plutôt que de rester muette sur ce chemin (revue de code)", () => {
    searchParams = new URLSearchParams("rank=gender");
    render(<StatCardsRank rankCounters={COUNTERS} />);

    // women {v:0,p:0,t:1} + men {v:0,p:1,t:1} = 0 victoire, 1 podium, 2 top 10.
    expect(screen.getByRole("status")).toHaveTextContent(
      "Classement genre : 0 victoire, 1 podium, 2 top 10",
    );
  });
});
