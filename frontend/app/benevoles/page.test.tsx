import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { Participation } from "@/lib/types";

const { getBenevoleQueue, benevoleLogin, validateParticipationBenevole } = vi.hoisted(() => ({
  getBenevoleQueue: vi.fn(),
  benevoleLogin: vi.fn(),
  validateParticipationBenevole: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { getBenevoleQueue, benevoleLogin, validateParticipationBenevole },
  };
});

import BenevolesPage from "./page";

function participation(over: Partial<Participation> & { id: number }): Participation {
  return {
    athlete: over.athlete ?? { id: over.id, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" },
    course: over.course ?? {
      id: over.id,
      name: `Course ${over.id}`,
      event_date: "2026-05-10",
      event_type: "triathlon-m",
      provider: "manuel",
      source_url: "",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: null,
    bib_number: null,
    rank_overall: null,
    rank_category: null,
    rank_gender: null,
    total_time: "01:00:00",
    status: "finisher",
    is_relay: false,
    team_name: null,
    evidence_url: null,
    is_pending_validation: true,
    splits: null,
    created_at: "2026-05-11T10:00:00Z",
    ...over,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("BenevolesPage", () => {
  it("affiche le formulaire de mot de passe sur 401", async () => {
    getBenevoleQueue.mockRejectedValue(new ApiError(401, "Non autorisé"));
    render(<BenevolesPage />);

    expect(await screen.findByLabelText(/mot de passe/i)).toBeInTheDocument();
  });

  it("affiche la file après une connexion réussie", async () => {
    getBenevoleQueue.mockRejectedValueOnce(new ApiError(401, "Non autorisé"));
    getBenevoleQueue.mockResolvedValueOnce([participation({ id: 1 })]);
    benevoleLogin.mockResolvedValue(null);
    const user = userEvent.setup();
    render(<BenevolesPage />);

    await user.type(await screen.findByLabelText(/mot de passe/i), "secret-du-club");
    await user.click(screen.getByRole("button", { name: /se connecter/i }));

    expect(await screen.findByText(/Course 1/)).toBeInTheDocument();
  });

  it("affiche directement la file quand la session est déjà valide", async () => {
    getBenevoleQueue.mockResolvedValue([participation({ id: 1 }), participation({ id: 2 })]);
    render(<BenevolesPage />);

    expect(await screen.findByText(/Course 1/)).toBeInTheDocument();
    expect(screen.getByText(/Course 2/)).toBeInTheDocument();
  });

  it("sélectionne un résultat et affiche son panneau de détail", async () => {
    getBenevoleQueue.mockResolvedValue([participation({ id: 1 })]);
    const user = userEvent.setup();
    render(<BenevolesPage />);

    await user.click(await screen.findByRole("button", { name: /Course 1/ }));

    expect(screen.getByRole("button", { name: /valider ce résultat/i })).toBeInTheDocument();
  });

  it("retire un résultat de la file une fois validé", async () => {
    getBenevoleQueue.mockResolvedValue([participation({ id: 1 })]);
    validateParticipationBenevole.mockResolvedValue(
      participation({ id: 1, is_pending_validation: false }),
    );
    const user = userEvent.setup();
    render(<BenevolesPage />);

    await user.click(await screen.findByRole("button", { name: /Course 1/ }));
    await user.click(screen.getByRole("button", { name: /valider ce résultat/i }));

    await waitFor(() => expect(screen.getByText(/aucun résultat en attente/i)).toBeInTheDocument());
  });
});
