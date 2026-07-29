import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const getStats = vi.fn();
const listEvents = vi.fn();
const listParticipations = vi.fn();
const listSeasons = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
    getStats: (opts: unknown) => getStats(opts),
    listEvents: (filters: unknown) => listEvents(filters),
    listParticipations: (filters: unknown) => listParticipations(filters),
    listSeasons: (opts: unknown) => listSeasons(opts),
  },
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

    expect(getStats).toHaveBeenCalledWith(expect.objectContaining({ scope: "club" }));
    expect(listEvents).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "club" }),
    );
    expect(listParticipations).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "club" }),
    );
  });

  it("ignore ?scope et reste sur le club même si l'URL demande « tous »", async () => {
    await renderDashboard({ scope: undefined }); // pas de scope = ancien mode « Tous »

    expect(getStats).toHaveBeenCalledWith(expect.objectContaining({ scope: "club" }));
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

    expect(listSeasons).toHaveBeenCalledWith(expect.objectContaining({ scope: "club" }));
    expect(screen.getByLabelText("Choisir les saisons")).toBeTruthy();
  });

  it("exclut les autres disciplines par défaut et les inclut sur demande", async () => {
    await renderDashboard({});
    expect(getStats).toHaveBeenCalledWith(
      expect.objectContaining({ federal_only: true }),
    );

    vi.clearAllMocks();
    getStats.mockResolvedValue(STATS);
    listEvents.mockResolvedValue(EVENTS_PAGE);
    listParticipations.mockResolvedValue(PARTICIPATIONS);
    listSeasons.mockResolvedValue(SEASONS);

    await renderDashboard({ sports: "all" });
    expect(getStats).toHaveBeenCalledWith(
      expect.objectContaining({ federal_only: undefined }),
    );
  });
});

// Sélecteur de type de rang (#104) — cases US1 : modes scalaires (scratch,
// category, all) et défaut silencieux sur valeur inconnue.
describe("DashboardPage — sélecteur de type de rang", () => {
  // Fixture divergente : rang scratch=100, rang catégorie=1. En mode Scratch,
  // la victoire ne compte PAS. En mode Catégorie, elle compte. C'est ce qui
  // permet de distinguer le mode actif au-delà du seul libellé.
  const DIVERGENT = [
    { rank_overall: 100, rank_category: 1, rank_gender: 50 },
    { rank_overall: 2, rank_category: 30 },
  ];

  function tileTextByLabel(label: string): string {
    // Structure StatCard : <div card> ── <div flex> ── <div>{label}</div>
    //                              └─ <div>{value}</div>. Le label est à deux
    // parents de profondeur de la carte, pas un seul.
    const el = screen.getByText(label);
    const tile = el.parentElement?.parentElement;
    return tile?.textContent ?? "";
  }

  it("sans ?rank=, applique le défaut Scratch (libellé « scratch »)", async () => {
    listParticipations.mockResolvedValue(DIVERGENT);
    await renderDashboard({});
    expect(screen.getAllByText("scratch").length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByText("scratch, genre ou catégorie")).not.toBeInTheDocument();
  });

  it("le défaut Scratch ne compte QUE rank_overall", async () => {
    listParticipations.mockResolvedValue(DIVERGENT);
    await renderDashboard({});
    // rank_overall=2 → 1 podium scratch. La victoire cat (rank_category=1) est
    // ignorée. Donc Victoires=0, Podiums=1.
    expect(tileTextByLabel("Victoires")).toContain("0");
    expect(tileTextByLabel("Podiums")).toContain("1");
  });

  it("?rank=category applique le mode Catégorie (libellé « catégorie »)", async () => {
    listParticipations.mockResolvedValue(DIVERGENT);
    await renderDashboard({ rank: "category" });
    expect(screen.getAllByText("catégorie").length).toBeGreaterThanOrEqual(3);
    // La victoire de catégorie compte maintenant.
    expect(tileTextByLabel("Victoires")).toContain("1");
  });

  it("?rank=all conserve le libellé historique « scratch, genre ou catégorie »", async () => {
    listParticipations.mockResolvedValue(DIVERGENT);
    await renderDashboard({ rank: "all" });
    expect(screen.getAllByText("scratch, genre ou catégorie").length).toBeGreaterThanOrEqual(3);
    // Min(100, 1, 50)=1 → 1 victoire (via cat) + 1 podium (via scratch=2) → v=1, p=2
    expect(tileTextByLabel("Victoires")).toContain("1");
    expect(tileTextByLabel("Podiums")).toContain("2");
  });

  it("?rank=foo (valeur inconnue) retombe silencieusement sur Scratch", async () => {
    listParticipations.mockResolvedValue(DIVERGENT);
    await renderDashboard({ rank: "foo" });
    expect(screen.getAllByText("scratch").length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByText("scratch, genre ou catégorie")).not.toBeInTheDocument();
  });

  it("?rank=gender dédouble chaque carte en compteur F et compteur H distincts", async () => {
    // 2 femmes classées + 1 homme classé. Les cartes doivent exposer F et H
    // séparément — pas une somme, pas un mélange.
    const alice = { id: 10, nom: "Alice", prenom: "A", gender: "F", club: "TCN" };
    const bob = { id: 20, nom: "Bob", prenom: "B", gender: "M", club: "TCN" };
    listParticipations.mockResolvedValue([
      { athlete: alice, rank_gender: 1 },
      { athlete: alice, rank_gender: 3 },
      { athlete: bob, rank_gender: 1 },
    ]);
    await renderDashboard({ rank: "gender" });
    // Étiquettes F et H présentes explicitement dans les cartes.
    // On les cherche au moins une fois par carte (3 cartes × 2 étiquettes).
    expect(screen.getAllByText(/^F$/).length).toBeGreaterThanOrEqual(3);
    expect(screen.getAllByText(/^H$/).length).toBeGreaterThanOrEqual(3);
    // Libellé mode courant (« genre ») présent au moins une fois.
    expect(screen.getAllByText("genre").length).toBeGreaterThanOrEqual(3);
  });
});
