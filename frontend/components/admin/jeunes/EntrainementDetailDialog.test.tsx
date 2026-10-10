import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Profile, TrainingSession, TrainingSessionDetail } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { getTrainingSession, updateTrainingSession, listProfiles, listTrainingGroups } = vi.hoisted(() => ({
  getTrainingSession: vi.fn(),
  updateTrainingSession: vi.fn(),
  listProfiles: vi.fn(),
  listTrainingGroups: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { getTrainingSession, updateTrainingSession, listProfiles, listTrainingGroups },
  };
});

import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { EntrainementDetailDialog } from "./EntrainementDetailDialog";

const SEANCE: TrainingSession = {
  id: 1,
  date: "2026-10-14",
  start_time: "14:00:00",
  location: "Piscine",
  session_type: null,
  note: "",
  participant_count: 0,
  group_ids: [7],
  recurrence_id: null,
  detached: false,
};

const ALIX: Profile = {
  id: 42,
  organisation_id: 1,
  first_name: "Alix",
  last_name: "Martin",
  birth_date: null,
  category: null,
  membership_ended_on: null,
  created_at: "2026-01-01T00:00:00Z",
};

const VIDE: TrainingSessionDetail = { ...SEANCE, participants: [] };
const INSCRITE: TrainingSessionDetail = {
  ...SEANCE,
  group_ids: [7, 8],
  participant_count: 1,
  participants: [
    { profile_id: 42, present: null, added_manually: false, category: null, created_at: "2026-10-10T10:00:00Z" },
  ],
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <EntrainementDetailDialog entrainement={SEANCE} peutEcrire open onOpenChange={vi.fn()} />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

describe("EntrainementDetailDialog, groupes visés (#1291)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listProfiles.mockResolvedValue([ALIX]);
    listTrainingGroups.mockResolvedValue([
      { id: 7, name: "Benjamins", member_count: 0 },
      { id: 8, name: "Minimes", member_count: 1 },
    ]);
    getTrainingSession.mockResolvedValue(VIDE);
  });

  it("coche les groupes déjà visés et en ajoute un second", async () => {
    updateTrainingSession.mockResolvedValue(INSCRITE);
    afficher();

    expect(await screen.findByRole("checkbox", { name: "Benjamins" })).toBeChecked();
    expect(screen.getByRole("dialog")).toHaveClass("max-h-[85dvh]", "overflow-y-auto");
    await userEvent.click(screen.getByRole("checkbox", { name: "Minimes" }));
    getTrainingSession.mockResolvedValue(INSCRITE);
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() =>
      expect(updateTrainingSession).toHaveBeenCalledWith(1, expect.objectContaining({ group_ids: [7, 8] })),
    );
    expect(await screen.findByText("Alix Martin")).toBeInTheDocument();
  });

  it("n'envoie aucun groupe quand la liste des groupes n'a pas pu être chargée", async () => {
    listTrainingGroups.mockRejectedValue(new Error("panne"));
    updateTrainingSession.mockResolvedValue(VIDE);
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(updateTrainingSession).toHaveBeenCalled());
    expect(updateTrainingSession.mock.calls[0][1]).not.toHaveProperty("group_ids");
  });
});
