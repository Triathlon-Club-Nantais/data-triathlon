import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ValidationQueueHistory } from "@/lib/types";

const { getValidationQueueHistory } = vi.hoisted(() => ({ getValidationQueueHistory: vi.fn() }));
vi.mock("@/lib/api/client", async (originale) => {
  const reel = await originale<typeof import("@/lib/api/client")>();
  return { ...reel, apiClient: { getValidationQueueHistory } };
});

import { ValidationBacklogChart } from "./ValidationBacklogChart";

function historique(overrides: Partial<ValidationQueueHistory> = {}): ValidationQueueHistory {
  return {
    backlog_by_day: [
      { date: "2026-08-24", pending_count: 2 },
      { date: "2026-08-25", pending_count: 3 },
      { date: "2026-08-26", pending_count: 1 },
    ],
    average_resolution_seconds: 7200,
    ...overrides,
  };
}

describe("ValidationBacklogChart", () => {
  it("affiche un état vide explicite sans résolution post-migration", async () => {
    getValidationQueueHistory.mockResolvedValue(historique({ backlog_by_day: [], average_resolution_seconds: null }));
    render(<ValidationBacklogChart />);

    expect(
      await screen.findByText(/pas encore d.historique de résolution/i)
    ).toBeInTheDocument();
  });

  it("affiche le graphique d'arriéré et le délai moyen en chiffre", async () => {
    getValidationQueueHistory.mockResolvedValue(historique());
    render(<ValidationBacklogChart />);

    expect(await screen.findByRole("img", { name: /arriéré de la file/i })).toBeInTheDocument();
    expect(screen.getByText(/2 h/i)).toBeInTheDocument();
  });

  it("ne rend rien si l'historique ne peut pas être chargé — composant secondaire, pas de blocage de la page", async () => {
    getValidationQueueHistory.mockRejectedValue(new Error("panne"));
    const { container } = render(<ValidationBacklogChart />);

    await vi.waitFor(() => expect(getValidationQueueHistory).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
