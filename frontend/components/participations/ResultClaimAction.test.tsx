import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Participation, SessionUser } from "@/lib/types";

const { getSession, getMyResultClaims, requestResultClaim, cancelResultClaim } = vi.hoisted(() => ({
  getSession: vi.fn(),
  getMyResultClaims: vi.fn(),
  requestResultClaim: vi.fn(),
  cancelResultClaim: vi.fn(),
}));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { ...original.apiClient, getSession, getMyResultClaims, requestResultClaim, cancelResultClaim },
  };
});

import { ResultClaimAction } from "./ResultClaimAction";

const LEA = { id: 42, prenom: "Léa", nom: "Martin" };
const HOMONYME = { id: 7, prenom: "Léa", nom: "Martin" };
const RESULTAT = {
  id: 5, athlete: HOMONYME, is_relay: false, is_pending_validation: false,
  course: { id: 9, name: "Tri de Nantes" },
} as unknown as Participation;

function session(athlete: SessionUser["athlete"]): SessionUser {
  return { id: 1, email: "lea@exemple.fr", permissions: [], roles: [], groups: [], athlete, athlete_claim: null } as unknown as SessionUser;
}

function afficher(participation: Participation = RESULTAT) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ResultClaimAction participation={participation} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  document.cookie = "tcn_logged_in=1; path=/";
  getSession.mockResolvedValue(session(LEA));
  getMyResultClaims.mockResolvedValue([]);
});

describe("ResultClaimAction (#1637)", () => {
  it("offers « Ce résultat est à moi » on another record's result, and sends the claim", async () => {
    requestResultClaim.mockResolvedValue({});
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Ce résultat est à moi" }));

    await waitFor(() => expect(requestResultClaim).toHaveBeenCalledWith(5, "result"));
    expect(screen.getByText(/le club vérifie puis déplace ce résultat sur votre fiche/i)).toBeInTheDocument();
  });

  it("shows a pending claim and lets the member cancel it", async () => {
    getMyResultClaims.mockResolvedValue([{ id: 3, participation_id: 5, status: "pending", created_at: "2026-10-19T10:00:00Z" }]);
    cancelResultClaim.mockResolvedValue(null);
    afficher();

    expect(await screen.findByText(/réclamation en attente/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Annuler la réclamation" }));
    await waitFor(() => expect(cancelResultClaim).toHaveBeenCalledWith(3));
  });

  it("says a claim was rejected and offers to ask again", async () => {
    getMyResultClaims.mockResolvedValue([{ id: 3, participation_id: 5, status: "rejected", created_at: "2026-10-19T10:00:00Z" }]);
    afficher();

    expect(await screen.findByText(/réclamation précédente a été refusée/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ce résultat est à moi" })).toBeInTheDocument();
  });

  it.each([
    ["the member's own result", session(LEA), { ...RESULTAT, athlete: LEA }],
    ["an account without a claimed record", session(null), RESULTAT],
    ["a pending result", session(LEA), { ...RESULTAT, is_pending_validation: true }],
    ["a relay", session(LEA), { ...RESULTAT, is_relay: true }],
  ])("offers nothing on %s", async (_, user, participation) => {
    getSession.mockResolvedValue(user);
    afficher(participation as Participation);

    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "Ce résultat est à moi" })).not.toBeInTheDocument();
  });
});
