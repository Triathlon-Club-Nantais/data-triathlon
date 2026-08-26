import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ApiError } from "@/lib/api/client";

const { useCounterScope } = vi.hoisted(() => ({ useCounterScope: vi.fn() }));

vi.mock("@/lib/queries/admin", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/queries/admin")>();
  return { ...original, useCounterScope };
});

import AdminPorteeCompteursPage from "./page";

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AdminPorteeCompteursPage />
    </QueryClientProvider>,
  );
}

/**
 * Le refus se juge **ici** et non dans la carte : `counter_scope:manage` est le
 * pouvoir unique de la ressource, donc un refus de lecture rend l'écran entier
 * passif — et il ne doit ni se dire deux fois, ni laisser un formulaire actif.
 */
describe("AdminPorteeCompteursPage", () => {
  it("dit le refus une seule fois, sans offrir de geste", () => {
    useCounterScope.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new ApiError(403, "Interdit"),
    });

    afficher();

    expect(screen.getAllByText(/accès refusé/i)).toHaveLength(1);
    expect(screen.queryByRole("button", { name: /ajouter/i })).not.toBeInTheDocument();
  });

  it("monte les deux listes quand la lecture passe", () => {
    useCounterScope.mockReturnValue({
      data: { club_labels: [], disciplines: [] },
      isLoading: false,
      error: null,
    });

    afficher();

    expect(screen.getByText("Libellés comptés comme club")).toBeInTheDocument();
    expect(screen.getByText("Disciplines hors compteurs")).toBeInTheDocument();
  });
});
