import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { TrainingSessionDetail, Profile } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const {
  getTrainingSession,
  listProfiles,
  addTrainingParticipant,
  removeTrainingParticipant,
} = vi.hoisted(() => ({
  getTrainingSession: vi.fn(),
  listProfiles: vi.fn(),
  addTrainingParticipant: vi.fn(),
  removeTrainingParticipant: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      getTrainingSession,
      listProfiles,
      addTrainingParticipant,
      removeTrainingParticipant,
    },
  };
});

import { ParticipantsList } from "./ParticipantsList";

const ALIX: Profile = {
  id: 42,
  organisation_id: 1,
  first_name: "Alix",
  last_name: "Martin",
  birth_date: null,
  created_at: "2026-01-01T00:00:00Z",
};

const ZOE: Profile = { ...ALIX, id: 43, first_name: "Zoé", last_name: "Roux" };

const DETAIL_AVEC_PARTICIPANT: TrainingSessionDetail = {
  id: 1,
  date: "2026-09-20",
  start_time: null,
  location: null,
  session_type: null,
  note: "",
  participant_count: 1,
  participants: [{ profile_id: 42, present: null, created_at: "2026-09-15T10:00:00Z" }],
};

const DETAIL_VIDE: TrainingSessionDetail = { ...DETAIL_AVEC_PARTICIPANT, participant_count: 0, participants: [] };

function afficher(peutEcrire: boolean) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ParticipantsList sessionId={1} peutEcrire={peutEcrire} />
    </QueryClientProvider>,
  );
}

describe("ParticipantsList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listProfiles.mockResolvedValue([ALIX, ZOE]);
  });

  it("nomme les jeunes inscrits", async () => {
    getTrainingSession.mockResolvedValue(DETAIL_AVEC_PARTICIPANT);

    afficher(true);

    expect(await screen.findByText("Alix Martin")).toBeInTheDocument();
    expect(screen.queryByText(/jeune n°/i)).not.toBeInTheDocument();
  });

  it("dit « aucun participant inscrit » sur une liste vide", async () => {
    getTrainingSession.mockResolvedValue(DETAIL_VIDE);

    afficher(true);

    expect(await screen.findByText(/aucun participant inscrit/i)).toBeInTheDocument();
  });

  it("n'affiche ni sélecteur d'inscription ni bouton de désinscription sans jeunes:write", async () => {
    getTrainingSession.mockResolvedValue(DETAIL_AVEC_PARTICIPANT);

    afficher(false);

    await screen.findByText("Alix Martin");
    expect(screen.queryByLabelText(/inscrire un jeune/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /désinscrire/i })).not.toBeInTheDocument();
  });

  it("inscrit un jeune choisi par son nom", async () => {
    getTrainingSession.mockResolvedValue(DETAIL_VIDE);
    addTrainingParticipant.mockResolvedValue(DETAIL_AVEC_PARTICIPANT);

    afficher(true);
    await screen.findByRole("option", { name: "Alix Martin" });
    await userEvent.selectOptions(screen.getByLabelText(/inscrire un jeune/i), "Alix Martin");

    expect(addTrainingParticipant).toHaveBeenCalledWith(1, 42, undefined);
  });

  it("ne propose pas un jeune déjà inscrit", async () => {
    getTrainingSession.mockResolvedValue(DETAIL_AVEC_PARTICIPANT);

    afficher(true);
    await screen.findByRole("option", { name: "Zoé Roux" });

    expect(screen.queryByRole("option", { name: "Alix Martin" })).not.toBeInTheDocument();
  });

  it("désinscrit un jeune inscrit", async () => {
    getTrainingSession.mockResolvedValue(DETAIL_AVEC_PARTICIPANT);
    removeTrainingParticipant.mockResolvedValue(null);

    afficher(true);
    await screen.findByText("Alix Martin");
    await userEvent.click(screen.getByRole("button", { name: /désinscrire alix martin/i }));

    await waitFor(() => expect(removeTrainingParticipant).toHaveBeenCalledWith(1, 42));
  });
});
