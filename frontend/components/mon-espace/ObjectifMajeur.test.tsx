import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SeasonGoal } from "@/lib/types";

const { getSeasonGoals } = vi.hoisted(() => ({ getSeasonGoals: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getSeasonGoals } };
});

import { ObjectifMajeur, RappelObjectifMajeur } from "./ObjectifMajeur";

const BASE: SeasonGoal = {
  id: 1, season: 2026, kind: "race", event_type: "triathlon-m", target: 9000, best_time: null, count: null,
  reached: false, course_id: null, race_name: "Triathlon de Nantes", race_date: "2026-10-12", major: true,
  public: false, outcome: "upcoming",
};
const goal = (extra: Partial<SeasonGoal>): SeasonGoal => ({ ...BASE, ...extra });

function afficher(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 1, 10));
});
afterEach(() => vi.useRealTimers());

describe("ObjectifMajeur", () => {
  it("renders nothing without a major goal", async () => {
    getSeasonGoals.mockResolvedValue([goal({ major: false })]);
    const { container } = afficher(<ObjectifMajeur />);
    await vi.waitFor(() => expect(getSeasonGoals).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 0));
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the countdown and the target time of an upcoming race", async () => {
    getSeasonGoals.mockResolvedValue([goal({})]);
    afficher(<ObjectifMajeur />);
    expect(await screen.findByText("J‑11")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText("dans 11 jours")).toHaveClass("sr-only");
    expect(screen.getByText("Temps visé : 2:30:00")).toBeInTheDocument();
  });

  it("says today on the day of the race", async () => {
    getSeasonGoals.mockResolvedValue([goal({ race_date: "2026-10-01" })]);
    afficher(<ObjectifMajeur />);
    expect(await screen.findByText("Aujourd'hui")).toBeInTheDocument();
  });

  it("states a race awaiting results", async () => {
    getSeasonGoals.mockResolvedValue([goal({ outcome: "awaiting_results" })]);
    afficher(<ObjectifMajeur />);
    expect(await screen.findByText("En attente des résultats")).toBeInTheDocument();
  });

  it("states the outcome of a finished race", async () => {
    getSeasonGoals.mockResolvedValue([goal({ outcome: "reached", reached: true, best_time: "2:20:00" })]);
    afficher(<ObjectifMajeur />);
    expect(await screen.findByText("Atteint")).toBeInTheDocument();
    expect(screen.getByText("Temps : 2:20:00")).toBeInTheDocument();
  });

  it("states a missed race", async () => {
    getSeasonGoals.mockResolvedValue([goal({ outcome: "missed", best_time: "2:40:00" })]);
    afficher(<ObjectifMajeur />);
    expect(await screen.findByText("Non atteint")).toBeInTheDocument();
  });

  it("shows the progress of a time goal without countdown", async () => {
    getSeasonGoals.mockResolvedValue([goal({ kind: "time", race_name: null, race_date: null, best_time: "2:35:10", outcome: "missed" })]);
    afficher(<ObjectifMajeur />);
    expect(await screen.findByText("Meilleur temps : 2:35:10")).toBeInTheDocument();
    expect(screen.queryByText(/^J‑/)).not.toBeInTheDocument();
  });

  it("shows the progress of a count goal without countdown", async () => {
    getSeasonGoals.mockResolvedValue([goal({ kind: "count", target: 6, count: 2, race_name: null, race_date: null, event_type: null, outcome: "missed" })]);
    afficher(<ObjectifMajeur />);
    expect(await screen.findByText("2 sur 6")).toBeInTheDocument();
    expect(screen.queryByText(/^J‑/)).not.toBeInTheDocument();
  });
});

describe("RappelObjectifMajeur", () => {
  it("renders nothing without a major goal", async () => {
    getSeasonGoals.mockResolvedValue([]);
    const { container } = afficher(<RappelObjectifMajeur />);
    await vi.waitFor(() => expect(getSeasonGoals).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 0));
    expect(container).toBeEmptyDOMElement();
  });

  it("gives the label and the countdown on one line", async () => {
    getSeasonGoals.mockResolvedValue([goal({})]);
    afficher(<RappelObjectifMajeur />);
    expect(await screen.findByText(/Triathlon de Nantes/)).toBeInTheDocument();
    expect(screen.getByText(/^Dans 11 jours$/)).toBeInTheDocument();
  });

  it("gives the outcome of a finished race", async () => {
    getSeasonGoals.mockResolvedValue([goal({ outcome: "reached", reached: true })]);
    afficher(<RappelObjectifMajeur />);
    expect(await screen.findByText("Atteint")).toBeInTheDocument();
  });
});
