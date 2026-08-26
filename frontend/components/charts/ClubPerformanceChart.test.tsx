import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ClubPerformanceChart } from "./ClubPerformanceChart";
import type { DashboardRankCounters } from "@/lib/types";

const searchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

const rankCounters: DashboardRankCounters = {
  scratch: { victories: 3, podiums: 12, top10: 40 },
  category: { victories: 5, podiums: 20, top10: 60 },
  all: { victories: 3, podiums: 12, top10: 40 },
  gender: {
    women: { victories: 1, podiums: 4, top10: 15 },
    men: { victories: 2, podiums: 8, top10: 25 },
  },
};

describe("ClubPerformanceChart", () => {
  it("affiche les trois compteurs du bucket scratch (défaut) en barres", () => {
    searchParams.delete("rank");
    render(<ClubPerformanceChart rankCounters={rankCounters} />);
    expect(screen.getByText("Victoires")).toBeInTheDocument();
    expect(screen.getByText("Podiums")).toBeInTheDocument();
    expect(screen.getByText("Top 10")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("40")).toBeInTheDocument();
  });

  it("réagit au type de classement choisi (?rank=category)", () => {
    searchParams.set("rank", "category");
    render(<ClubPerformanceChart rankCounters={rankCounters} />);
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.queryByText("3")).not.toBeInTheDocument();
    searchParams.delete("rank");
  });

  it("agrège femmes+hommes en mode gender", () => {
    searchParams.set("rank", "gender");
    render(<ClubPerformanceChart rankCounters={rankCounters} />);
    expect(screen.getByText("3")).toBeInTheDocument(); // 1+2 victoires
    searchParams.delete("rank");
  });

  it("annonce un récapitulatif accessible mentionnant le libellé du classement", () => {
    searchParams.delete("rank");
    render(<ClubPerformanceChart rankCounters={rankCounters} />);
    expect(screen.getByRole("img", { name: /général/i })).toBeInTheDocument();
  });
});
