import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

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
});
