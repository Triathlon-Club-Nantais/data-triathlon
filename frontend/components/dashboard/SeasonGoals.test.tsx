import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SeasonGoal, SessionUser } from "@/lib/types";

const { getSession, getSeasonGoals, createSeasonGoal, deleteSeasonGoal } = vi.hoisted(() => ({
  getSession: vi.fn(),
  getSeasonGoals: vi.fn(),
  createSeasonGoal: vi.fn(),
  deleteSeasonGoal: vi.fn(),
}));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { ...original.apiClient, getSession, getSeasonGoals, createSeasonGoal, deleteSeasonGoal },
  };
});

import { SeasonGoals } from "./SeasonGoals";

const LEA = { id: 42, prenom: "Léa", nom: "Martin" };
const TEMPS: SeasonGoal = {
  id: 1, season: 2025, kind: "time", event_type: "triathlon-m", target: 9000,
  best_time: "2:35:10", count: null, reached: false,
};
const NOMBRE: SeasonGoal = {
  id: 2, season: 2025, kind: "count", event_type: null, target: 6, best_time: null, count: 6, reached: true,
};

function session(athlete: SessionUser["athlete"]): SessionUser {
  return { id: 1, email: "lea@exemple.fr", permissions: [], roles: [], groups: [], athlete, athlete_claim: null } as unknown as SessionUser;
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SeasonGoals />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  document.cookie = "tcn_logged_in=1; path=/";
  getSession.mockResolvedValue(session(LEA));
  getSeasonGoals.mockResolvedValue([TEMPS, NOMBRE]);
});

describe("SeasonGoals (#1373)", () => {
  it("lists each goal with its progress", async () => {
    afficher();

    const temps = (await screen.findByText("Triathlon M en moins de 2:30:00")).closest("li") as HTMLElement;
    expect(temps).toHaveTextContent("Meilleur temps : 2:35:10");
    expect(temps).not.toHaveTextContent("Atteint");
    const nombre = screen.getByText("6 épreuves cette saison").closest("li") as HTMLElement;
    expect(nombre).toHaveTextContent("6 sur 6");
    expect(nombre).toHaveTextContent("Atteint");
  });

  it("adds a time goal from the form", async () => {
    createSeasonGoal.mockResolvedValue(TEMPS);
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Ajouter un objectif" }));
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon-m");
    await userEvent.type(screen.getByLabelText("Temps cible"), "2:30:00");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() =>
      expect(createSeasonGoal).toHaveBeenCalledWith({ kind: "time", event_type: "triathlon-m", target: 9000 }),
    );
  });

  it("adds a count goal on every discipline", async () => {
    createSeasonGoal.mockResolvedValue(NOMBRE);
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Ajouter un objectif" }));
    await userEvent.click(screen.getByRole("radio", { name: "Nombre d'épreuves" }));
    await userEvent.type(screen.getByLabelText("Nombre d'épreuves visé"), "6");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(createSeasonGoal).toHaveBeenCalledWith({ kind: "count", event_type: null, target: 6 }));
  });

  it("refuses a malformed time without calling the server", async () => {
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Ajouter un objectif" }));
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon-m");
    await userEvent.type(screen.getByLabelText("Temps cible"), "2h30");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByText(/Format attendu H:MM:SS/)).toBeInTheDocument();
    expect(createSeasonGoal).not.toHaveBeenCalled();
  });

  it("deletes a goal after confirmation", async () => {
    deleteSeasonGoal.mockResolvedValue(null);
    afficher();

    const ligne = (await screen.findByText("6 épreuves cette saison")).closest("li") as HTMLElement;
    await userEvent.click(within(ligne).getByRole("button", { name: "Supprimer l'objectif « 6 épreuves cette saison »" }));
    await userEvent.click(await screen.findByRole("button", { name: "Supprimer l'objectif" }));

    await waitFor(() => expect(deleteSeasonGoal).toHaveBeenCalledWith(2));
  });

  it("shows nothing without a claimed athlete", async () => {
    getSession.mockResolvedValue(session(null));
    afficher();

    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByText("Mes objectifs")).not.toBeInTheDocument();
    expect(getSeasonGoals).not.toHaveBeenCalled();
  });
});
