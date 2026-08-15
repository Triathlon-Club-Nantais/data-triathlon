import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const getStats = vi.fn();
const listEvents = vi.fn();
const listParticipations = vi.fn();
const listSeasons = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
    getStats: (opts: unknown, fetchOpts?: unknown) => getStats(opts, fetchOpts),
    listEvents: (filters: unknown, fetchOpts?: unknown) => listEvents(filters, fetchOpts),
    listParticipations: (filters: unknown, fetchOpts?: unknown) => listParticipations(filters, fetchOpts),
    listSeasons: (opts: unknown, fetchOpts?: unknown) => listSeasons(opts, fetchOpts),
  },
  SHORT_REVALIDATE_SECONDS: 30,
}));

// SeasonSelector et DisciplineToggle sont des composants client
// (useRouter/usePathname/useSearchParams).
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/dashboard",
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

    expect(getStats).toHaveBeenCalledWith(expect.objectContaining({ scope: "club" }), expect.anything());
    expect(listEvents).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "club" }),
      expect.anything(),
    );
    expect(listParticipations).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "club" }),
      expect.anything(),
    );
  });

  it("demande une fenêtre de revalidation courte sur les quatre appels (#352)", async () => {
    await renderDashboard({});

    expect(getStats).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
    expect(listEvents).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
    expect(listParticipations).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
    expect(listSeasons).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
  });

  it("ignore ?scope et reste sur le club même si l'URL demande « tous »", async () => {
    await renderDashboard({ scope: undefined }); // pas de scope = ancien mode « Tous »

    expect(getStats).toHaveBeenCalledWith(expect.objectContaining({ scope: "club" }), expect.anything());
  });

  it("ne rend plus le sélecteur de portée (Tous / Membres TCN)", async () => {
    await renderDashboard({});

    // Note : « Tous » existe désormais dans le RankTypeToggle (#104), on ne
    // peut plus faire d'assertion sur ce mot seul. On cible le radiogroup de
    // portée par son aria-label, qui est ce qui disparaît vraiment.
    expect(screen.queryByText("Membres TCN")).toBeNull();
    expect(screen.queryByRole("radiogroup", { name: "Portée" })).toBeNull();
  });

  it("rend le sélecteur de saison alimenté par les saisons du club", async () => {
    await renderDashboard({});

    expect(listSeasons).toHaveBeenCalledWith(expect.objectContaining({ scope: "club" }), expect.anything());
    expect(screen.getByLabelText("Choisir les saisons")).toBeTruthy();
  });

  it("exclut les autres disciplines par défaut et les inclut sur demande", async () => {
    await renderDashboard({});
    expect(getStats).toHaveBeenCalledWith(
      expect.objectContaining({ federal_only: true }),
      expect.anything(),
    );

    vi.clearAllMocks();
    getStats.mockResolvedValue(STATS);
    listEvents.mockResolvedValue(EVENTS_PAGE);
    listParticipations.mockResolvedValue(PARTICIPATIONS);
    listSeasons.mockResolvedValue(SEASONS);

    await renderDashboard({ sports: "all" });
    expect(getStats).toHaveBeenCalledWith(
      expect.objectContaining({ federal_only: undefined }),
      expect.anything(),
    );
  });
});

// Sélecteur de type de rang (#104) — le rendu détaillé des 3 cartes vit
// désormais dans le composant client `StatCardsRank` (cf. issue #132) qui a
// ses propres tests. Ici on vérifie que la page monte bien le composant, en
// mode par défaut (les mocks `useSearchParams` renvoient une URL vide).
describe("DashboardPage — sélecteur de type de rang", () => {
  it("monte le StatCardsRank avec le mode par défaut (libellé « général »)", async () => {
    listParticipations.mockResolvedValue([
      { rank_overall: 2, rank_category: 30 },
    ]);
    await renderDashboard({});
    expect(screen.getAllByText("général").length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByText("général, genre ou catégorie")).not.toBeInTheDocument();
  });
});
