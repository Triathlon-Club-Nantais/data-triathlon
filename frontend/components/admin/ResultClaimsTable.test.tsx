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
import { toast } from "sonner";
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

vi.mock("@/components/athletes/TeammatesDialog", () => ({
  TeammatesDialog: ({ equipiers }: { equipiers: { prenom: string; nom: string }[] }) => (
    <div role="dialog">{equipiers.map((e) => `${e.prenom} ${e.nom}`).join("|")}</div>
  ),
}));

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

const EQUIPIERS = [
  { id: 1, prenom: "Ana", nom: "Roux" },
  { id: 2, prenom: "Bob", nom: "Lenoir" },
];
const EQUIPE: ResultClaimReview = {
  ...RECLAMATION,
  id: 8,
  kind: "team",
  teammates: EQUIPIERS,
  proposed_teammates: [...EQUIPIERS, { id: 42, prenom: "Léa", nom: "Martin" }],
  claimant_has_result_on_course: true,
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

  it("une_demande_d_equipe_montre_la_composition_proposee", async () => {
    getResultClaims.mockResolvedValue([EQUIPE]);
    afficher();

    const ligne = (await screen.findByText("lea@exemple.fr")).closest("tr") as HTMLElement;
    expect(within(ligne).getByText("Résultat d'équipe")).toBeInTheDocument();
    expect(ligne).toHaveTextContent("Équipe actuelle : Ana Roux, Bob Lenoir");
    expect(ligne).toHaveTextContent("Après validation : Ana Roux, Bob Lenoir, Léa Martin");
    const ajouter = within(ligne).getByRole("button", { name: /Ajouter à l.équipe/ });
    expect(ajouter).toBeDisabled();
    expect(ajouter).toHaveAccessibleDescription(
      "L'auteur de la demande a déjà un résultat sur cette épreuve : l'ajout serait refusé.",
    );
    expect(within(ligne).queryByRole("button", { name: /déplacer/i })).not.toBeInTheDocument();
  });

  it("ajouter_a_l_equipe_valide_la_demande", async () => {
    getResultClaims.mockResolvedValue([{ ...EQUIPE, claimant_has_result_on_course: false }]);
    approveResultClaim.mockResolvedValue(null);
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: /Ajouter à l.équipe/ }));
    await waitFor(() => expect(approveResultClaim).toHaveBeenCalledWith(8));
    expect(toast.success).toHaveBeenCalledWith("Ajouté à l'équipe.");
  });

  it("refuser_une_demande_d_equipe_annonce_demande_refusee", async () => {
    getResultClaims.mockResolvedValue([EQUIPE]);
    rejectResultClaim.mockResolvedValue(null);
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Refuser la réclamation de Léa M." }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Demande refusée."));
  });

  it("une_equipe_composee_a_la_main_ouvre_la_fenetre_preremplie", async () => {
    getResultClaims.mockResolvedValue([{ ...EQUIPE, proposed_teammates: null, claimant_has_result_on_course: false }]);
    approveResultClaim.mockResolvedValue(null);
    afficher();

    expect(await screen.findByText(/Composition posée à la main : composez l.équipe, puis closez la demande\./)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Ajouter à l.équipe/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Composer l'équipe (Léa M.)" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("Ana Roux|Bob Lenoir|Léa Martin");
    await userEvent.click(screen.getByRole("button", { name: "Clore la demande (Léa M.)" }));
    await waitFor(() => expect(approveResultClaim).toHaveBeenCalledWith(8));
    expect(toast.success).toHaveBeenCalledWith("Demande close.");
  });

  it("une_demande_de_resultat_reste_inchangee", async () => {
    getResultClaims.mockResolvedValue([RECLAMATION]);
    afficher();

    const ligne = (await screen.findByText("lea@exemple.fr")).closest("tr") as HTMLElement;
    expect(within(ligne).getByRole("button", { name: /Déplacer le résultat/ })).toBeInTheDocument();
    expect(within(ligne).queryByRole("button", { name: /Ajouter à l.équipe/ })).not.toBeInTheDocument();
    expect(ligne).not.toHaveTextContent("Équipe actuelle");
  });
});
