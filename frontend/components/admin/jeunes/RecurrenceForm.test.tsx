import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { TrainingRecurrence } from "@/lib/types";

const { toast } = vi.hoisted(() => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("sonner", () => ({ toast }));

const {
  listTrainingRecurrences,
  previewTrainingRecurrence,
  createTrainingRecurrence,
  updateTrainingRecurrence,
  deleteTrainingRecurrence,
} = vi.hoisted(() => ({
  listTrainingRecurrences: vi.fn(),
  previewTrainingRecurrence: vi.fn(),
  createTrainingRecurrence: vi.fn(),
  updateTrainingRecurrence: vi.fn(),
  deleteTrainingRecurrence: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      listTrainingRecurrences,
      previewTrainingRecurrence,
      createTrainingRecurrence,
      updateTrainingRecurrence,
      deleteTrainingRecurrence,
    },
  };
});

import { ApiError } from "@/lib/api/client";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { RecurrencesSection } from "./RecurrenceForm";

const GROUPES = [{ id: 7, name: "Benjamins", member_count: 3 }];

const RECURRENCE: TrainingRecurrence = {
  id: 3,
  weekday: 2,
  start_time: "14:00:00",
  location: "Piscine",
  session_type: null,
  starts_on: "2026-10-01",
  ends_on: "2026-11-30",
  group_ids: [7],
  upcoming_session_count: 6,
};

function afficher(peutEcrire = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <RecurrencesSection groupes={GROUPES} peutEcrire={peutEcrire} />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

async function remplir() {
  await userEvent.click(await screen.findByRole("button", { name: "Nouvelle récurrence" }));
  const dialog = await screen.findByRole("dialog");
  await userEvent.selectOptions(within(dialog).getByLabelText("Jour"), "2");
  await userEvent.type(within(dialog).getByLabelText("Heure"), "14:00");
  await userEvent.type(within(dialog).getByLabelText("Du"), "2026-10-01");
  await userEvent.type(within(dialog).getByLabelText("Au"), "2026-11-30");
  await userEvent.click(within(dialog).getByRole("checkbox", { name: "Benjamins" }));
  return dialog;
}

describe("RecurrencesSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listTrainingRecurrences.mockResolvedValue([RECURRENCE]);
  });

  it("décrit les récurrences existantes", async () => {
    afficher();

    expect(await screen.findByText(/Chaque mercredi à 14:00/)).toBeInTheDocument();
    expect(screen.getByText(/6 séances à venir/)).toBeInTheDocument();
  });

  it("annonce le nombre de séances avant de créer la récurrence", async () => {
    previewTrainingRecurrence.mockResolvedValue({ occurrence_count: 9, dates: [] });
    createTrainingRecurrence.mockResolvedValue({ ...RECURRENCE, created_session_count: 9 });
    afficher();
    const dialog = await remplir();

    expect(await within(dialog).findByText("9 séances seront créées.")).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Créer les séances" }));

    await waitFor(() =>
      expect(createTrainingRecurrence).toHaveBeenCalledWith({
        weekday: 2,
        start_time: "14:00:00",
        location: null,
        session_type: null,
        starts_on: "2026-10-01",
        ends_on: "2026-11-30",
        group_ids: [7],
      }),
    );
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("9 séances créées."));
  });

  it("affiche lisiblement le refus de l'aperçu et bloque la création", async () => {
    previewTrainingRecurrence.mockRejectedValue(
      new ApiError(422, "Une récurrence compte au plus 53 séances : raccourcissez la période."),
    );
    afficher();
    const dialog = await remplir();

    expect(await within(dialog).findByText(/au plus 53 séances/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Créer les séances" })).toBeDisabled();
  });

  it("supprime une récurrence après une confirmation qui chiffre les séances à venir", async () => {
    deleteTrainingRecurrence.mockResolvedValue({ deleted_session_count: 6, kept_session_count: 2 });
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Supprimer la récurrence" }));
    const confirmation = await screen.findByRole("dialog", { name: "Supprimer la récurrence ?" });
    expect(within(confirmation).getByText(/6 séances à venir seront supprimées/)).toBeInTheDocument();
    await userEvent.click(within(confirmation).getByRole("button", { name: "Supprimer la récurrence" }));

    await waitFor(() => expect(deleteTrainingRecurrence).toHaveBeenCalledWith(3));
  });

  it("modifie l'heure d'une récurrence", async () => {
    previewTrainingRecurrence.mockResolvedValue({ occurrence_count: 9, dates: [] });
    updateTrainingRecurrence.mockResolvedValue(RECURRENCE);
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Modifier la récurrence" }));
    const dialog = await screen.findByRole("dialog");
    const heure = within(dialog).getByLabelText("Heure");
    await userEvent.clear(heure);
    await userEvent.type(heure, "15:00");
    await userEvent.click(within(dialog).getByRole("button", { name: "Enregistrer" }));

    await waitFor(() =>
      expect(updateTrainingRecurrence).toHaveBeenCalledWith(3, expect.objectContaining({ start_time: "15:00:00" })),
    );
  });

  it("ne propose aucun geste sans jeunes:write", async () => {
    afficher(false);

    await screen.findByText(/Chaque mercredi/);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
