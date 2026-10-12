import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";

const { useMemberEmails } = vi.hoisted(() => ({ useMemberEmails: vi.fn() }));

vi.mock("@/lib/queries/admin", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/queries/admin")>();
  return { ...original, useMemberEmails };
});

import AdminAdressesAdherentsPage from "./page";

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <AdminAdressesAdherentsPage />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

describe("AdminAdressesAdherentsPage", () => {
  it("states the refusal once, without offering any action", () => {
    useMemberEmails.mockReturnValue({ data: undefined, isLoading: false, error: new ApiError(403, "Interdit") });

    afficher();

    expect(screen.getAllByText(/accès refusé/i)).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Importer" })).not.toBeInTheDocument();
  });

  it("renders the season's list", () => {
    useMemberEmails.mockReturnValue({
      data: {
        season: 2026, counting_season: 2026, seasons: [2026],
        entries: [{ id: 1, email: "anne@exemple.fr", season: 2026, source: "import", created_at: "" }],
      },
      isLoading: false,
      error: null,
    });

    afficher();

    expect(screen.getByRole("heading", { level: 1, name: "Adresses d'adhérents" })).toBeInTheDocument();
    expect(screen.getByText("anne@exemple.fr")).toBeInTheDocument();
  });
});
