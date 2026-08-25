import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { AdminActionLogPage as AdminActionLogPageData } from "@/lib/types";

const { getActionLog } = vi.hoisted(() => ({ getActionLog: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getActionLog } };
});

import AdminJournalPage from "./page";

const PAGE: AdminActionLogPageData = {
  entries: [
    {
      id: 1,
      created_at: "2026-08-20T10:15:00Z",
      user_name: "Jean Dupont",
      action: "course.delete",
      entity_type: "course",
      entity_id: 42,
      payload: { name: "Triathlon de Nantes" },
    },
  ],
  total: 1,
};

/**
 * Garde d'accès : non re-testée ici, comme toute autre page de `app/admin/*`
 * (`app/admin/layout.tsx` la couvre déjà — voir `retours-utilisateurs/page.test.tsx`).
 */
describe("AdminJournalPage", () => {
  beforeEach(() => {
    getActionLog.mockReset();
    getActionLog.mockResolvedValue(PAGE);
  });

  it("affiche le journal", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <AdminJournalPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText(/Triathlon de Nantes/)).toBeInTheDocument();
  });
});
