import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";

const { useClubMembers } = vi.hoisted(() => ({ useClubMembers: vi.fn() }));

vi.mock("@/lib/queries/admin", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/queries/admin")>();
  return { ...original, useClubMembers };
});

import AdminMembresPage from "./page";

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AdminMembresPage />
    </QueryClientProvider>,
  );
}

describe("AdminMembresPage", () => {
  it("dit le refus une seule fois, sans offrir de geste", () => {
    useClubMembers.mockReturnValue({ data: undefined, isLoading: false, error: new ApiError(403, "Interdit") });

    afficher();

    expect(screen.getAllByText(/accès refusé/i)).toHaveLength(1);
    expect(screen.queryByRole("button", { name: /relire la liste fftri/i })).not.toBeInTheDocument();
  });

  it("annonce les compteurs de la saison et les licenciés à rattacher", () => {
    useClubMembers.mockReturnValue({
      data: {
        season: 2026, seasons: [2026], total: 2, linked: 1, unlinked: 1, ambiguous: 0,
        members: [
          { id: 1, season: 2026, licence_id: "C1", nom: "MARTIN", prenom: "Anne", gender: "F",
            athlete_id: 5, link_status: "auto", source: "fftri" },
          { id: 2, season: 2026, licence_id: "C2", nom: "DURAND", prenom: "Paul", gender: "M",
            athlete_id: null, link_status: "unlinked", source: "fftri" },
        ],
      },
      isLoading: false,
      error: null,
    });

    afficher();

    expect(screen.getByText(/1 rattaché/i)).toBeInTheDocument();
    expect(screen.getByText("DURAND Paul")).toBeInTheDocument();
    expect(screen.queryByText("MARTIN Anne")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /relire la liste fftri/i })).toBeInTheDocument();
  });
});
