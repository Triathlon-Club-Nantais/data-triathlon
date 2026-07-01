import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { TCN_CLUB_FILTER } from "@/lib/club-constants";

const getStats = vi.fn();
const listEvents = vi.fn();
const listParticipations = vi.fn();
const listSeasons = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
    getStats: (club?: string) => getStats(club),
    listEvents: (filters: unknown) => listEvents(filters),
    listParticipations: (filters: unknown) => listParticipations(filters),
    listSeasons: (club?: string) => listSeasons(club),
  },
}));

// SeasonSelector est un composant client (useRouter/useSearchParams).
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

import DashboardPage from "./page";

const STATS = {
  total: 42,
  athletes: 10,
  events: 5,
  by_type: { "Triathlon S": 30, "Duathlon M": 12 },
  by_month: {},
  recent: [],
};
const EVENTS_PAGE = { items: [], total_events: 5, total_participations: 42 };
const PARTICIPATIONS = [{ rank_overall: 1 }, { rank_overall: 4 }, { rank_overall: 50 }];
const SEASONS = [
  { start_year: 2026, label: "Saison 2026", event_count: 5, participation_count: 42, is_current: true },
  { start_year: 2025, label: "Saison 2025", event_count: 3, participation_count: 20, is_current: false },
];

beforeEach(() => {
  vi.clearAllMocks();
  getStats.mockResolvedValue(STATS);
  listEvents.mockResolvedValue(EVENTS_PAGE);
  listParticipations.mockResolvedValue(PARTICIPATIONS);
  listSeasons.mockResolvedValue(SEASONS);
});

async function renderDashboard(searchParams: Record<string, string | undefined> = {}) {
  const ui = await DashboardPage({ searchParams: Promise.resolve(searchParams) });
  return render(ui);
}

describe("DashboardPage", () => {
  it("force la portée club sur tous les appels API, même sans ?scope=club", async () => {
    await renderDashboard({});

    expect(getStats).toHaveBeenCalledWith(TCN_CLUB_FILTER);
    expect(listEvents).toHaveBeenCalledWith(
      expect.objectContaining({ club: TCN_CLUB_FILTER }),
    );
    expect(listParticipations).toHaveBeenCalledWith(
      expect.objectContaining({ club: TCN_CLUB_FILTER }),
    );
  });

  it("ignore ?scope et reste sur le club même si l'URL demande « tous »", async () => {
    await renderDashboard({ scope: undefined }); // pas de scope = ancien mode « Tous »

    expect(getStats).toHaveBeenCalledWith(TCN_CLUB_FILTER);
  });

  it("ne rend plus le sélecteur de portée (Tous / Membres TCN)", async () => {
    await renderDashboard({});

    expect(screen.queryByText("Tous")).toBeNull();
    expect(screen.queryByText("Membres TCN")).toBeNull();
    expect(screen.queryByRole("group", { name: "Portée" })).toBeNull();
  });

  it("rend le sélecteur de saison alimenté par les saisons du club", async () => {
    await renderDashboard({});

    expect(listSeasons).toHaveBeenCalledWith(TCN_CLUB_FILTER);
    expect(screen.getByLabelText("Choisir les saisons")).toBeTruthy();
  });
});
