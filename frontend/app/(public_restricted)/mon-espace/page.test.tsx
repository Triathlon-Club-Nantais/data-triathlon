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
  usePathname: () => "/mon-espace",
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

// `InvitationAthlete` (#588) est un composant client sans props, testé pour
// lui-même (`components/dashboard/InvitationAthlete.test.tsx`) : ici on ne
// vérifie que sa présence et sa place dans le document.
vi.mock("@/components/dashboard/InvitationAthlete", () => ({
  InvitationAthlete: () => <div data-testid="invitation-athlete-stub" />,
}));

import MonEspacePage from "./page";

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
  const ui = await MonEspacePage({ searchParams: Promise.resolve(searchParams) });
  return render(ui);
}

describe("MonEspacePage", () => {
  it("porte l'eyebrow « Mon espace »", async () => {
    await renderDashboard({});

    expect(screen.getByText("Mon espace")).toBeInTheDocument();
  });

  it("force la portée club sur tous les appels API, même sans ?scope=club", async () => {
    await renderDashboard({});

    expect(getStats).toHaveBeenCalledWith(expect.objectContaining({ scope: "club" }), expect.anything());
    expect(listEvents).not.toHaveBeenCalled();
    expect(screen.queryByRole("heading", { name: "Dernières épreuves" })).toBeNull();
  });

  it("demande une fenêtre de revalidation courte sur les appels (#352)", async () => {
    await renderDashboard({});

    expect(getStats).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
    expect(listSeasons).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
  });

  it("ignore ?scope et reste sur le club même si l'URL demande « tous »", async () => {
    await renderDashboard({ scope: undefined }); // pas de scope = ancien mode « Tous »

    expect(getStats).toHaveBeenCalledWith(expect.objectContaining({ scope: "club" }), expect.anything());
  });

  it("ne rend plus le sélecteur de portée (Tous / Membres TCN)", async () => {
    await renderDashboard({});

    expect(screen.queryByText("Membres TCN")).toBeNull();
    expect(screen.queryByRole("radiogroup", { name: "Portée" })).toBeNull();
  });

  it("rend le sélecteur de saison alimenté par les saisons du club", async () => {
    await renderDashboard({});

    expect(listSeasons).toHaveBeenCalledWith(expect.objectContaining({ scope: "club" }), expect.anything());
    expect(screen.getByLabelText(/choisir les saisons/i)).toBeTruthy();
  });

  it("rend le titre de saison comme un <h1> (A11Y-2)", async () => {
    url.qs = "seasons=2026,2025";
    await renderDashboard({ seasons: "2026,2025" });

    expect(screen.getByRole("heading", { level: 1, name: "2 saisons sélectionnées" })).toBeInTheDocument();
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

    expect(barre).toContainElement(screen.getByLabelText(/choisir les saisons/i));
    expect(barre).toContainElement(screen.getByLabelText("Inclure les autres disciplines"));
    expect(barre).not.toContainElement(tags);
    expect(tags).toHaveTextContent("Saison 2026");
    expect(tags).toHaveTextContent("Saison 2025");
  });

  it("nomme visiblement les 2 contrôles de filtrage, sans sélecteur de rang (NAV-5)", async () => {
    await renderDashboard({});

    const barre = screen.getByTestId("dashboard-toolbar");
    expect(screen.getByText("Disciplines")).toBeInTheDocument();
    expect(screen.getByText("Saisons")).toBeInTheDocument();
    expect(screen.queryByText("Type de rang")).toBeNull();
    expect(barre).toContainElement(screen.getByLabelText("Inclure les autres disciplines"));
    expect(barre).toContainElement(screen.getByLabelText(/choisir les saisons/i));
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

describe("MonEspacePage — état vide unifié (NAV-6)", () => {
  const STATS_VIDE = { ...STATS, total: 0, athletes: 0, events: 0, by_type: {} };
  const EVENTS_PAGE_VIDE = { items: [], total_events: 0, total_participations: 0 };

  it("remplace toute la grille par un état vide unique quand stats.total === 0", async () => {
    getStats.mockResolvedValue(STATS_VIDE);
    listEvents.mockResolvedValue(EVENTS_PAGE_VIDE);

    await renderDashboard({ seasons: "2015" });

    expect(screen.getByText("Aucun résultat enregistré pour la saison 2015 — 2016")).toBeInTheDocument();
  });

  it("propose « Voir la saison en cours » quand la sélection n'est pas la saison en cours", async () => {
    getStats.mockResolvedValue(STATS_VIDE);
    listEvents.mockResolvedValue(EVENTS_PAGE_VIDE);

    await renderDashboard({ seasons: "2015" });

    const voir = screen.getByRole("link", { name: "Voir la saison en cours" });
    expect(voir).toHaveAttribute("href", "/mon-espace");
    expect(voir).toHaveClass("tcn-cible-tactile");
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

    const ajouter = screen.getByRole("link", { name: "Ajouter une épreuve" });
    expect(ajouter).toHaveAttribute("href", "/ajouter");
    expect(ajouter).toHaveClass("tcn-cible-tactile");
  });
});

describe("MonEspacePage — bande « Ma saison » (#502, NAV-9)", () => {
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
});

describe("MonEspacePage — invitation à choisir un athlète (#588)", () => {
  it("monte l'invitation sur une sélection non vide", async () => {
    await renderDashboard({});

    expect(screen.getByTestId("invitation-athlete-stub")).toBeInTheDocument();
  });

  it("ne monte pas l'invitation quand la sélection du club est vide — l'EmptyState porte déjà la sortie", async () => {
    getStats.mockResolvedValue({ ...STATS, total: 0, athletes: 0, events: 0, by_type: {} });
    listEvents.mockResolvedValue({ items: [], total_events: 0, total_participations: 0 });

    await renderDashboard({ seasons: "2019" });

    expect(screen.queryByTestId("invitation-athlete-stub")).not.toBeInTheDocument();
  });
});

describe("MonEspacePage: personal page, the home page leads to the club (#1299, #1620)", () => {
  it("no longer renders the club aggregates", async () => {
    await renderDashboard({});

    expect(screen.queryByRole("heading", { name: "Performance du club" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Type d'épreuves" })).toBeNull();
  });

  it("drops the « Le club » card, the home page now leads to the club (#1620)", async () => {
    await renderDashboard({});

    expect(screen.queryByRole("heading", { name: "Le club" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Voir la page Club/ })).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });
});
