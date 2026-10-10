import { QueryClient, QueryClientProvider, focusManager } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { TrainingSession, TrainingSessionDetail, SessionUser } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const {
  listTrainingSessions,
  getTrainingSession,
  createTrainingSession,
  deleteTrainingSession,
  listProfiles,
  getSession,
} = vi.hoisted(() => ({
  listTrainingSessions: vi.fn(),
  getTrainingSession: vi.fn(),
  createTrainingSession: vi.fn(),
  deleteTrainingSession: vi.fn(),
  listProfiles: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      listTrainingSessions,
      getTrainingSession,
      createTrainingSession,
      deleteTrainingSession,
      listProfiles,
      getSession,
    },
  };
});

import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
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
  can_administer: true,
};

const LECTURE_SEULE: SessionUser = { ...AVEC_ECRITURE, permissions: ["jeunes:read"] };

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <CalendrierEntrainements />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

describe("CalendrierEntrainements", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(AVEC_ECRITURE);
    getTrainingSession.mockResolvedValue(DETAIL);
    listProfiles.mockResolvedValue([]);
  });

  afterEach(() => focusManager.setFocused(undefined));

  it("ne prend pas une relance suspendue pour une absence de données (#1290)", async () => {
    // Backend endormi : le premier essai échoue, et React Query suspend la
    // relance tant que l'onglet n'a pas le focus.
    focusManager.setFocused(false);
    listTrainingSessions.mockRejectedValue(new ApiError(503, "Service indisponible"));
    const client = new QueryClient({ defaultOptions: { queries: { retry: 1, retryDelay: 0 } } });
    render(
      <QueryClientProvider client={client}>
        <DangerConfirmProvider>
          <CalendrierEntrainements />
        </DangerConfirmProvider>
      </QueryClientProvider>,
    );

    await waitFor(() =>
      expect(client.getQueryCache().find({ queryKey: ["admin-training-sessions"] })?.state.fetchStatus).toBe("paused"),
    );
    expect(screen.queryByText(/aucun entraînement/i)).not.toBeInTheDocument();
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

  it.each([
    [0, "0 inscrit"],
    [1, "1 inscrit"],
    [2, "2 inscrits"],
  ])("accorde %i participant(s) au singulier jusqu'à 1 (#1013)", async (count, libelle) => {
    listTrainingSessions.mockResolvedValue([{ ...SEANCE, participant_count: count }]);

    afficher();

    expect(await screen.findByText(libelle)).toBeInTheDocument();
  });

  describe("ordre du calendrier, vu le 10/10/2026", () => {
    beforeEach(() => {
      vi.useFakeTimers({ toFake: ["Date"] });
      vi.setSystemTime(new Date(2026, 9, 10, 12));
    });
    afterEach(() => vi.useRealTimers());

    const seance = (id: number, date: string): TrainingSession => ({ ...SEANCE, id, date });

    it("liste les séances à venir d'abord, puis les passées de la plus récente à la plus ancienne", async () => {
      listTrainingSessions.mockResolvedValue([
        seance(1, "2026-09-20"),
        seance(2, "2026-10-01"),
        seance(3, "2026-10-10"),
        seance(4, "2026-10-20"),
      ]);

      afficher();

      const aVenir = await screen.findByRole("region", { name: "Séances à venir" });
      const passees = screen.getByRole("region", { name: "Séances passées" });
      const dates = (zone: HTMLElement) =>
        within(zone)
          .getAllByText(/^\d{2}\/\d{2}\/\d{4}$/)
          .map((n) => n.textContent);
      expect(dates(aVenir)).toEqual(["10/10/2026", "20/10/2026"]);
      expect(dates(passees)).toEqual(["01/10/2026", "20/09/2026"]);
    });

    it("signale la séance du jour", async () => {
      listTrainingSessions.mockResolvedValue([seance(3, "2026-10-10"), seance(4, "2026-10-20")]);

      afficher();

      const aujourdhui = await screen.findByText("Aujourd'hui");
      expect(aujourdhui.closest("[role=button]")).toHaveTextContent("10/10/2026");
      expect(screen.getAllByText("Aujourd'hui")).toHaveLength(1);
    });

    it("dit qu'aucune séance n'est à venir quand toutes sont passées", async () => {
      listTrainingSessions.mockResolvedValue([seance(1, "2026-09-20")]);

      afficher();

      expect(await screen.findByText("Aucune séance à venir.")).toBeInTheDocument();
      expect(screen.getByRole("region", { name: "Séances passées" })).toHaveTextContent(
        "20/09/2026",
      );
    });
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

  it("supprime une séance après confirmation", async () => {
    listTrainingSessions.mockResolvedValue([SEANCE]);
    deleteTrainingSession.mockResolvedValue(null);

    afficher();
    await userEvent.click(await screen.findByText("20/09/2026"));
    await userEvent.click(await screen.findByRole("button", { name: "Supprimer la séance" }));

    expect(deleteTrainingSession).not.toHaveBeenCalled();
    const confirmation = await screen.findByRole("dialog", {
      name: "Supprimer la séance du 20/09/2026 ?",
    });
    await userEvent.click(within(confirmation).getByRole("button", { name: "Supprimer la séance" }));

    await waitFor(() => expect(deleteTrainingSession).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("ne propose pas de supprimer une séance sans jeunes:write", async () => {
    getSession.mockResolvedValue(LECTURE_SEULE);
    listTrainingSessions.mockResolvedValue([SEANCE]);

    afficher();
    await userEvent.click(await screen.findByText("20/09/2026"));

    await screen.findByRole("dialog");
    expect(screen.queryByRole("button", { name: /supprimer/i })).not.toBeInTheDocument();
  });

  it("dit « accès refusé » sur un 403", async () => {
    listTrainingSessions.mockRejectedValue(new ApiError(403, "Refusé"));

    afficher();

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
  });
});
