import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ProfileMeasurement, TrainingSession } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { addProfileMeasurement, deleteProfileMeasurement, listMeasurementEvents, listTrainingSessions } =
  vi.hoisted(() => ({
    addProfileMeasurement: vi.fn(),
    deleteProfileMeasurement: vi.fn(),
    listMeasurementEvents: vi.fn(),
    listTrainingSessions: vi.fn(),
  }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      addProfileMeasurement,
      deleteProfileMeasurement,
      listMeasurementEvents,
      listTrainingSessions,
    },
  };
});

import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { ProfileMeasurements } from "./ProfileMeasurements";

function test(id: number, event: string, measuredOn: string, tenths: number): ProfileMeasurement {
  return {
    id,
    measured_on: measuredOn,
    event,
    duration_tenths: tenths,
    training_session_id: null,
    created_at: "2026-10-01T10:00:00Z",
  };
}

const SEANCE: TrainingSession = {
  id: 9,
  date: "2026-10-21",
  start_time: "18:00:00",
  location: "Piscine",
  session_type: "Natation",
  note: "",
  participant_count: 3,
  group_ids: [],
  recurrence_id: null,
  detached: false,
};

function afficher(measurements: ProfileMeasurement[], peutEcrire = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <ProfileMeasurements profileId={4} measurements={measurements} peutEcrire={peutEcrire} />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

describe("ProfileMeasurements", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listMeasurementEvents.mockResolvedValue(["50 m nage libre"]);
    listTrainingSessions.mockResolvedValue([]);
    addProfileMeasurement.mockResolvedValue({});
  });

  it("groupe les tests par épreuve, durées formatées", () => {
    afficher([
      test(1, "50 m nage libre", "2026-09-10", 423),
      test(2, "50 m nage libre", "2026-10-10", 410),
      test(3, "Cooper", "2026-10-11", 4623),
    ]);

    expect(screen.getByRole("heading", { name: "50 m nage libre" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Cooper" })).toBeInTheDocument();
    expect(screen.getAllByRole("list")).toHaveLength(2);
    expect(screen.getByText(/42,3 s/)).toBeInTheDocument();
    expect(screen.getByText(/7:42,3/)).toBeInTheDocument();
  });

  it("garde l'ordre de l'API avec deux épreuves entrelacées", () => {
    afficher([
      test(1, "Cooper", "2026-09-10", 4623),
      test(2, "50 m nage libre", "2026-09-11", 423),
      test(3, "Cooper", "2026-10-11", 4500),
    ]);

    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual([
      "Cooper",
      "50 m nage libre",
    ]);
    expect(within(screen.getAllByRole("list")[0]).getAllByRole("listitem")).toHaveLength(2);
  });

  it("mentionne la séance seulement quand le test en a une", () => {
    afficher([
      { ...test(1, "Cooper", "2026-09-10", 4623), training_session_id: 5 },
      test(2, "Cooper", "2026-10-11", 4500),
    ]);

    const [avec, sans] = screen.getAllByRole("listitem");
    expect(avec).toHaveTextContent("en séance");
    expect(sans).not.toHaveTextContent("en séance");
  });

  it("supprime le test après confirmation, pas après renoncement", async () => {
    deleteProfileMeasurement.mockResolvedValue(undefined);
    const user = userEvent.setup();
    afficher([test(7, "Cooper", "2026-10-11", 4623)]);
    const supprimer = () => screen.getByRole("button", { name: /Supprimer le test Cooper/ });

    await user.click(supprimer());
    await user.click(await screen.findByRole("button", { name: "Renoncer" }));
    expect(deleteProfileMeasurement).not.toHaveBeenCalled();

    await user.click(supprimer());
    const dialogue = await screen.findByRole("dialog");
    await user.click(within(dialogue).getByRole("button", { name: "Supprimer" }));
    await waitFor(() => expect(deleteProfileMeasurement).toHaveBeenCalledWith(4, 7));
  });

  it("dit qu'il n'y a aucun test", () => {
    afficher([]);
    expect(screen.getByText("Aucun test chronométré pour l'instant.")).toBeInTheDocument();
  });

  it("enregistre une durée lue en dixièmes, épreuve sans ses blancs de bord", async () => {
    const user = userEvent.setup();
    afficher([]);

    await user.type(screen.getByLabelText("Épreuve"), "  Cooper ");
    await user.type(screen.getByLabelText("Durée"), "7:42,3");
    await user.click(screen.getByRole("button", { name: "Enregistrer le test" }));

    await waitFor(() =>
      expect(addProfileMeasurement).toHaveBeenCalledWith(4, {
        measured_on: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        event: "Cooper",
        duration_tenths: 4623,
        training_session_id: null,
      }),
    );
  });

  it("refuse une durée illisible sans appeler l'API", async () => {
    const user = userEvent.setup();
    afficher([]);

    await user.type(screen.getByLabelText("Épreuve"), "Cooper");
    await user.type(screen.getByLabelText("Durée"), "7:75");
    await user.click(screen.getByRole("button", { name: "Enregistrer le test" }));

    expect(screen.getByText("Durée illisible. Exemples : 42,3 ou 7:42.")).toBeInTheDocument();
    expect(screen.getByLabelText("Durée")).toHaveAttribute("aria-invalid", "true");
    expect(addProfileMeasurement).not.toHaveBeenCalled();
  });

  it("sans droit d'écriture, ni formulaire ni suppression", () => {
    afficher([test(1, "Cooper", "2026-10-11", 4623)], false);

    expect(screen.queryByLabelText("Durée")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Supprimer/ })).not.toBeInTheDocument();
  });

  it("n'offre pas de champ Séance sans séance ce jour", async () => {
    afficher([]);
    await waitFor(() => expect(listTrainingSessions).toHaveBeenCalled());
    expect(screen.queryByLabelText("Séance")).not.toBeInTheDocument();
  });

  it("rattache le test à la séance choisie", async () => {
    listTrainingSessions.mockResolvedValue([SEANCE]);
    const user = userEvent.setup();
    afficher([]);

    await user.selectOptions(await screen.findByLabelText("Séance"), "9");
    await user.type(screen.getByLabelText("Épreuve"), "Cooper");
    await user.type(screen.getByLabelText("Durée"), "42,3");
    await user.click(screen.getByRole("button", { name: "Enregistrer le test" }));

    await waitFor(() =>
      expect(addProfileMeasurement).toHaveBeenCalledWith(
        4,
        expect.objectContaining({ duration_tenths: 423, training_session_id: 9 }),
      ),
    );
  });
});
