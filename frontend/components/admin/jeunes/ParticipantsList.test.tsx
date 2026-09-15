import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { EntrainementDetail } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { getEntrainement, addEntrainementParticipant, removeEntrainementParticipant } =
  vi.hoisted(() => ({
    getEntrainement: vi.fn(),
    addEntrainementParticipant: vi.fn(),
    removeEntrainementParticipant: vi.fn(),
  }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { getEntrainement, addEntrainementParticipant, removeEntrainementParticipant },
  };
});

import { ParticipantsList } from "./ParticipantsList";

const DETAIL_AVEC_PARTICIPANT: EntrainementDetail = {
  id: 1,
  date: "2026-09-20",
  heure_debut: null,
  lieu: null,
  type_seance: null,
  participant_count: 1,
  participants: [{ jeune_id: 42, created_at: "2026-09-15T10:00:00Z" }],
};

const DETAIL_VIDE: EntrainementDetail = { ...DETAIL_AVEC_PARTICIPANT, participant_count: 0, participants: [] };

function afficher(peutEcrire: boolean) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ParticipantsList entrainementId={1} peutEcrire={peutEcrire} />
    </QueryClientProvider>,
  );
}

describe("ParticipantsList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("liste les jeunes inscrits", async () => {
    getEntrainement.mockResolvedValue(DETAIL_AVEC_PARTICIPANT);

    afficher(true);

    expect(await screen.findByText(/jeune n° 42/i)).toBeInTheDocument();
  });

  it("dit « aucun participant inscrit » sur une liste vide", async () => {
    getEntrainement.mockResolvedValue(DETAIL_VIDE);

    afficher(true);

    expect(await screen.findByText(/aucun participant inscrit/i)).toBeInTheDocument();
  });

  it("n'affiche ni formulaire d'inscription ni bouton de désinscription sans jeunes:write", async () => {
    getEntrainement.mockResolvedValue(DETAIL_AVEC_PARTICIPANT);

    afficher(false);

    await screen.findByText(/jeune n° 42/i);
    expect(screen.queryByLabelText(/identifiant du jeune/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /désinscrire/i })).not.toBeInTheDocument();
  });

  it("inscrit un jeune par son identifiant", async () => {
    getEntrainement.mockResolvedValue(DETAIL_VIDE);
    addEntrainementParticipant.mockResolvedValue(DETAIL_AVEC_PARTICIPANT);

    afficher(true);
    await screen.findByText(/aucun participant inscrit/i);
    await userEvent.type(screen.getByLabelText(/identifiant du jeune/i), "42");
    await userEvent.click(screen.getByRole("button", { name: /^inscrire$/i }));

    expect(addEntrainementParticipant).toHaveBeenCalledWith(1, 42);
  });

  it("désinscrit un jeune inscrit", async () => {
    getEntrainement.mockResolvedValue(DETAIL_AVEC_PARTICIPANT);
    removeEntrainementParticipant.mockResolvedValue(null);

    afficher(true);
    await screen.findByText(/jeune n° 42/i);
    await userEvent.click(screen.getByRole("button", { name: /désinscrire le jeune n° 42/i }));

    expect(removeEntrainementParticipant).toHaveBeenCalledWith(1, 42);
  });
});
