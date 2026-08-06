import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AdminAthlete } from "@/lib/types";

const { updateAthlete, toastError, toastSuccess } = vi.hoisted(() => ({
  updateAthlete: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { updateAthlete } };
});

import { EditAthleteDialog } from "./EditAthleteDialog";

const COUREUR: AdminAthlete = {
  id: 42,
  nom: "DUPOND",
  prenom: "Jean",
  birth_date: "1988-03-02",
  gender: "M",
  club: "TCN",
  participations: 3,
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <EditAthleteDialog athlete={COUREUR} open onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
}

describe("EditAthleteDialog", () => {
  beforeEach(() => {
    updateAthlete.mockReset();
    toastError.mockReset();
    toastSuccess.mockReset();
  });

  it("propose le triplet d'identité, et lui seul", () => {
    afficher();

    expect(screen.getByLabelText(/^nom/i)).toHaveValue("DUPOND");
    expect(screen.getByLabelText(/prénom/i)).toHaveValue("Jean");
    expect(screen.getByLabelText(/naissance/i)).toHaveValue("1988-03-02");
    expect(screen.queryByLabelText(/club/i)).not.toBeInTheDocument();
  });

  it("enregistre la correction", async () => {
    updateAthlete.mockResolvedValue(COUREUR);

    afficher();
    const nom = screen.getByLabelText(/^nom/i);
    await userEvent.clear(nom);
    await userEvent.type(nom, "DUPONT");
    await userEvent.click(screen.getByRole("button", { name: /enregistrer/i }));

    await waitFor(() =>
      expect(updateAthlete).toHaveBeenCalledWith(
        42,
        expect.objectContaining({ nom: "DUPONT" }),
      ),
    );
  });

  it("montre en français la fiche en conflit, sans vider le formulaire", async () => {
    updateAthlete.mockRejectedValue(
      new ApiError(409, "Un coureur porte déjà cette identité (fiche #7)."),
    );

    afficher();
    const nom = screen.getByLabelText(/^nom/i);
    await userEvent.clear(nom);
    await userEvent.type(nom, "DUPONT");
    await userEvent.click(screen.getByRole("button", { name: /enregistrer/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "Un coureur porte déjà cette identité (fiche #7).",
      ),
    );
    expect(screen.getByLabelText(/^nom/i)).toHaveValue("DUPONT");
  });
});
