import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Stats } from "@/lib/types";

const getStats = vi.fn();
const listEvents = vi.fn();
const getClubLastOuting = vi.fn();
vi.mock("@/lib/api/server", () => ({
  apiServer: {
    getStats: (o: unknown, f?: unknown) => getStats(o, f),
    listEvents: (o: unknown, f?: unknown) => listEvents(o, f),
    getClubLastOuting: (o: unknown, f?: unknown) => getClubLastOuting(o, f),
  },
  SHORT_REVALIDATE_SECONDS: 30,
}));
vi.mock("@/components/home/TuilesEspaces", () => ({ TuilesEspaces: () => <nav aria-label="Espaces" /> }));

import HomePage from "./page";

const bucket = { victories: 0, podiums: 0, top10: 0 };
const STATS: Stats = { total: 312, athletes: 87, events: 14, by_type: {}, by_month: {}, recent: [], rank_counters: { scratch: bucket, category: bucket, all: bucket, gender: { women: bucket, men: bucket } } };

async function afficher(sp: Record<string, string> = {}) {
  const ui = await HomePage({ searchParams: Promise.resolve(sp) });
  return render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);
}

describe("HomePage", () => {
  beforeEach(() => {
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
    expect(getClubLastOuting).toHaveBeenCalledWith({ federal_only: true }, { revalidateSeconds: 30 });
  });

  it("keeps the season figures when the last outing call fails", async () => {
    getStats.mockResolvedValue(STATS);
    listEvents.mockResolvedValue({ items: [], total_events: 0, total_participations: 0 });
    getClubLastOuting.mockRejectedValue(new Error("down"));

    await afficher();

    expect(screen.getByText("Pas encore de course cette saison")).toBeInTheDocument();
    expect(screen.getByText("312")).toBeInTheDocument();
  });
});
