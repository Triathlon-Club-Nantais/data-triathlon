import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { TrainingSession, TrainingSessionDetail, SessionUser } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { listTrainingSessions, getTrainingSession, createTrainingSession, getSession } = vi.hoisted(
  () => ({
    listTrainingSessions: vi.fn(),
    getTrainingSession: vi.fn(),
    createTrainingSession: vi.fn(),
    getSession: vi.fn(),
  }),
);

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listTrainingSessions, getTrainingSession, createTrainingSession, getSession },
  };
});

import { CalendrierEntrainements } from "./CalendrierEntrainements";

const SEANCE: TrainingSession = {
  id: 1,
  date: "2026-09-20",
  start_time: "18:00:00",
  location: "Base nautique",
  session_type: "Natation",
  note: "",
  participant_count: 2,
};

const SEANCE_SANS_CHAMPS: TrainingSession = {
  id: 2,
  date: "2026-09-27",
  start_time: null,
  location: null,
  session_type: null,
  note: "",
  participant_count: 0,
};

const DETAIL: TrainingSessionDetail = { ...SEANCE, participants: [] };

const AVEC_ECRITURE: SessionUser = {
  id: 1,
  email: "moi@exemple.fr",
  display_name: "Moi",
  created_at: "2026-01-01T00:00:00Z",
  permissions: ["jeunes:read", "jeunes:write"],
  roles: [],
  groups: [],
};

const LECTURE_SEULE: SessionUser = { ...AVEC_ECRITURE, permissions: ["jeunes:read"] };

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CalendrierEntrainements />
    </QueryClientProvider>,
  );
}

describe("CalendrierEntrainements", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(AVEC_ECRITURE);
    getTrainingSession.mockResolvedValue(DETAIL);
  });

  it("liste les entraînements triés, avec leur nombre d'inscrits", async () => {
    listTrainingSessions.mockResolvedValue([SEANCE]);

    afficher();

    expect(await screen.findByText("20/09/2026")).toBeInTheDocument();
    expect(screen.getByText("Base nautique")).toBeInTheDocument();
    expect(screen.getByText("Natation")).toBeInTheDocument();
    expect(screen.getByText(/2 inscrits/)).toBeInTheDocument();
  });

  it("n'affiche aucun texte vide pour les champs optionnels absents", async () => {
    listTrainingSessions.mockResolvedValue([SEANCE_SANS_CHAMPS]);

    afficher();

    expect(await screen.findByText("27/09/2026")).toBeInTheDocument();
    expect(screen.getByText("Lieu non renseigné")).toBeInTheDocument();
    expect(screen.getByText(/0 inscrit/)).toBeInTheDocument();
    expect(screen.queryByText("undefined")).not.toBeInTheDocument();
    expect(screen.queryByText("null")).not.toBeInTheDocument();
  });

  it("dit « aucun entraînement » sur une liste vide", async () => {
    listTrainingSessions.mockResolvedValue([]);

    afficher();

    expect(await screen.findByText(/aucun entraînement/i)).toBeInTheDocument();
  });

  it("ne propose aucune commande d'écriture sans jeunes:write", async () => {
    getSession.mockResolvedValue(LECTURE_SEULE);
    listTrainingSessions.mockResolvedValue([SEANCE]);

    afficher();

    await screen.findByText("20/09/2026");
    expect(screen.queryByLabelText(/^date$/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /créer la séance/i })).not.toBeInTheDocument();
  });

  it("crée un entraînement à partir de sa date", async () => {
    listTrainingSessions.mockResolvedValue([]);
    createTrainingSession.mockResolvedValue(DETAIL);

    afficher();
    await screen.findByText(/aucun entraînement/i);
    await userEvent.type(screen.getByLabelText(/^date$/i), "2026-09-20");
    await userEvent.click(screen.getByRole("button", { name: /créer la séance/i }));

    expect(createTrainingSession).toHaveBeenCalledWith({
      date: "2026-09-20",
      start_time: null,
      location: null,
      session_type: null,
    });
  });

  it("dit « accès refusé » sur un 403", async () => {
    listTrainingSessions.mockRejectedValue(new ApiError(403, "Refusé"));

    afficher();

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
  });
});
