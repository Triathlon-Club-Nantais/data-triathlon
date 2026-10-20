import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionUser } from "@/lib/types";

const { getSession, getMyResultClaims, cancelResultClaim } = vi.hoisted(() => ({
  getSession: vi.fn(), getMyResultClaims: vi.fn(), cancelResultClaim: vi.fn(),
}));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getSession, getMyResultClaims, cancelResultClaim } };
});

import { MesDemandes } from "./MesDemandes";

const LEA = { id: 42, prenom: "Léa", nom: "Martin" };
const claim = (extra = {}) => ({
  id: 3, participation_id: 5, course_id: 9, course_name: "Tri de Nantes", event_date: "2026-05-17",
  status: "pending", created_at: "2026-10-19T10:00:00Z", ...extra,
});

function session() {
  return { id: 1, athlete: LEA, permissions: [], roles: [], groups: [], athlete_claim: null } as unknown as SessionUser;
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MesDemandes /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  document.cookie = "tcn_logged_in=1; path=/";
  getSession.mockResolvedValue(session());
  getMyResultClaims.mockResolvedValue([]);
});

describe("MesDemandes (#1670)", () => {
  it("hides the card when there is no request", async () => {
    const { container } = afficher();
    await waitFor(() => expect(getMyResultClaims).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 0));
    expect(container).toBeEmptyDOMElement();
  });

  it("lists result claims with status and date", async () => {
    getMyResultClaims.mockResolvedValue([claim(), claim({ id: 4, status: "rejected", event_date: null })]);
    afficher();

    expect(await screen.findByRole("heading", { name: "Mes demandes" })).toBeInTheDocument();
    expect(await screen.findByText("En attente")).toBeInTheDocument();
    expect(await screen.findByText("Refusée")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tri de Nantes · 17/05/2026" })).toHaveAttribute("href", "/courses/9");
    expect(screen.getAllByText(/Demandée le 19\/10\/2026/)).toHaveLength(2);
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /Annuler la demande/ })).toHaveLength(1);
  });

  it("cancels a pending result claim after inline confirmation", async () => {
    getMyResultClaims.mockResolvedValue([claim(), claim({ id: 4, status: "rejected", course_name: "Autre" })]);
    cancelResultClaim.mockResolvedValue(null);
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: /Annuler la demande.*Tri de Nantes/ }));
    expect(cancelResultClaim).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /Confirmer.*Tri de Nantes/ }));

    await waitFor(() => expect(cancelResultClaim).toHaveBeenCalledWith(3));
    expect(screen.queryByRole("button", { name: /Autre/ })).not.toBeInTheDocument();
  });

  it("shows the error when cancelling fails", async () => {
    getMyResultClaims.mockResolvedValue([claim()]);
    cancelResultClaim.mockRejectedValue(new Error("Cette demande a déjà été traitée."));
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: /Annuler la demande/ }));
    await userEvent.click(screen.getByRole("button", { name: /Confirmer/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Cette demande a déjà été traitée.");
    await waitFor(() => expect(getMyResultClaims).toHaveBeenCalledTimes(2));
  });
});
