import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { Participation } from "@/lib/types";

const {
  getBenevoleQueue,
  getBenevoleRejected,
  benevoleLogin,
  validateParticipationBenevole,
  rejectParticipationBenevole,
  unrejectParticipationBenevole,
} = vi.hoisted(() => ({
  getBenevoleQueue: vi.fn(),
  getBenevoleRejected: vi.fn(),
  benevoleLogin: vi.fn(),
  validateParticipationBenevole: vi.fn(),
  rejectParticipationBenevole: vi.fn(),
  unrejectParticipationBenevole: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      getBenevoleQueue,
      getBenevoleRejected,
      benevoleLogin,
      validateParticipationBenevole,
      rejectParticipationBenevole,
      unrejectParticipationBenevole,
    },
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
  getBenevoleRejected.mockResolvedValue([]);
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

  it("affiche un signal de chargement avant que la file ne réponde", () => {
    getBenevoleQueue.mockReturnValue(new Promise(() => {})); // ne se résout jamais dans ce test
    render(<BenevolesPage />);
    expect(screen.getByText(/chargement/i)).toBeInTheDocument();
  });

  it("propose de réessayer après un échec de chargement", async () => {
    getBenevoleQueue.mockRejectedValueOnce(new Error("Panne réseau"));
    getBenevoleQueue.mockResolvedValueOnce([participation({ id: 1 })]);
    const user = userEvent.setup();
    render(<BenevolesPage />);

    const reessayer = await screen.findByRole("button", { name: /réessayer/i });
    await user.click(reessayer);

    expect(await screen.findByText(/Course 1/)).toBeInTheDocument();
  });

  it("réinitialise le panneau de détail quand on change de résultat sélectionné", async () => {
    getBenevoleQueue.mockResolvedValue([participation({ id: 1 }), participation({ id: 2 })]);
    const user = userEvent.setup();
    render(<BenevolesPage />);

    await user.click(await screen.findByRole("button", { name: /Course 1/ }));
    const champNom = screen.getByLabelText(/nom de l.épreuve/i);
    await user.clear(champNom);
    await user.type(champNom, "Texte non enregistré");

    await user.click(screen.getByRole("button", { name: /Course 2/ }));

    expect(screen.getByLabelText(/nom de l.épreuve/i)).toHaveValue("Course 2");
  });

  it("signale un résultat non conforme et le fait passer dans l'onglet non-conformes", async () => {
    const pendante = participation({ id: 1, is_pending_validation: true, is_rejected: false });
    getBenevoleQueue.mockResolvedValue([pendante]);
    getBenevoleRejected.mockResolvedValue([]);
    rejectParticipationBenevole.mockResolvedValue(
      participation({ id: 1, is_pending_validation: true, is_rejected: true }),
    );
    const user = userEvent.setup();
    render(<BenevolesPage />);

    await user.click(await screen.findByRole("button", { name: /Course 1/ }));
    await user.click(screen.getByRole("button", { name: /signaler non conforme/i }));
    await user.click(screen.getByRole("button", { name: /confirmer/i }));

    await waitFor(() => expect(rejectParticipationBenevole).toHaveBeenCalledWith(1));
    expect(screen.queryByRole("button", { name: /Course 1/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /non conformes/i }));
    expect(screen.getByRole("button", { name: /Course 1/ })).toBeInTheDocument();
  });

  it("annule un rejet et fait revenir le résultat dans la file", async () => {
    const rejetee = participation({ id: 1, is_pending_validation: true, is_rejected: true });
    getBenevoleQueue.mockResolvedValue([]);
    getBenevoleRejected.mockResolvedValue([rejetee]);
    unrejectParticipationBenevole.mockResolvedValue(
      participation({ id: 1, is_pending_validation: true, is_rejected: false }),
    );
    const user = userEvent.setup();
    render(<BenevolesPage />);

    await user.click(await screen.findByRole("button", { name: /non conformes/i }));
    await user.click(screen.getByRole("button", { name: /Course 1/ }));
    await user.click(screen.getByRole("button", { name: /annuler le rejet/i }));

    await waitFor(() => expect(unrejectParticipationBenevole).toHaveBeenCalledWith(1));
    await user.click(screen.getByRole("button", { name: /^file/i }));
    expect(screen.getByRole("button", { name: /Course 1/ })).toBeInTheDocument();
  });
});
