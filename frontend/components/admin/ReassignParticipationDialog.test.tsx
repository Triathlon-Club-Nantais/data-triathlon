import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AdminAthlete, Participation } from "@/lib/types";

const { searchAthletesAdmin, reassignParticipation, toastError, toastSuccess } = vi.hoisted(
  () => ({
    searchAthletesAdmin: vi.fn(),
    reassignParticipation: vi.fn(),
    toastError: vi.fn(),
    toastSuccess: vi.fn(),
  }),
);

vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { searchAthletesAdmin, reassignParticipation } };
});

import { ReassignParticipationDialog } from "./ReassignParticipationDialog";

const CIBLE: AdminAthlete = {
  id: 42,
  nom: "DUPONT",
  prenom: "Jean",
  birth_date: "1988-03-02",
  gender: "M",
  club: "TCN",
  participations: 3,
};

const RESULTAT = {
  id: 7,
  athlete: { id: 1, nom: "J. DUPONT", prenom: "", gender: "M", club: "TCN" },
  course: { id: 5, name: "Triathlon de Nantes" },
  total_time: "01:23:45",
} as unknown as Participation;

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ReassignParticipationDialog participation={RESULTAT} open onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
}

async function choisirLaCible() {
  await userEvent.type(screen.getByRole("searchbox"), "dupont");
  await userEvent.click(await screen.findByRole("button", { name: /DUPONT Jean/ }));
}

describe("ReassignParticipationDialog", () => {
  beforeEach(() => {
    searchAthletesAdmin.mockReset();
    reassignParticipation.mockReset();
    toastError.mockReset();
    toastSuccess.mockReset();
    searchAthletesAdmin.mockResolvedValue([CIBLE]);
  });

  it("n'offre pas de rattacher tant qu'aucune fiche n'est choisie", () => {
    afficher();

    expect(screen.getByRole("button", { name: /^rattacher/i })).toBeDisabled();
  });

  it("rattache le résultat à la fiche choisie", async () => {
    reassignParticipation.mockResolvedValue({});

    afficher();
    await choisirLaCible();
    await userEvent.click(screen.getByRole("button", { name: /^rattacher/i }));

    await waitFor(() =>
      expect(reassignParticipation).toHaveBeenCalledWith(7, 42),
    );
  });

  it("dit en français qu'un coureur est déjà classé sur cette épreuve", async () => {
    reassignParticipation.mockRejectedValue(
      new ApiError(409, "Ce coureur a déjà un résultat sur cette épreuve."),
    );

    afficher();
    await choisirLaCible();
    await userEvent.click(screen.getByRole("button", { name: /^rattacher/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "Ce coureur a déjà un résultat sur cette épreuve.",
      ),
    );
  });

  it("prévient que le geste est irréversible", async () => {
    afficher();

    expect(screen.getByText(/irréversible/i)).toBeInTheDocument();
  });
});
