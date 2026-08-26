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

// `MaSaison` (#502) est un composant client testé pour lui-même
// (`components/dashboard/MaSaison.test.tsx`) : ici on ne vérifie que le
// câblage — quelles props la page lui transmet, et à quelle place dans le
// document. Le stub expose ses props reçues en attributs `data-*`.
vi.mock("@/components/dashboard/MaSaison", () => ({
  MaSaison: ({
    clubEvents,
    seasons,
    federalOnly,
  }: {
    clubEvents: number;
    seasons: string;
    federalOnly: boolean | undefined;
  }) => (
    <div
      data-testid="ma-saison-stub"
      data-club-events={clubEvents}
      data-seasons={seasons}
      data-federal-only={String(federalOnly)}
    />
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

describe("DashboardPage — états vides (ETAT-3)", () => {
  it("propose d'ajouter une épreuve quand aucune discipline n'est enregistrée", async () => {
    getStats.mockResolvedValue({ ...STATS, by_type: {} });
    await renderDashboard({});

    expect(screen.getByText("Aucune épreuve enregistrée")).toBeInTheDocument();
    // `eventsPage` (mock par défaut) est vide elle aussi : les deux états vides
    // du dashboard s'affichent ensemble, d'où `getAllBy` plutôt que `getBy`.
    const liens = screen.getAllByRole("link", { name: /Ajouter une épreuve/ });
    expect(liens.every((l) => l.getAttribute("href") === "/ajouter")).toBe(true);
  });

  it("propose d'ajouter une épreuve quand la liste des dernières épreuves est vide", async () => {
    // `EVENTS_PAGE` par défaut a déjà `items: []` : l'état vide est le cas
    // par défaut de la fixture, pas un cas à construire.
    await renderDashboard({});

    expect(screen.getByText("Aucune épreuve récente à afficher")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ajouter une épreuve/ })).toHaveAttribute("href", "/ajouter");
  });
});

describe("DashboardPage", () => {
  it("force la portée club sur tous les appels API, même sans ?scope=club", async () => {
    await renderDashboard({});

    expect(getStats).toHaveBeenCalledWith(expect.objectContaining({ scope: "club" }), expect.anything());
    expect(listEvents).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "club" }),
      expect.anything(),
    );
  });

  it("demande 6 dernières épreuves, pas 200 (#581)", async () => {
    await renderDashboard({});

    expect(listEvents).toHaveBeenCalledWith(
      expect.objectContaining({ page_size: 6 }),
      expect.anything(),
    );
  });

  it("demande une fenêtre de revalidation courte sur les trois appels (#352)", async () => {
    await renderDashboard({});

    expect(getStats).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
    expect(listEvents).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
    expect(listSeasons).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
  });

  it("désactive le prefetch des liens « Dernières épreuves » (#425) — au-dessus de la ligne de flottaison, jusqu'à 6 à la fois, prefetchées au hasard sans intérêt", async () => {
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

  it("trie les dernières épreuves par date décroissante plutôt que par volume (NAV-7)", async () => {
    listEvents.mockResolvedValue({
      items: [
        { id: 1, event_name: "Petit format", event_date: "2026-01-10", event_type: "Triathlon S", is_relay: false, distance_km: null, total: 50, tcn_count: 5 },
        { id: 2, event_name: "Ironman Nantes", event_date: "2026-06-14", event_type: "Triathlon L", is_relay: false, distance_km: 113, total: 5, tcn_count: 5 },
      ],
      total_events: 2,
      total_participations: 55,
    });

    await renderDashboard({});

    const liens = screen.getAllByRole("link", { name: /Petit format|Ironman Nantes/ });
    expect(liens[0]).toHaveTextContent("Ironman Nantes");
    expect(liens[1]).toHaveTextContent("Petit format");
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

  it("rend le titre de saison comme un <h1> (A11Y-2)", async () => {
    url.qs = "seasons=2026,2025";
    await renderDashboard({ seasons: "2026,2025" });

    expect(screen.getByRole("heading", { level: 1, name: "2 saisons sélectionnées" })).toBeInTheDocument();
  });

  it("rend les titres de carte comme des <h2> (A11Y-2)", async () => {
    await renderDashboard({});

    expect(screen.getByRole("heading", { level: 2, name: "Type d'épreuves" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Dernières épreuves" })).toBeInTheDocument();
  });

  it("garde les tags de saison hors de la barre d'outils, pour que les boutons ne bougent pas (#445)", async () => {
    // Dans la barre, les tags l'élargissaient jusqu'à la faire basculer sous
    // le titre et repartir tout à gauche : les quatre boutons de sélection
    // changeaient de place à la deuxième saison cochée. La ligne de tags est
    // donc un frère de la barre, pas un de ses enfants.
    url.qs = "seasons=2026,2025";
    await renderDashboard({ seasons: "2026,2025" });

    const barre = screen.getByTestId("dashboard-toolbar");
    const tags = screen.getByTestId("season-tags");

    expect(barre).toContainElement(screen.getByLabelText("Choisir les saisons"));
    expect(barre).toContainElement(screen.getByLabelText("Inclure les autres disciplines"));
    expect(barre).not.toContainElement(tags);
    expect(tags).toHaveTextContent("Saison 2026");
    expect(tags).toHaveTextContent("Saison 2025");
  });

  it("nomme visiblement les 3 contrôles de filtrage, et sort le sélecteur de rang de la barre d'outils (NAV-5)", async () => {
    await renderDashboard({});

    const barre = screen.getByTestId("dashboard-toolbar");
    expect(screen.getByText("Disciplines")).toBeInTheDocument();
    expect(screen.getByText("Saisons")).toBeInTheDocument();
    expect(screen.getByText("Type de rang")).toBeInTheDocument();

    const rankGroup = screen.getByRole("group", { name: "Type de rang" });
    expect(barre).not.toContainElement(rankGroup);
    expect(barre).toContainElement(screen.getByLabelText("Inclure les autres disciplines"));
    expect(barre).toContainElement(screen.getByLabelText("Choisir les saisons"));
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

describe("DashboardPage — état vide unifié (NAV-6)", () => {
  const STATS_VIDE = { ...STATS, total: 0, athletes: 0, events: 0, by_type: {} };
  const EVENTS_PAGE_VIDE = { items: [], total_events: 0, total_participations: 0 };

  it("remplace toute la grille par un état vide unique quand stats.total === 0", async () => {
    getStats.mockResolvedValue(STATS_VIDE);
    listEvents.mockResolvedValue(EVENTS_PAGE_VIDE);

    await renderDashboard({ seasons: "2015" });

    expect(screen.getByText("Aucun résultat enregistré pour la saison 2015 — 2016")).toBeInTheDocument();
    expect(screen.queryByText("Dossards enregistrés")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "Type d'épreuves" })).not.toBeInTheDocument();
  });

  it("propose « Voir la saison en cours » quand la sélection n'est pas la saison en cours", async () => {
    getStats.mockResolvedValue(STATS_VIDE);
    listEvents.mockResolvedValue(EVENTS_PAGE_VIDE);

    await renderDashboard({ seasons: "2015" });

    expect(screen.getByRole("link", { name: "Voir la saison en cours" })).toHaveAttribute("href", "/dashboard");
  });

  it("n'affiche pas « Voir la saison en cours » quand la saison en cours est déjà sélectionnée", async () => {
    getStats.mockResolvedValue(STATS_VIDE);
    listEvents.mockResolvedValue(EVENTS_PAGE_VIDE);

    await renderDashboard({});

    expect(screen.queryByRole("link", { name: "Voir la saison en cours" })).not.toBeInTheDocument();
  });

  it("garde le CTA « Ajouter une épreuve » dans l'état vide", async () => {
    getStats.mockResolvedValue(STATS_VIDE);
    listEvents.mockResolvedValue(EVENTS_PAGE_VIDE);

    await renderDashboard({});

    expect(screen.getByRole("link", { name: /Ajouter une épreuve/ })).toHaveAttribute("href", "/ajouter");
  });
});

describe("DashboardPage — bande « Ma saison » (#502, NAV-9)", () => {
  it("monte la bande avec les compteurs club et les filtres de la page, sur une sélection non vide", async () => {
    getStats.mockResolvedValue({ ...STATS, events: 32 });

    await renderDashboard({ seasons: "2025" });

    const bande = screen.getByTestId("ma-saison-stub");
    expect(bande).toHaveAttribute("data-club-events", "32");
    expect(bande).toHaveAttribute("data-seasons", "2025");
    // Aucun `?sports=all` dans l'URL : le défaut fédéral s'applique (#76).
    expect(bande).toHaveAttribute("data-federal-only", "true");
  });

  it("ne monte pas la bande quand la sélection du club est vide — l'EmptyState porte déjà la sortie", async () => {
    getStats.mockResolvedValue({ ...STATS, total: 0, athletes: 0, events: 0, by_type: {} });
    listEvents.mockResolvedValue({ items: [], total_events: 0, total_participations: 0 });

    await renderDashboard({ seasons: "2019" });

    expect(screen.getByText(/Aucun résultat enregistré/)).toBeInTheDocument();
    expect(screen.queryByTestId("ma-saison-stub")).not.toBeInTheDocument();
  });

  it("place la bande au-dessus de la grille de compteurs club, dans l'ordre du document", async () => {
    await renderDashboard({});

    const bande = screen.getByTestId("ma-saison-stub");
    const compteurClub = screen.getByText("Dossards enregistrés");

    expect(bande.compareDocumentPosition(compteurClub) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
