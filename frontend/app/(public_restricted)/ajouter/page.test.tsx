import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { dansLesCartes } from "@/test/cartes";

const listEvents = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
    listEvents: (filters: unknown, fetchOpts?: unknown) => listEvents(filters, fetchOpts),
  },
  SHORT_REVALIDATE_SECONDS: 30,
}));

// TcnScrapeForm est un composant client lourd (routeur, requêtes, SSE) sans
// rapport avec ce qui est testé ici — le comportement de son propre fichier
// est couvert par ses propres tests.
vi.mock("@/components/scrape/TcnScrapeForm", () => ({
  TcnScrapeForm: () => null,
}));

import AjouterPage from "./page";

beforeEach(() => {
  vi.clearAllMocks();
  listEvents.mockResolvedValue({ items: [], total_events: 0, total_participations: 0 });
});

describe("AjouterPage", () => {
  it("demande une fenêtre de revalidation courte sur listEvents (#376)", async () => {
    const ui = await AjouterPage();
    render(ui);

    expect(listEvents).toHaveBeenCalledWith(
      { page_size: 6, sort: "imported_desc" },
      { revalidateSeconds: 30 },
    );
  });

  it("rend un titre <h1> et le titre de carte en <h2> (A11Y-2)", async () => {
    const ui = await AjouterPage();
    render(ui);

    expect(screen.getByRole("heading", { level: 1, name: "Ajouter une épreuve" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Derniers résultats enregistrés" }),
    ).toBeInTheDocument();
  });

  it("affiche un état vide quand il n'y a encore aucun résultat récent (ETAT-3)", async () => {
    // Pas d'action ici, à dessein : le formulaire d'import est juste au-dessus.
    const ui = await AjouterPage();
    render(ui);

    expect(screen.getByText("Aucun résultat enregistré pour l'instant")).toBeInTheDocument();
  });

  // ── Structure de tableau (#481, A11Y-3) ────────────────────────────────────

  const epreuve = {
    id: 7,
    event_name: "Triathlon de Mesquer",
    event_date: "2026-06-13",
    event_type: "triathlon-s",
    distance_km: null,
    is_relay: false,
    total: 120,
    tcn_count: 3,
  };

  it("s'annonce comme un tableau et nomme ses quatre colonnes", async () => {
    listEvents.mockResolvedValue({ items: [epreuve], total_events: 1, total_participations: 120 });
    render(await AjouterPage());

    expect(screen.getByRole("table")).toBeInTheDocument();
    for (const nom of ["Date", "Épreuve", "Format", "Athlètes club"]) {
      expect(screen.getByRole("columnheader", { name: nom })).toBeInTheDocument();
    }
    expect(screen.getAllByRole("row")).toHaveLength(2);
  });

  it("garde une ligne-lien vers l'épreuve, et un seul arrêt clavier par ligne", async () => {
    listEvents.mockResolvedValue({ items: [epreuve], total_events: 1, total_participations: 120 });
    render(await AjouterPage());

    const ligne = screen.getAllByRole("row")[1];
    expect(within(ligne).getByRole("link")).toHaveAttribute("href", "/courses/7");
    // FR-011 : le compte est **par `<tr>`**. Un `href` par cellule passerait
    // l'assertion ci-dessus et multiplierait les tabulations par quatre.
    expect(ligne.querySelectorAll("a[href], button, input, select, textarea")).toHaveLength(1);
  });

  it("garde son en-tête sur une liste vide, l'état vide restant hors du tableau", async () => {
    render(await AjouterPage());

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(1);
    expect(
      within(screen.getByRole("table")).queryByText("Aucun résultat enregistré pour l'instant"),
    ).not.toBeInTheDocument();
  });

  it("bascule la grille et les cartes aux seuils annoncés", async () => {
    const ui = await AjouterPage();
    render(ui);

    expect(screen.getByTestId("recents-grille").className).toContain("hidden sm:block");
    expect(screen.getByTestId("recents-cartes").className).toContain("sm:hidden");
  });

  it("porte date, épreuve et format dans la carte", async () => {
    listEvents.mockResolvedValue({
      items: [
        {
          id: 14,
          event_name: "Tri de Nantes",
          event_type: "triathlon-m",
          event_date: "2026-05-16",
          distance_km: null,
          is_relay: false,
          total: 148,
          tcn_count: 3,
        },
      ],
      total_events: 1,
      total_participations: 148,
    });
    const ui = await AjouterPage();
    render(ui);

    const carte = dansLesCartes("recents-cartes");
    expect(carte.getByRole("link", { name: /Tri de Nantes/ })).toHaveAttribute(
      "href",
      "/courses/14",
    );
    expect(carte.texte("16/05/2026")).toBeTruthy();
  });

  it("affiche un tiret dans la carte quand aucun membre du club n'a participé", async () => {
    listEvents.mockResolvedValue({
      items: [
        {
          id: 22,
          event_name: "Marathon de Paris",
          event_type: "run",
          event_date: "2026-04-12",
          distance_km: 42.195,
          is_relay: false,
          total: 5000,
          tcn_count: 0,
        },
      ],
      total_events: 1,
      total_participations: 5000,
    });
    const ui = await AjouterPage();
    render(ui);

    const carte = dansLesCartes("recents-cartes");
    expect(carte.texte("—")).toBeTruthy();
  });
});
