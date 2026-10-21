import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { queryKeys } from "@/lib/queries/keys";
import type { ResultClaimReview } from "@/lib/types";

const { getResultClaims, approveResultClaim, rejectResultClaim, setParticipationTeammates, searchAthletesAdmin } =
  vi.hoisted(() => ({
    getResultClaims: vi.fn(),
    approveResultClaim: vi.fn(),
    rejectResultClaim: vi.fn(),
    setParticipationTeammates: vi.fn(),
    searchAthletesAdmin: vi.fn(),
  }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { getResultClaims, approveResultClaim, rejectResultClaim, setParticipationTeammates, searchAthletesAdmin },
  };
});
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

import { ResultClaimsTable } from "./ResultClaimsTable";

const RECLAMATION: ResultClaimReview = {
  id: 4,
  created_at: "2026-10-19T10:00:00Z",
  user: { id: 12, display_name: "Léa M.", email: "lea@exemple.fr" },
  participation: {
    id: 5, course_id: 9, course_name: "Tri de Nantes", event_date: "2026-06-07", event_type: "triathlon-m",
    bib_number: "128", total_time: "2:30:00", club: "AUTRE CLUB", category: "SEF",
    is_relay: false, team_name: null, teammates: [],
  },
  current_athlete: { id: 7, prenom: "Léa", nom: "Martin", club: null },
  current_athlete_results: 1,
  claimant_athlete: { id: 42, prenom: "Léa", nom: "Martin", club: "TCN" },
  licensee: { prenom: "Léa", nom: "MARTIN", season: 2026 },
};

function afficher(permissions: string[] = ["athlete_claims:review"]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(queryKeys.session(), { id: 1, permissions, athlete: null });
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

describe("ResultClaimsTable, relais (#1739)", () => {
  const RELAIS: ResultClaimReview = {
    ...RECLAMATION,
    participation: { ...RECLAMATION.participation, is_relay: true, team_name: "Les Dauphins" },
    current_athlete: { id: 7, prenom: "", nom: "Les Dauphins", club: null },
  };
  const PAUL = { id: 8, prenom: "Paul", nom: "Durand" };
  const AVEC_EQUIPE: ResultClaimReview = {
    ...RELAIS,
    participation: { ...RELAIS.participation, teammates: [{ id: 7, prenom: "Jean", nom: "Dupont" }, PAUL] },
  };

  it("asks before replacing a team label that would be left without results", async () => {
    getResultClaims.mockResolvedValue([RELAIS]);
    approveResultClaim.mockResolvedValue(null);
    afficher();

    const ligne = (await screen.findByText("lea@exemple.fr")).closest("tr") as HTMLElement;
    expect(ligne).toHaveTextContent("Équipe : Les Dauphins");
    expect(ligne).toHaveTextContent("Fiche actuelle : Les Dauphins (n'aura plus aucun résultat, elle sera supprimée)");
    expect(ligne).not.toHaveTextContent("vidée par le déplacement");
    await userEvent.click(within(ligne).getByRole("button", { name: "Ajouter à l'équipe la fiche de Léa M." }));

    const confirmation = await screen.findByRole("dialog");
    expect(confirmation).toHaveTextContent("La fiche « Les Dauphins » sera supprimée, elle n'a plus d'autre résultat.");
    expect(approveResultClaim).not.toHaveBeenCalled();
    await userEvent.click(within(confirmation).getByRole("button", { name: "Ajouter à l'équipe" }));
    await waitFor(() => expect(approveResultClaim).toHaveBeenCalledWith(4));
  });

  it("adds the member beside a carrier who is a person, in one click", async () => {
    getResultClaims.mockResolvedValue([
      { ...RELAIS, participation: { ...RELAIS.participation, team_name: null }, current_athlete: { ...PAUL, club: null } },
    ]);
    approveResultClaim.mockResolvedValue(null);
    afficher();

    const ligne = (await screen.findByText("lea@exemple.fr")).closest("tr") as HTMLElement;
    expect(ligne).toHaveTextContent("Équipe : nom inconnu");
    expect(ligne).toHaveTextContent("Fiche actuelle : Paul Durand (gardée dans l'équipe)");
    await userEvent.click(within(ligne).getByRole("button", { name: "Ajouter à l'équipe la fiche de Léa M." }));

    await waitFor(() => expect(approveResultClaim).toHaveBeenCalledWith(4));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("only validates when the member is already in the team", async () => {
    getResultClaims.mockResolvedValue([
      { ...AVEC_EQUIPE, participation: { ...AVEC_EQUIPE.participation, teammates: [PAUL, { id: 42, prenom: "Léa", nom: "Martin" }] } },
    ]);
    approveResultClaim.mockResolvedValue(null);
    afficher(["athlete_claims:review", "participations:reassign"]);

    const ligne = (await screen.findByText("lea@exemple.fr")).closest("tr") as HTMLElement;
    expect(within(ligne).queryByRole("button", { name: /Attribuer aux équipiers/ })).not.toBeInTheDocument();
    await userEvent.click(within(ligne).getByRole("button", { name: "Valider la réclamation de Léa M." }));

    await waitFor(() => expect(approveResultClaim).toHaveBeenCalledWith(4));
  });

  it("adds the member to a composed relay in one click, without the reassign permission", async () => {
    getResultClaims.mockResolvedValue([AVEC_EQUIPE]);
    approveResultClaim.mockResolvedValue(null);
    afficher();

    const ligne = (await screen.findByText("lea@exemple.fr")).closest("tr") as HTMLElement;
    const actuels = within(ligne).getByRole("list", { name: "Équipiers actuels" });
    expect(within(actuels).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["Jean Dupont", "Paul Durand"]);
    await userEvent.click(within(ligne).getByRole("button", { name: "Ajouter à l'équipe la fiche de Léa M." }));

    await waitFor(() => expect(approveResultClaim).toHaveBeenCalledWith(4));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
