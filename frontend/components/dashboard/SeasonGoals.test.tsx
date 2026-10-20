import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SeasonGoal, SessionUser } from "@/lib/types";

const { getSession, getSeasonGoals, createSeasonGoal, deleteSeasonGoal, listCourses } = vi.hoisted(() => ({
  getSession: vi.fn(),
  getSeasonGoals: vi.fn(),
  createSeasonGoal: vi.fn(),
  deleteSeasonGoal: vi.fn(),
  listCourses: vi.fn(),
}));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { ...original.apiClient, getSession, getSeasonGoals, createSeasonGoal, deleteSeasonGoal, listCourses },
  };
});

import { localToday } from "@/lib/utils/date";
import { currentSeason, seasonLabel } from "@/lib/utils/season";
import { SeasonGoals, libelle, progression } from "./SeasonGoals";

const LEA = { id: 42, prenom: "Léa", nom: "Martin" };
const TEMPS: SeasonGoal = {
  id: 1, season: 2025, kind: "time", event_type: "triathlon-m", target: 9000,
  best_time: "2:35:10", count: null, reached: false,
  course_id: null, race_name: null, race_date: null, major: false, outcome: "missed",
};
const NOMBRE: SeasonGoal = {
  id: 2, season: 2025, kind: "count", event_type: null, target: 6, best_time: null, count: 6, reached: true,
  course_id: null, race_name: null, race_date: null, major: false, outcome: "reached",
};

function session(athlete: SessionUser["athlete"]): SessionUser {
  return { id: 1, email: "lea@exemple.fr", permissions: [], roles: [], groups: [], athlete, athlete_claim: null } as unknown as SessionUser;
}

function afficher(seasons: number[] = [currentSeason()]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SeasonGoals seasons={seasons} />
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
    const nombre = screen.getByText("6 épreuves").closest("li") as HTMLElement;
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
      expect(createSeasonGoal).toHaveBeenCalledWith({ kind: "time", event_type: "triathlon-m", target: 9000, major: false }),
    );
  });

  it("adds a count goal on every discipline", async () => {
    createSeasonGoal.mockResolvedValue(NOMBRE);
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Ajouter un objectif" }));
    await userEvent.click(screen.getByRole("radio", { name: "Nombre d'épreuves" }));
    await userEvent.type(screen.getByLabelText("Nombre d'épreuves visé"), "6");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(createSeasonGoal).toHaveBeenCalledWith({ kind: "count", event_type: null, target: 6, major: false }));
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

    const ligne = (await screen.findByText("6 épreuves")).closest("li") as HTMLElement;
    await userEvent.click(within(ligne).getByRole("button", { name: "Supprimer l'objectif « 6 épreuves »" }));
    await userEvent.click(await screen.findByRole("button", { name: "Supprimer l'objectif" }));

    await waitFor(() => expect(deleteSeasonGoal).toHaveBeenCalledWith(2));
  });

  it("names the season in the card title and no longer repeats the recap link", async () => {
    afficher();

    expect(await screen.findByRole("heading", { level: 2, name: `Objectifs, ${seasonLabel(currentSeason())}` })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Récap de la saison passée" })).toBeNull();
    expect(getSeasonGoals).toHaveBeenCalledWith(currentSeason());
  });

  it("shows a past season's goals read only", async () => {
    const passee = currentSeason() - 1;
    afficher([passee]);

    expect(await screen.findByRole("heading", { level: 2, name: `Objectifs, ${seasonLabel(passee)}` })).toBeInTheDocument();
    expect(await screen.findByText("6 épreuves")).toBeInTheDocument();
    expect(getSeasonGoals).toHaveBeenCalledWith(passee);
    expect(screen.queryByRole("button", { name: "Ajouter un objectif" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Modifier|Supprimer/ })).toBeNull();
  });

  it("falls back to the current season and says so when several seasons are selected", async () => {
    afficher([currentSeason(), currentSeason() - 1]);

    expect(await screen.findByRole("heading", { level: 2, name: `Objectifs, ${seasonLabel(currentSeason())}` })).toBeInTheDocument();
    expect(screen.getByText(/Plusieurs saisons sont sélectionnées/)).toBeInTheDocument();
    expect(getSeasonGoals).toHaveBeenCalledWith(currentSeason());
    expect(await screen.findByRole("button", { name: "Ajouter un objectif" })).toBeInTheDocument();
  });

  it("does not announce several seasons for an empty selection", async () => {
    afficher([]);

    expect(await screen.findByRole("heading", { level: 2, name: `Objectifs, ${seasonLabel(currentSeason())}` })).toBeInTheDocument();
    expect(screen.queryByText(/Plusieurs saisons/)).toBeNull();
    expect(getSeasonGoals).toHaveBeenCalledWith(currentSeason());
  });

  it("shows nothing without a claimed athlete", async () => {
    getSession.mockResolvedValue(session(null));
    afficher();

    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByRole("heading", { level: 2 })).not.toBeInTheDocument();
    expect(getSeasonGoals).not.toHaveBeenCalled();
  });
});

const COURSE = { id: 7, name: "Triathlon de Nantes", event_date: `${currentSeason() + 1}-06-14`, event_type: "triathlon-m" };

function jourDecale(jours: number): string {
  const d = new Date();
  d.setDate(d.getDate() + jours);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

describe("SeasonGoals, épreuve cible (#1694)", () => {
  it("creates a goal on an imported race found by search", async () => {
    listCourses.mockResolvedValue([COURSE]);
    createSeasonGoal.mockResolvedValue(TEMPS);
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Ajouter un objectif" }));
    await userEvent.click(screen.getByRole("radio", { name: "Une épreuve cible" }));
    await userEvent.type(screen.getByLabelText("Rechercher votre épreuve"), "Nantes");
    await userEvent.click(await screen.findByRole("button", { name: /Triathlon de Nantes/ }));
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(listCourses).toHaveBeenCalledWith({
      name: "Nantes",
      date_from: `${currentSeason()}-09-01`,
      date_to: `${currentSeason() + 1}-08-31`,
      page_size: 8,
    });
    await waitFor(() =>
      expect(createSeasonGoal).toHaveBeenCalledWith({ kind: "race", event_type: "triathlon-m", target: null, major: false, course_id: 7 }),
    );
  });

  it("creates a goal on a free entry race with the major flag", async () => {
    createSeasonGoal.mockResolvedValue(TEMPS);
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Ajouter un objectif" }));
    await userEvent.click(screen.getByRole("radio", { name: "Une épreuve cible" }));
    await userEvent.click(screen.getByRole("button", { name: "Mon épreuve n'est pas dans la liste" }));
    await userEvent.type(screen.getByLabelText("Nom de l'épreuve"), "Run du coin");
    await userEvent.type(screen.getByLabelText("Date de l'épreuve"), `${currentSeason() + 1}-05-02`);
    await userEvent.click(screen.getByRole("checkbox", { name: "Objectif majeur de la saison" }));
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() =>
      expect(createSeasonGoal).toHaveBeenCalledWith({
        kind: "race", event_type: null, target: null, major: true,
        race_name: "Run du coin", race_date: `${currentSeason() + 1}-05-02`,
      }),
    );
  });

  it("refuses a target time without a discipline", async () => {
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Ajouter un objectif" }));
    await userEvent.click(screen.getByRole("radio", { name: "Une épreuve cible" }));
    await userEvent.click(screen.getByRole("button", { name: "Mon épreuve n'est pas dans la liste" }));
    await userEvent.type(screen.getByLabelText("Nom de l'épreuve"), "Run du coin");
    await userEvent.type(screen.getByLabelText("Date de l'épreuve"), `${currentSeason() + 1}-05-02`);
    await userEvent.type(screen.getByLabelText("Temps visé (facultatif)"), "2:30:00");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByText("Choisissez la discipline et le format du temps à battre.")).toBeInTheDocument();
    expect(createSeasonGoal).not.toHaveBeenCalled();
  });

  it("labels a race goal and its four outcomes", () => {
    const course: SeasonGoal = {
      ...TEMPS, kind: "race", target: null, course_id: 7, race_name: "Triathlon de Nantes",
      race_date: "2026-06-14", outcome: "awaiting_results",
    };
    expect(libelle(course)).toBe("Triathlon de Nantes, 14/06/2026");
    expect(progression(course)).toBe("En attente des résultats");
    expect(progression({ ...course, outcome: "reached", best_time: "2:25:00" })).toBe("Objectif atteint, temps 2:25:00");
    expect(progression({ ...course, outcome: "missed", best_time: null })).toBe("Objectif manqué");
    expect(progression({ ...course, outcome: "upcoming", race_date: jourDecale(12) })).toBe("Dans 12 jours");
    expect(progression({ ...course, outcome: "upcoming", race_date: jourDecale(0) })).toBe("Aujourd'hui");
    expect(localToday()).toBe(jourDecale(0));
  });

  it("flags the major goal", async () => {
    getSeasonGoals.mockResolvedValue([{ ...NOMBRE, major: true }, TEMPS]);
    afficher();

    const ligne = (await screen.findByText("6 épreuves")).closest("li") as HTMLElement;
    expect(within(ligne).getByText("Majeur")).toBeInTheDocument();
    expect(within((await screen.findByText("Triathlon M en moins de 2:30:00")).closest("li") as HTMLElement).queryByText("Majeur")).toBeNull();
  });
});
