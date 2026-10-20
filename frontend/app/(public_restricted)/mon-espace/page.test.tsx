import type { ReactNode } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const listSeasons = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
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

// Le shell est un composant client testé pour lui-même (`components/mon-espace/MonEspace.test.tsx`) :
// ici on ne vérifie que ce que la page lui transmet.
vi.mock("@/components/mon-espace/MonEspace", () => ({
  MonEspace: ({ seasons, federalOnly }: { seasons: number[]; federalOnly: boolean }) => (
    <div data-testid="mon-espace-stub" data-seasons={seasons.join(",")} data-federal-only={String(federalOnly)} />
  ),
}));

import MonEspacePage from "./page";

const SEASONS = [
  { start_year: 2026, label: "Saison 2026", event_count: 5, participation_count: 42, is_current: true },
  { start_year: 2025, label: "Saison 2025", event_count: 3, participation_count: 20, is_current: false },
];

beforeEach(() => {
  vi.clearAllMocks();
  url.qs = "";
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

  it("demande une fenêtre de revalidation courte sur les appels (#352)", async () => {
    await renderDashboard({});

    expect(listSeasons).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
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

});

describe("MonEspacePage: shell", () => {
  it("mounts the client shell with the selected seasons and the discipline filter", async () => {
    await renderDashboard({ seasons: "2025", sports: "all" });

    const shell = screen.getByTestId("mon-espace-stub");
    expect(shell).toHaveAttribute("data-seasons", "2025");
    expect(shell).toHaveAttribute("data-federal-only", "false");
  });

  it("defaults to the federal filter", async () => {
    await renderDashboard({});

    expect(screen.getByTestId("mon-espace-stub")).toHaveAttribute("data-federal-only", "true");
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
