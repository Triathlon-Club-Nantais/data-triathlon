import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Feedback } from "@/lib/types";

const { listFeedback } = vi.hoisted(() => ({ listFeedback: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listFeedback },
  };
});

import AdminFeedbackPage from "./page";

const SIGNALEMENT: Feedback = {
  id: 1,
  type: "bug",
  title: "Le classement n'affiche pas mon temps",
  body: "Détail",
  page_url: null,
  user_agent: null,
  status: "nouveau",
  github_url: null,
  created_at: "2026-08-01T14:54:28Z",
  email: null,
};

/**
 * Garde d'accès : non re-testée ici. `app/admin/layout.tsx` couvre déjà toutes
 * les sous-routes de `/admin` (FR-040, `layout.test.tsx`) — aucune autre page
 * de `app/admin/*` ne porte son propre test de garde.
 */
describe("AdminFeedbackPage", () => {
  beforeEach(() => {
    listFeedback.mockReset();
    listFeedback.mockResolvedValue([SIGNALEMENT]);
  });

  it("affiche la liste des retours utilisateurs", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <AdminFeedbackPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText(SIGNALEMENT.title)).toBeInTheDocument();
  });
});
