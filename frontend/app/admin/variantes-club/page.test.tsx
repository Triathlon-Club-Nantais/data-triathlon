// frontend/app/admin/variantes-club/page.test.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ApiError } from "@/lib/api/client";

const { useClubAliases } = vi.hoisted(() => ({ useClubAliases: vi.fn() }));

vi.mock("@/lib/queries/admin", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/queries/admin")>();
  return { ...original, useClubAliases };
});

import AdminVariantesClubPage from "./page";

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AdminVariantesClubPage />
    </QueryClientProvider>,
  );
}

describe("AdminVariantesClubPage", () => {
  it("dit le refus une seule fois, sans offrir de formulaire", () => {
    useClubAliases.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new ApiError(403, "Interdit"),
    });

    afficher();

    expect(screen.getAllByText(/accès refusé/i)).toHaveLength(1);
    expect(screen.queryByRole("button", { name: /ajouter/i })).not.toBeInTheDocument();
  });

  it("monte la carte quand la lecture passe", () => {
    useClubAliases.mockReturnValue({
      data: { entries: [] },
      isLoading: false,
      error: null,
    });

    afficher();

    expect(screen.getByText("Variantes de libellé de club")).toBeInTheDocument();
  });
});
