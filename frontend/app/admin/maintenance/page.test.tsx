import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { SessionUser } from "@/lib/types";

const { getSession } = vi.hoisted(() => ({ getSession: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getSession } };
});

import AdminMaintenancePage from "./page";

function session(permissions: string[]): SessionUser {
  return {
    id: 1,
    email: "admin@exemple.fr",
    display_name: "Admin",
    created_at: "2026-01-01T00:00:00Z",
    permissions,
    roles: [],
    groups: [],
  };
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AdminMaintenancePage />
    </QueryClientProvider>,
  );
}

/**
 * `layout.tsx` couvre l'accès à `/admin` — non re-testé ici (même réserve
 * que `retours-utilisateurs/page.test.tsx`). Ce que ce fichier couvre, et que
 * rien d'autre ne couvrait : le grain des deux pouvoirs `*:wipe_all`, qu'une
 * session peut porter un pouvoir d'admin sans porter (#499, revue finale
 * Important #3).
 */
describe("AdminMaintenancePage", () => {
  beforeEach(() => {
    getSession.mockReset();
  });

  it("dit que l'écran est en consultation à une session sans aucun des deux pouvoirs de purge", async () => {
    getSession.mockResolvedValue(session(["courses:sources"]));

    afficher();

    expect(
      await screen.findByText(/cet écran est en consultation/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /supprimer toutes les épreuves/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /purger tous les résultats/i })).not.toBeInTheDocument();
  });

  it("ne dit rien à un porteur de courses:wipe_all", async () => {
    getSession.mockResolvedValue(session(["courses:wipe_all"]));

    afficher();

    expect(
      await screen.findByRole("button", { name: /supprimer toutes les épreuves/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/cet écran est en consultation/i)).not.toBeInTheDocument();
  });

  it("ne dit rien à un porteur de participations:wipe_all seul", async () => {
    getSession.mockResolvedValue(session(["participations:wipe_all"]));

    afficher();

    await screen.findByText(/purger les résultats/i); // le titre de sa propre carte
    expect(screen.queryByText(/cet écran est en consultation/i)).not.toBeInTheDocument();
  });
});
