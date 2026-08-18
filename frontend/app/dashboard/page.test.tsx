import type { ReactNode } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const getStats = vi.fn();
const listEvents = vi.fn();
const listSeasons = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
    getStats: (opts: unknown, fetchOpts?: unknown) => getStats(opts, fetchOpts),
    listEvents: (filters: unknown, fetchOpts?: unknown) => listEvents(filters, fetchOpts),
    listSeasons: (opts: unknown, fetchOpts?: unknown) => listSeasons(opts, fetchOpts),
  },
  SHORT_REVALIDATE_SECONDS: 30,
}));

// SeasonSelector et DisciplineToggle sont des composants client
// (useRouter/usePathname/useSearchParams). La query string est mutable : la
// place des tags de saison (#445) ne s'observe qu'en multi-saisons.
const url = vi.hoisted(() => ({ qs: "" }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(url.qs),
}));

// `prefetch` ne se reflète sur aucun attribut DOM du <a> réel de next/link
// (comportement purement interne, piloté par IntersectionObserver) : on ne
// peut donc vérifier son câblage qu'en interceptant le composant lui-même.
vi.mock("next/link", () => ({
  default: ({
    href,
    prefetch,
    children,
    ...rest
  }: {
    href: string;
    prefetch?: boolean;
    children?: ReactNode;
    [key: string]: unknown;
  }) => (
    <a href={href} data-prefetch={String(prefetch)} {...rest}>
      {children}
    </a>
  ),
}));

import DashboardPage from "./page";

const ZERO_BUCKET = { victories: 0, podiums: 0, top10: 0 };
const STATS = {
  total: 42,
  athletes: 10,
  events: 5,
  by_type: { "Triathlon S": 30, "Duathlon M": 12 },
  by_month: {},
  recent: [],
  rank_counters: {
    scratch: ZERO_BUCKET,
    category: ZERO_BUCKET,
    all: ZERO_BUCKET,
    gender: { women: ZERO_BUCKET, men: ZERO_BUCKET },
  },
};
const EVENTS_PAGE = { items: [], total_events: 5, total_participations: 42 };
const SEASONS = [
  { start_year: 2026, label: "Saison 2026", event_count: 5, participation_count: 42, is_current: true },
  { start_year: 2025, label: "Saison 2025", event_count: 3, participation_count: 20, is_current: false },
];

beforeEach(() => {
  vi.clearAllMocks();
  url.qs = "";
  getStats.mockResolvedValue(STATS);
  listEvents.mockResolvedValue(EVENTS_PAGE);
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
  });

  it("demande une fenêtre de revalidation courte sur les trois appels (#352)", async () => {
    await renderDashboard({});

    expect(getStats).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
    expect(listEvents).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
    expect(listSeasons).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
  });

  it("désactive le prefetch des liens « Épreuves préférées » (#425) — au-dessus de la ligne de flottaison, jusqu'à 6 à la fois, prefetchées au hasard sans intérêt", async () => {
    listEvents.mockResolvedValue({
      items: [
        { id: 5, event_name: "Ironman Nantes", event_date: null, event_type: "Triathlon L", is_relay: false, distance_km: 113, total: 30, tcn_count: 5 },
      ],
      total_events: 1,
      total_participations: 30,
    });

    await renderDashboard({});

    const lien = screen.getByRole("link", { name: /Ironman Nantes/ });
    expect(lien).toHaveAttribute("href", "/courses/5");
    expect(lien).toHaveAttribute("data-prefetch", "false");
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

  it("garde les tags de saison hors de la barre d'outils, pour que les boutons ne bougent pas (#445)", async () => {
    // Dans la barre, les tags l'élargissaient jusqu'à la faire basculer sous
    // le titre et repartir tout à gauche : les quatre boutons de sélection
    // changeaient de place à la deuxième saison cochée. La ligne de tags est
    // donc un frère de la barre, pas un de ses enfants.
    url.qs = "seasons=2026,2025";
    await renderDashboard({ seasons: "2026,2025" });

    const barre = screen.getByLabelText("Choisir les saisons").parentElement;
    const tags = screen.getByTestId("season-tags");

    expect(barre).not.toBeNull();
    expect(barre).toContainElement(screen.getByLabelText("Inclure les autres disciplines"));
    expect(barre).not.toContainElement(tags);
    expect(tags).toHaveTextContent("Saison 2026");
    expect(tags).toHaveTextContent("Saison 2025");
  });

  it("aligne les tags comme la barre d'outils, au palier où l'en-tête cesse de s'empiler (revue UI/UX)", async () => {
    // L'en-tête s'empile sous `lg` — la barre y passe donc à gauche, sous le
    // titre. Les tags doivent basculer au **même** palier, faute de quoi ils
    // restent à droite pendant que le bouton qui les commande est à gauche.
    url.qs = "seasons=2026,2025";
    await renderDashboard({ seasons: "2026,2025" });

    expect(screen.getByTestId("season-tags")).toHaveClass("justify-start", "lg:justify-end");
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
    await renderDashboard({});
    expect(screen.getAllByText("général").length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByText("général, genre ou catégorie")).not.toBeInTheDocument();
  });
});
