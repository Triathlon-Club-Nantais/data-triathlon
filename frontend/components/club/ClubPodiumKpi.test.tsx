import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { DashboardRankCounters } from "@/lib/types";

let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

import { ClubPodiumKpi } from "./ClubPodiumKpi";

const RANK_COUNTERS: DashboardRankCounters = {
  scratch: { victories: 0, podiums: 4, top10: 0 },
  category: { victories: 0, podiums: 7, top10: 0 },
  all: { victories: 0, podiums: 11, top10: 0 },
  gender: {
    women: { victories: 0, podiums: 2, top10: 0 },
    men: { victories: 0, podiums: 3, top10: 0 },
  },
};

describe("ClubPodiumKpi — lit rank_counters (#581, miroir de StatCardsRank)", () => {
  it("sans ?rank= (défaut scratch) : lit rankCounters.scratch.podiums", () => {
    searchParams = new URLSearchParams();
    render(<ClubPodiumKpi rankCounters={RANK_COUNTERS} />);
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("Podiums")).toBeInTheDocument();
  });

  it("?rank=category : lit rankCounters.category.podiums", () => {
    searchParams = new URLSearchParams("rank=category");
    render(<ClubPodiumKpi rankCounters={RANK_COUNTERS} />);
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("?rank=all : lit rankCounters.all.podiums", () => {
    searchParams = new URLSearchParams("rank=all");
    render(<ClubPodiumKpi rankCounters={RANK_COUNTERS} />);
    expect(screen.getByText("11")).toBeInTheDocument();
  });

  it("?rank=gender : somme women.podiums + men.podiums", () => {
    searchParams = new URLSearchParams("rank=gender");
    render(<ClubPodiumKpi rankCounters={RANK_COUNTERS} />);
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("nomme la portée du décompte, mode par mode (PROF-3, #488)", () => {
    searchParams = new URLSearchParams();
    const { unmount } = render(<ClubPodiumKpi rankCounters={RANK_COUNTERS} />);
    expect(screen.getByText("général")).toBeInTheDocument();
    unmount();

    searchParams = new URLSearchParams("rank=all");
    render(<ClubPodiumKpi rankCounters={RANK_COUNTERS} />);
    expect(screen.getByText("général, genre ou catégorie")).toBeInTheDocument();
  });
});
