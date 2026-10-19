import { describe, it, expect, vi, beforeEach } from "vitest";
import { render as renderRTL, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import type { ClubSummary, Participation, Stats } from "@/lib/types";
import { currentSeason } from "@/lib/utils/season";

const getStats = vi.fn();
const getClubSummary = vi.fn();
const listParticipations = vi.fn();
const getClubBestTimes = vi.fn();
const listSeasons = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
    getStats: (opts: unknown, fetchOpts?: unknown) => getStats(opts, fetchOpts),
    getClubSummary: (opts: unknown, fetchOpts?: unknown) => getClubSummary(opts, fetchOpts),
    listParticipations: (filters: unknown, fetchOpts?: unknown) => listParticipations(filters, fetchOpts),
    getClubBestTimes: (opts: unknown, fetchOpts?: unknown) => getClubBestTimes(opts, fetchOpts),
    listSeasons: (opts: unknown, fetchOpts?: unknown) => listSeasons(opts, fetchOpts),
  },
  SHORT_REVALIDATE_SECONDS: 30,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/club",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/components/charts/BarList", () => ({ BarList: () => <div data-testid="barlist" /> }));
vi.mock("@/components/charts/MonthlyTrend", () => ({ MonthlyTrend: () => <div data-testid="monthly" /> }));

import ClubPage from "./page";

const STATS: Stats = {
  total: 42, athletes: 10, events: 5,
  by_type: {}, by_month: {}, recent: [],
  rank_counters: {
    scratch: { victories: 0, podiums: 0, top10: 0 },
    category: { victories: 0, podiums: 0, top10: 0 },
    all: { victories: 0, podiums: 0, top10: 0 },
    gender: { women: { victories: 0, podiums: 0, top10: 0 }, men: { victories: 0, podiums: 0, top10: 0 } },
  },
};

const SUMMARY: ClubSummary = {
  roster: [],
  podiums: { scratch: [], category: [], gender: [], all: [] },
  podiums_totals: { scratch: 0, category: 0, gender: 0, all: 0 },
  podiums_by_discipline: {},
  composition: { gender: {}, category: {} },
  licensees: null,
};

const SEASONS = [
  { start_year: 2026, label: "Saison 2026", event_count: 5, participation_count: 42, is_current: true },
  { start_year: 2025, label: "Saison 2025", event_count: 3, participation_count: 20, is_current: false },
];

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: over.athlete ?? { id: over.id, nom: "N", prenom: "P", gender: "F", club: "TCN" },
    course: over.course ?? {
      id: over.id, name: `Course ${over.id}`, event_date: "2026-05-10",
      event_type: "triathlon-m", provider: "manuel", source_url: "", is_relay: false,
    },
    club: "TCN", is_tcn: true, category: null, bib_number: null,
    rank_overall: over.rank_overall ?? null, rank_category: null, rank_gender: null,
    total_time: "01:59:00", status: "finisher", is_relay: false, splits: null,
    created_at: "2026-05-11T10:00:00Z",
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  getStats.mockResolvedValue(STATS);
  getClubSummary.mockResolvedValue(SUMMARY);
  listParticipations.mockResolvedValue([part({ id: 1 })]);
  getClubBestTimes.mockResolvedValue([]);
  listSeasons.mockResolvedValue(SEASONS);
});

// `RosterApercu` appelle `useClubRosterRank` (#641) : un `QueryClientProvider`
// doit envelopper le rendu, même si aucun test ici ne sélectionne d'athlète.
function render(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderRTL(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

async function renderClub(searchParams: Record<string, string | undefined> = {}) {
  const ui = await ClubPage({ searchParams: Promise.resolve(searchParams) });
  return render(ui);
}

describe("ClubPage", () => {
  it("demande une fenêtre de revalidation courte sur les trois appels (#352)", async () => {
    await renderClub({});
    expect(getStats).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
    expect(getClubSummary).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
    expect(listParticipations).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
  });

  // #581 : la page ne demande plus le plafond de /participations — seulement
  // les 6 résultats récents affichés. Le roster et les podiums viennent de
  // /club/summary, agrégés côté serveur.
  it("demande 6 résultats récents, pas 5000", async () => {
    await renderClub({});
    expect(listParticipations).toHaveBeenCalledWith(
      expect.objectContaining({ page_size: 6 }),
      expect.anything(),
    );
  });

  it("scopes every figure to ?seasons and takes the max season for the best times", async () => {
    await renderClub({ seasons: "2024,2025" });

    expect(getStats).toHaveBeenCalledTimes(1);
    expect(getStats).toHaveBeenCalledWith(
      expect.objectContaining({ seasons: [2024, 2025] }),
      expect.anything(),
    );
    expect(getClubSummary).toHaveBeenCalledWith(
      expect.objectContaining({ seasons: [2024, 2025] }),
      expect.anything(),
    );
    expect(listParticipations).toHaveBeenCalledWith(
      expect.objectContaining({ seasons: [2024, 2025] }),
      expect.anything(),
    );
    expect(getClubBestTimes).toHaveBeenCalledWith(
      expect.objectContaining({ season: 2025 }),
      expect.anything(),
    );
  });

  it("falls back to the current season without ?seasons and makes a single stats call", async () => {
    await renderClub({});

    expect(getStats).toHaveBeenCalledTimes(1);
    expect(getStats).toHaveBeenCalledWith(
      expect.objectContaining({ seasons: [currentSeason()] }),
      expect.anything(),
    );
    expect(getClubSummary).toHaveBeenCalledWith(
      expect.objectContaining({ seasons: [currentSeason()] }),
      expect.anything(),
    );
  });

  it("renders the season selector", async () => {
    await renderClub({});

    expect(listSeasons).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "club" }),
      expect.anything(),
    );
    expect(screen.getByText("Saisons")).toBeInTheDocument();
  });

  it("renders the empty state for a season without results", async () => {
    getStats.mockResolvedValue({ ...STATS, total: 0 });

    await renderClub({ seasons: "2020" });

    expect(screen.getByText("Aucun résultat de club")).toBeInTheDocument();
  });

  it("asks the club best times for the selected season and for all seasons (#1588)", async () => {
    await renderClub({ sports: "federal" });

    expect(getClubBestTimes).toHaveBeenCalledWith(
      { season: currentSeason(), federal_only: true },
      { revalidateSeconds: 30 },
    );
    expect(getClubBestTimes).toHaveBeenCalledWith({ federal_only: true }, { revalidateSeconds: 30 });
  });

  it("shows the club best times card", async () => {
    getClubBestTimes.mockResolvedValue([
      {
        participation_id: 1, course_id: 2, athlete_id: 3, athlete_name: "Alice DUPONT",
        event_name: "Tri", event_type: "triathlon-m", event_date: "2026-05-16",
        gender: "F", total_time: "02:05:30",
      },
    ]);

    await renderClub({});

    expect(screen.getByRole("heading", { name: "Meilleurs temps du club" })).toBeInTheDocument();
  });
});
