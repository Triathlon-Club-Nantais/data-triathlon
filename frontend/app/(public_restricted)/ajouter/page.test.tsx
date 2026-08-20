import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

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

    expect(screen.getByRole("heading", { level: 1, name: "Ajouter un triathlon" })).toBeInTheDocument();
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
});
