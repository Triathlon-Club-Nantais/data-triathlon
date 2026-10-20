import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AthleteChallenge, Participation } from "@/lib/types";

let searchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  usePathname: () => "/mon-espace",
  useSearchParams: () => searchParams,
}));
const { getMyVolunteerActions } = vi.hoisted(() => ({ getMyVolunteerActions: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getMyVolunteerActions } };
});
vi.mock("@/components/athletes/EventsTable", () => ({
  EventsTable: ({ participations }: { participations: unknown[] }) => <div data-testid="events">{participations.length} épreuves</div>,
}));
vi.mock("@/components/challenges/AthleteChallenges", () => ({
  AthleteChallenges: ({ challenges }: { challenges: unknown[] }) => <div data-testid="challenges">{challenges.length} challenges</div>,
}));
vi.mock("./OngletDisciplines", () => ({ OngletDisciplines: () => <div data-testid="disciplines" /> }));
vi.mock("./OngletProgression", () => ({ OngletProgression: () => <div data-testid="progression" /> }));
vi.mock("./OngletRecords", () => ({ OngletRecords: ({ federalOnly }: { federalOnly: boolean }) => <div data-testid="records">{String(federalOnly)}</div> }));
vi.mock("@/components/dashboard/SeasonGoals", () => ({ SeasonGoals: ({ seasons }: { seasons: number[] }) => <div data-testid="goals">{seasons.join(",")}</div> }));

import { OngletsMonEspace } from "./OngletsMonEspace";

const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
const arbre = () => (
  <QueryClientProvider client={client}>
    <OngletsMonEspace
      precedent={null}
      seasons={[2026]}
      athleteId={42}
      athleteName="Léa Martin"
      federalOnly
      participations={[{ id: 1 }, { id: 2 }] as unknown as Participation[]}
      challenges={[{ id: 9 }] as unknown as AthleteChallenge[]}
    />
  </QueryClientProvider>
);
const afficher = () => render(arbre());

beforeEach(() => {
  searchParams = new URLSearchParams();
  getMyVolunteerActions.mockReset().mockResolvedValue([]);
  // Next reflects pushState in useSearchParams; the mock does the same.
  vi.spyOn(window.history, "replaceState").mockImplementation((_s, _t, url) => {
    searchParams = new URLSearchParams(String(url).split("?")[1]);
  });
});

describe("OngletsMonEspace", () => {
  it("lists the tabs in order and opens the progression by default", () => {
    afficher();

    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["Progression", "Records", "Disciplines", "Épreuves", "Bénévolat", "Objectifs"]);
    expect(screen.getByRole("tab", { name: "Progression" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("progression")).toBeInTheDocument();
    expect(getMyVolunteerActions).not.toHaveBeenCalled();
  });

  it("keeps 44 px tabs that scroll sideways instead of overflowing the page", () => {
    afficher();

    expect(screen.getByRole("tablist")).toHaveClass("h-auto", "pb-2", "max-w-full", "justify-start", "overflow-x-auto");
    for (const tab of screen.getAllByRole("tab")) expect(tab).toHaveClass("min-h-11");
  });

  it("shows my races with their challenges in their tab", () => {
    searchParams = new URLSearchParams("onglet=epreuves");
    afficher();

    expect(screen.getByRole("tab", { name: "Épreuves" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("events")).toHaveTextContent("2 épreuves");
    expect(screen.getByTestId("challenges")).toHaveTextContent("1 challenges");
    expect(getMyVolunteerActions).not.toHaveBeenCalled();
  });

  it("selects the tab named by ?onglet and shows my validated actions", async () => {
    searchParams = new URLSearchParams("onglet=benevolat");
    getMyVolunteerActions.mockResolvedValue([
      { id: 1, title: "Buvette", season: 2026, created_at: "2026-05-02T10:00:00" },
    ]);
    afficher();

    expect(screen.getByRole("tab", { name: "Bénévolat" })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByText("Buvette")).toBeInTheDocument();
    expect(screen.getByText(/déclarée le/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Déclarer/ })).toHaveAttribute("href", "/benevolat");
  });

  it("shows an empty state for volunteering with the link to declare", async () => {
    searchParams = new URLSearchParams("onglet=benevolat");
    afficher();

    expect(await screen.findByText("Aucune action de bénévolat validée")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Déclarer/ })).toHaveAttribute("href", "/benevolat");
  });

  it("falls back to the first tab for an unknown ?onglet", () => {
    searchParams = new URLSearchParams("onglet=zzz");
    afficher();

    expect(screen.getByRole("tab", { name: "Progression" })).toHaveAttribute("aria-selected", "true");
  });

  it("shows my goals in their tab", () => {
    searchParams = new URLSearchParams("onglet=objectifs");
    afficher();

    expect(screen.getByTestId("goals")).toBeInTheDocument();
  });

  it("moves with the arrow keys and replaces the URL (no history entry per tab), keeping other params", async () => {
    searchParams = new URLSearchParams("seasons=2026");
    const { rerender } = afficher();

    screen.getByRole("tab", { name: "Épreuves" }).focus();
    await userEvent.keyboard("{ArrowRight}");
    rerender(arbre());

    expect(screen.getByRole("tab", { name: "Bénévolat" })).toHaveAttribute("aria-selected", "true");
    expect(window.history.replaceState).toHaveBeenCalledWith(null, "", "/mon-espace?seasons=2026&onglet=benevolat");
  });
});
