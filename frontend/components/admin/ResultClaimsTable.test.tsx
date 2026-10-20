import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ResultClaimReview } from "@/lib/types";

const { getResultClaims, approveResultClaim, rejectResultClaim } = vi.hoisted(() => ({
  getResultClaims: vi.fn(),
  approveResultClaim: vi.fn(),
  rejectResultClaim: vi.fn(),
}));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getResultClaims, approveResultClaim, rejectResultClaim } };
});
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { ResultClaimsTable } from "./ResultClaimsTable";

const RECLAMATION: ResultClaimReview = {
  id: 4,
  kind: "result",
  created_at: "2026-10-19T10:00:00Z",
  user: { id: 12, display_name: "Léa M.", email: "lea@exemple.fr" },
  participation: {
    id: 5, course_id: 9, course_name: "Tri de Nantes", event_date: "2026-06-07", event_type: "triathlon-m",
    bib_number: "128", total_time: "2:30:00", club: "AUTRE CLUB", category: "SEF",
  },
  current_athlete: { id: 7, prenom: "Léa", nom: "Martin", club: null },
  current_athlete_results: 1,
  teammates: [],
  proposed_teammates: null,
  claimant_has_result_on_course: false,
  claimant_athlete: { id: 42, prenom: "Léa", nom: "Martin", club: "TCN" },
  licensee: { prenom: "Léa", nom: "MARTIN", season: 2026 },
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ResultClaimsTable />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("ResultClaimsTable (#1637)", () => {
  it("marks each row as a single result and shows where it is and where it would go", async () => {
    getResultClaims.mockResolvedValue([RECLAMATION]);
    afficher();

    const ligne = (await screen.findByText("lea@exemple.fr")).closest("tr") as HTMLElement;
    expect(within(ligne).getByText("Un résultat")).toBeInTheDocument();
    expect(within(ligne).getByRole("link", { name: "Tri de Nantes" })).toHaveAttribute(
      "href", "/courses/9/participations/5",
    );
    expect(ligne).toHaveTextContent("dossard 128");
    expect(ligne).toHaveTextContent("Fiche actuelle : Léa Martin");
    expect(ligne).toHaveTextContent("vidée par le déplacement");
    expect(ligne).toHaveTextContent("Vers : Léa Martin");
    expect(ligne).toHaveTextContent("Licencié 2026 : Léa MARTIN");
  });

  it("moves the result or refuses", async () => {
    getResultClaims.mockResolvedValue([RECLAMATION]);
    approveResultClaim.mockResolvedValue(null);
    rejectResultClaim.mockResolvedValue(null);
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Déplacer le résultat réclamé par Léa M." }));
    await waitFor(() => expect(approveResultClaim).toHaveBeenCalledWith(4));
    await userEvent.click(screen.getByRole("button", { name: "Refuser la réclamation de Léa M." }));
    await waitFor(() => expect(rejectResultClaim).toHaveBeenCalledWith(4));
  });

  it("says the queue is empty", async () => {
    getResultClaims.mockResolvedValue([]);
    afficher();

    expect(await screen.findByText(/aucun résultat réclamé/i)).toBeInTheDocument();
  });
});
