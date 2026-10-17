import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Stats } from "@/lib/types";
import { BandeauDirect } from "./BandeauDirect";

const bucket = { victories: 0, podiums: 0, top10: 0 };
const STATS: Stats = {
  total: 312, athletes: 87, events: 14, by_type: {}, recent: [],
  by_month: { "2026-09": 120, "2026-10": 192 },
  rank_counters: { scratch: bucket, category: bucket, all: { ...bucket, podiums: 27 }, gender: { women: bucket, men: bucket } },
};
const TODAY = new Date("2026-10-15T12:00:00");

describe("BandeauDirect", () => {
  beforeEach(() => {
    vi.stubGlobal("matchMedia", (query: string) => ({ matches: true, media: query, addEventListener() {}, removeEventListener() {} }));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("shows a recent outing as « Ce week-end » with its figures", () => {
    render(<BandeauDirect sortie={{ end_date: "2026-10-11", events: 3, athletes: 48, podiums: 9 }} stats={STATS} season={2026} today={TODAY} />);
    expect(screen.getByText("Ce week-end")).toBeInTheDocument();
    expect(screen.getByText("48 TCN")).toBeInTheDocument();
    expect(screen.getByText(/3 épreuves · 9 podiums/)).toBeInTheDocument();
  });

  it("dates an older outing", () => {
    render(<BandeauDirect sortie={{ end_date: "2026-09-06", events: 1, athletes: 5, podiums: 0 }} stats={STATS} season={2026} today={TODAY} />);
    expect(screen.getByText("Dernière sortie · 6 sept.")).toBeInTheDocument();
  });

  it("falls back when the season has no outing yet, season figures stay", () => {
    render(<BandeauDirect sortie={null} stats={STATS} season={2026} today={TODAY} />);
    expect(screen.getByText("Pas encore de course cette saison")).toBeInTheDocument();
    expect(screen.getByText("312")).toBeInTheDocument();
    expect(screen.getByText("27")).toBeInTheDocument();
  });

  it("summarises the monthly chart for screen readers", () => {
    render(<BandeauDirect sortie={null} stats={STATS} season={2026} today={TODAY} />);
    expect(screen.getByRole("img", { name: /Résultats par mois.*sept\. : 120.*oct\. : 192/ })).toBeInTheDocument();
  });
});
