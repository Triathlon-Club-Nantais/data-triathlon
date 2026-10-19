import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Stats } from "@/lib/types";

const getStats = vi.fn();
const listEvents = vi.fn();
const getClubLastOuting = vi.fn();
const listSeasons = vi.fn();
vi.mock("@/lib/api/server", () => ({
  apiServer: {
    getStats: (o: unknown, f?: unknown) => getStats(o, f),
    listEvents: (o: unknown, f?: unknown) => listEvents(o, f),
    getClubLastOuting: (o: unknown, f?: unknown) => getClubLastOuting(o, f),
    listSeasons: (o: unknown, f?: unknown) => listSeasons(o, f),
  },
  SHORT_REVALIDATE_SECONDS: 30,
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/components/home/TuilesEspaces", () => ({ TuilesEspaces: () => <nav aria-label="Espaces" /> }));

import { currentSeason } from "@/lib/utils/season";
import HomePage from "./page";

const bucket = { victories: 0, podiums: 0, top10: 0 };
const STATS: Stats = { total: 312, athletes: 87, events: 14, by_type: {}, by_month: {}, recent: [], rank_counters: { scratch: bucket, category: bucket, all: bucket, gender: { women: bucket, men: bucket } } };

async function afficher(sp: Record<string, string> = {}) {
  const ui = await HomePage({ searchParams: Promise.resolve(sp) });
  return render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);
}

describe("HomePage", () => {
  beforeEach(() => {
    listSeasons.mockResolvedValue([
      { start_year: 2026, label: "Saison 2026", event_count: 5, participation_count: 42, is_current: true },
      { start_year: 2025, label: "Saison 2025", event_count: 3, participation_count: 20, is_current: false },
    ]);
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: true, media: q, addEventListener() {}, removeEventListener() {} }));
  });

  it("renders the live banner and the space tiles from the club's season", async () => {
    getStats.mockResolvedValue(STATS);
    listEvents.mockResolvedValue({ items: [], total_events: 0, total_participations: 0 });
    getClubLastOuting.mockResolvedValue(null);

    await afficher();

    expect(screen.getByRole("heading", { level: 1, name: /Triathlon Club Nantais/ })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Espaces" })).toBeInTheDocument();
    expect(getStats).toHaveBeenCalledWith(expect.objectContaining({ scope: "club", federal_only: true }), { revalidateSeconds: 30 });
    expect(listEvents).toHaveBeenCalledWith(expect.objectContaining({ page_size: 1 }), { revalidateSeconds: 30 });
    expect(getClubLastOuting).toHaveBeenCalledWith({ federal_only: true, seasons: [currentSeason()] }, { revalidateSeconds: 30 });
  });

  it("keeps the season figures when the last outing call fails", async () => {
    getStats.mockResolvedValue(STATS);
    listEvents.mockResolvedValue({ items: [], total_events: 0, total_participations: 0 });
    getClubLastOuting.mockRejectedValue(new Error("down"));

    await afficher();

    expect(screen.getByText("Pas encore d'épreuve cette saison")).toBeInTheDocument();
    expect(screen.getByText("312")).toBeInTheDocument();
  });

  it("follows ?seasons= for the figures, the last outing and the selector", async () => {
    getStats.mockResolvedValue(STATS);
    listEvents.mockResolvedValue({ items: [], total_events: 0, total_participations: 0 });
    getClubLastOuting.mockResolvedValue(null);

    await afficher({ seasons: "2025" });

    expect(getStats).toHaveBeenCalledWith(expect.objectContaining({ seasons: [2025] }), { revalidateSeconds: 30 });
    expect(getClubLastOuting).toHaveBeenCalledWith({ federal_only: true, seasons: [2025] }, { revalidateSeconds: 30 });
    expect(screen.getByText("Saisons")).toBeInTheDocument();
  });
});
