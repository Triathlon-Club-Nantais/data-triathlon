import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AdminActionLogPage } from "@/lib/types";

const { getActionLog } = vi.hoisted(() => ({ getActionLog: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getActionLog } };
});

import { AdminActionLogTable } from "./AdminActionLogTable";

function page(overrides: Partial<AdminActionLogPage> = {}): AdminActionLogPage {
  return {
    entries: [
      {
        id: 1,
        created_at: "2026-08-20T10:15:00Z",
        user_name: "Jean Dupont",
        action: "course.delete",
        entity_type: "course",
        entity_id: 42,
        payload: { name: "Triathlon de Nantes", participations_deleted: 179 },
      },
    ],
    total: 1,
    ...overrides,
  };
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { client, ...render(
    <QueryClientProvider client={client}>
      <AdminActionLogTable />
    </QueryClientProvider>,
  ) };
}

describe("AdminActionLogTable", () => {
  beforeEach(() => {
    getActionLog.mockReset();
  });

  it("affiche une entrée traduite", async () => {
    getActionLog.mockResolvedValue(page());

    afficher();

    expect(await screen.findByText("Suppression d'une épreuve")).toBeInTheDocument();
    expect(screen.getByText("Jean Dupont")).toBeInTheDocument();
    expect(screen.getByText(/Triathlon de Nantes/)).toBeInTheDocument();
  });

  it("affiche un état vide", async () => {
    getActionLog.mockResolvedValue(page({ entries: [], total: 0 }));

    afficher();

    expect(await screen.findByText(/aucune entrée/i)).toBeInTheDocument();
  });

  it("dit en français qu'un refus a empêché la lecture", async () => {
    getActionLog.mockRejectedValue(new ApiError(403, "Vous n'avez pas les droits nécessaires."));

    afficher();

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
  });

  it("désactive « Précédent » sur la première page et pagine vers la suivante", async () => {
    getActionLog.mockResolvedValue(page({ total: 45 }));

    afficher();
    await screen.findByText("Suppression d'une épreuve");

    expect(screen.getByRole("button", { name: /précédent/i })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: /suivant/i }));

    await waitFor(() => expect(getActionLog).toHaveBeenCalledWith(2, expect.any(Number)));
  });
});
