import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import type { Participation, Stats } from "@/lib/types";

const getStats = vi.fn();
const listParticipations = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
    getStats: (opts: unknown, fetchOpts?: unknown) => getStats(opts, fetchOpts),
    listParticipations: (filters: unknown, fetchOpts?: unknown) => listParticipations(filters, fetchOpts),
  },
  SHORT_REVALIDATE_SECONDS: 30,
}));

// RankTypeToggle, DisciplineToggle et ClubDashboard sont des composants client.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/club",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/components/charts/BarList", () => ({ BarList: () => <div data-testid="barlist" /> }));
vi.mock("@/components/charts/MonthlyTrend", () => ({ MonthlyTrend: () => <div data-testid="monthly" /> }));

import ClubPage from "./page";
import { CLUB_PARTICIPATIONS_PAGE_SIZE } from "@/components/club/ClubDashboard";

const STATS: Stats = {
  total: 42,
  athletes: 10,
  events: 5,
  by_type: { "Triathlon S": 30, "Duathlon M": 12 },
  by_month: {},
  recent: [],
  rank_counters: {
    scratch: { victories: 0, podiums: 0, top10: 0 },
    category: { victories: 0, podiums: 0, top10: 0 },
    all: { victories: 0, podiums: 0, top10: 0 },
    gender: {
      women: { victories: 0, podiums: 0, top10: 0 },
      men: { victories: 0, podiums: 0, top10: 0 },
    },
  },
};

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

const PARTICIPATIONS = [part({ id: 1, rank_overall: 1 }), part({ id: 2, rank_overall: 4 })];

beforeEach(() => {
  vi.clearAllMocks();
  getStats.mockResolvedValue(STATS);
  listParticipations.mockResolvedValue(PARTICIPATIONS);
});

async function renderClub(searchParams: Record<string, string | undefined> = {}) {
  const ui = await ClubPage({ searchParams: Promise.resolve(searchParams) });
  return render(ui);
}

describe("ClubPage", () => {
  it("demande une fenêtre de revalidation courte sur les deux appels (#352)", async () => {
    await renderClub({});

    expect(getStats).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
    expect(listParticipations).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
  });

  // #487 : la page demandait 1000 participations quand `/participations`
  // accepte 5000 (`page_size: int = Query(20, ge=1, le=5000)`). Le roster et
  // les 4 KPI se seraient tronqués en silence bien avant le plafond réel.
  it("demande le plafond réel de /participations", async () => {
    await renderClub({});

    expect(listParticipations).toHaveBeenCalledWith(
      expect.objectContaining({ page_size: CLUB_PARTICIPATIONS_PAGE_SIZE }),
      expect.anything(),
    );
    expect(CLUB_PARTICIPATIONS_PAGE_SIZE).toBe(5000);
  });
});
