import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AthleteMergeImpact } from "@/lib/types";

const { getAthleteMergeImpact, mergeAthletes, toastError, toastSuccess } = vi.hoisted(() => ({
  getAthleteMergeImpact: vi.fn(),
  mergeAthletes: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getAthleteMergeImpact, mergeAthletes } };
});

import { MergeAthletesDialog } from "./MergeAthletesDialog";

const DUPONT = { id: 7, nom: "DUPONT", prenom: "Jean", club: "Triathlon Club Nantais", participations: 14 };
const DUPOMT = { id: 9, nom: "DUPOMT", prenom: "Jean", club: null, participations: 1 };

const IMPACT: AthleteMergeImpact = {
  kept: DUPONT,
  absorbed: DUPOMT,
  moves: { participations: 1, teammates: 0, volunteer_actions: 0, season_validations: 1, users: 0 },
  alias_added: true,
  blocking_reason: null,
  blocking_label: null,
};

function afficher(onMerged = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MergeAthletesDialog athleteA={DUPONT} athleteB={DUPOMT} open onOpenChange={() => {}} onMerged={onMerged} />
    </QueryClientProvider>,
  );
  return onMerged;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("MergeAthletesDialog", () => {
  it("présente les deux fiches sans aperçu, fusion inerte tant qu'aucune n'est choisie", async () => {
    afficher();

    expect(await screen.findByRole("button", { name: /garder dupont jean/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /garder dupomt jean/i })).toBeInTheDocument();
    expect(getAthleteMergeImpact).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /^fusionner$/i })).toBeDisabled();
  });

  it("choisir la fiche conservée charge l'aperçu de ce qui passera sur elle", async () => {
    getAthleteMergeImpact.mockResolvedValue(IMPACT);
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: /garder dupont jean/i }));

    expect(getAthleteMergeImpact).toHaveBeenCalledWith(7, 9);
    const apercu = await screen.findByRole("list");
    expect(apercu).toHaveTextContent(/1 résultat et 0 place d'équipier/i);
    expect(screen.getByText(/1 validation de saison/i)).toBeInTheDocument();
    expect(screen.getByText(/« DUPOMT Jean » sera reconnue/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^fusionner$/i })).toBeEnabled();
  });

  it("une fusion refusée le dit avant le clic, bouton inerte", async () => {
    getAthleteMergeImpact.mockResolvedValue({
      ...IMPACT,
      blocking_reason: "same_course_bibs",
      blocking_label: "Les deux fiches ont chacune un résultat sur une même épreuve individuelle : ce sont deux personnes.",
    });
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: /garder dupont jean/i }));

    expect(await screen.findByText(/ce sont deux personnes/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^fusionner$/i })).toBeDisabled();
  });

  it("confirmer fusionne, annonce le résultat et rend la fiche conservée", async () => {
    getAthleteMergeImpact.mockResolvedValue(IMPACT);
    mergeAthletes.mockResolvedValue({ ...DUPONT, birth_date: null, gender: "M", participations: 15 });
    const onMerged = afficher();

    await userEvent.click(await screen.findByRole("button", { name: /garder dupont jean/i }));
    await userEvent.click(await screen.findByRole("button", { name: /^fusionner$/i }));

    await waitFor(() => expect(mergeAthletes).toHaveBeenCalledWith(7, 9));
    expect(toastSuccess).toHaveBeenCalledWith(expect.stringMatching(/fusionnée dans « DUPONT Jean »/));
    expect(onMerged).toHaveBeenCalledWith(7);
  });

  it("un refus du serveur s'affiche en toast, sans fermer ni rien promettre", async () => {
    getAthleteMergeImpact.mockResolvedValue(IMPACT);
    mergeAthletes.mockRejectedValue(new ApiError(409, "Cette fiche est en cours d'import. Réessayez dans un instant."));
    const onMerged = afficher();

    await userEvent.click(await screen.findByRole("button", { name: /garder dupomt jean/i }));
    await userEvent.click(await screen.findByRole("button", { name: /^fusionner$/i }));

    await waitFor(() => expect(toastError).toHaveBeenCalledWith(expect.stringMatching(/en cours d'import/)));
    expect(onMerged).not.toHaveBeenCalled();
  });

  it("un aperçu illisible n'active pas la fusion", async () => {
    getAthleteMergeImpact.mockRejectedValue(new ApiError(500, "boom"));
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: /garder dupont jean/i }));

    expect(await screen.findByText(/n'a pas pu être chiffrée/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^fusionner$/i })).toBeDisabled();
  });
});
