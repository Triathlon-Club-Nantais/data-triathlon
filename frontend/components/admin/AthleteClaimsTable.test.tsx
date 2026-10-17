import { QueryClient, QueryClientProvider, onlineManager } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AthleteClaimReview } from "@/lib/types";

const { getAthleteClaims, approveAthleteClaim, rejectAthleteClaim } = vi.hoisted(() => ({
  getAthleteClaims: vi.fn(),
  approveAthleteClaim: vi.fn(),
  rejectAthleteClaim: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getAthleteClaims, approveAthleteClaim, rejectAthleteClaim } };
});

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { AthleteClaimsTable } from "./AthleteClaimsTable";
import { rendreAvecRelanceSuspendue } from "@/test/requete-suspendue";

const DEMANDE: AthleteClaimReview = {
  id: 7,
  created_at: "2026-10-17T10:00:00Z",
  user: { id: 12, display_name: "Léa M.", email: "lea@exemple.fr" },
  athlete: { id: 42, prenom: "Léa", nom: "Martin", club: "TRIATHLON CLUB NANTAIS" },
  licensee: { prenom: "Léa", nom: "MARTIN", season: 2026 },
  email_on_member_list: true,
  linked_accounts: 1,
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AthleteClaimsTable />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  getAthleteClaims.mockReset();
  approveAthleteClaim.mockReset();
  rejectAthleteClaim.mockReset();
});

describe("AthleteClaimsTable (#1325)", () => {
  it("shows each claim with its hints", async () => {
    getAthleteClaims.mockResolvedValue([DEMANDE]);
    afficher();

    const ligne = (await screen.findByText("lea@exemple.fr")).closest("tr") as HTMLElement;
    expect(within(ligne).getByRole("link", { name: "Léa Martin" })).toHaveAttribute("href", "/athletes/42");
    expect(ligne).toHaveTextContent("Licencié 2026 : Léa MARTIN");
    expect(ligne).toHaveTextContent("Adresse sur la liste d'adhérents");
    expect(ligne).toHaveTextContent("1 compte déjà rattaché");
  });

  it("says what is missing when no hint backs the claim", async () => {
    getAthleteClaims.mockResolvedValue([
      { ...DEMANDE, licensee: null, email_on_member_list: false, linked_accounts: 0 },
    ]);
    afficher();

    const ligne = (await screen.findByText("lea@exemple.fr")).closest("tr") as HTMLElement;
    expect(ligne).toHaveTextContent("Aucun licencié de la saison");
    expect(ligne).toHaveTextContent("Adresse absente de la liste d'adhérents");
    expect(ligne).not.toHaveTextContent("déjà rattaché");
  });

  it("approves and rejects", async () => {
    getAthleteClaims.mockResolvedValue([DEMANDE]);
    approveAthleteClaim.mockResolvedValue(null);
    rejectAthleteClaim.mockResolvedValue(null);
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Valider la demande de Léa M." }));
    await waitFor(() => expect(approveAthleteClaim).toHaveBeenCalledWith(7));
    await userEvent.click(screen.getByRole("button", { name: "Refuser la demande de Léa M." }));
    await waitFor(() => expect(rejectAthleteClaim).toHaveBeenCalledWith(7));
  });

  it("says the queue is empty", async () => {
    getAthleteClaims.mockResolvedValue([]);
    afficher();

    expect(await screen.findByText(/aucune demande de rattachement/i)).toBeInTheDocument();
  });

  it("says access is denied on a 403, not an empty queue", async () => {
    getAthleteClaims.mockRejectedValue(new ApiError(403, "Refusé"));
    afficher();

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
    expect(screen.queryByText(/aucune demande/i)).not.toBeInTheDocument();
  });

  it("does not take a query paused offline for an empty queue (#1294)", async () => {
    // `retry: false` : sans relance, seule la perte du réseau suspend la liste.
    onlineManager.setOnline(false);
    onTestFinished(() => onlineManager.setOnline(true));
    getAthleteClaims.mockResolvedValue([]);
    await rendreAvecRelanceSuspendue(<AthleteClaimsTable />, ["athlete-claims"]);

    expect(screen.queryByText(/aucune demande/i)).not.toBeInTheDocument();
  });
});
