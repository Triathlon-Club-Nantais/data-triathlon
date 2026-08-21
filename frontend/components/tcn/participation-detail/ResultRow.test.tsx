import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { Participation, RankingEvolutionStep } from "@/lib/types";
import { ResultRow } from "./ResultRow";

function participation(over: Partial<Participation> = {}): Participation {
  return {
    id: 42,
    athlete: { id: 7, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" },
    course: {
      id: 3,
      name: "Triathlon de Nantes",
      event_date: "2026-05-16",
      event_type: "triathlon-m",
      provider: "raceresult",
      source_url: "",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: "V1H",
    bib_number: "56",
    rank_overall: 56,
    rank_category: 4,
    rank_gender: 41,
    total_time: "02:02:31",
    status: "finisher",
    is_relay: false,
    splits: {
      swim: "00:22:52",
      t1: "00:02:55",
      bike: "01:01:07",
      t2: "00:01:54",
      run: "00:33:45",
    },
    created_at: null,
    ...over,
  };
}

const SEGMENTS = ["swim", "t1", "bike", "t2", "run"];

const STEPS: RankingEvolutionStep[] = [
  { segment: "swim", scratch_position: 12, segment_position: 1 },
  { segment: "t1", scratch_position: 14, segment_position: 3 },
  { segment: "bike", scratch_position: 40, segment_position: 62 },
  { segment: "t2", scratch_position: 42, segment_position: 18 },
  { segment: "run", scratch_position: 56, segment_position: 30 },
];

function renderRow({
  row = participation(),
  segments = SEGMENTS,
  steps = STEPS,
}: {
  row?: Participation;
  segments?: string[];
  steps?: RankingEvolutionStep[];
} = {}) {
  return render(<ResultRow participation={row} segments={segments} steps={steps} />);
}

describe("ResultRow", () => {
  it("affiche l'identité, la catégorie, le sexe et le temps total", () => {
    renderRow();

    expect(screen.getByText("DUPONT Jean")).toBeTruthy();
    expect(screen.getByText("V1H")).toBeTruthy();
    expect(screen.getByText("M")).toBeTruthy();
    expect(screen.getByText("02:02:31")).toBeTruthy();
  });

  it("ouvre la page de l'athlète depuis son nom", () => {
    renderRow();

    const lien = screen.getByRole("link", { name: "DUPONT Jean" });
    expect(lien.getAttribute("href")).toBe("/athletes/7");
  });

  it("affiche le rang scratch", () => {
    renderRow();

    expect(screen.getByText("56")).toBeTruthy();
  });

  it("affiche le rang catégorie et le rang genre, pas seulement le rang scratch", () => {
    renderRow();

    expect(screen.getByText("4e cat.")).toBeTruthy();
    expect(screen.getByText("41e genre")).toBeTruthy();
  });

  it("n'affiche pas d'eyebrow \"Ma performance\" — l'écran est public", () => {
    renderRow();

    expect(screen.queryByText("Ma performance")).toBeNull();
  });

  it("affiche chaque segment publié par l'épreuve", () => {
    const { container } = renderRow();

    const cells = container.querySelectorAll("[data-segment]");
    expect([...cells].map((c) => c.getAttribute("data-segment"))).toEqual(SEGMENTS);
  });

  it("affiche la position de l'athlète sur chaque segment", () => {
    const { container } = renderRow();

    const cell = (key: string) => container.querySelector(`[data-segment="${key}"]`) as HTMLElement;
    expect(within(cell("swim")).getByText("1er")).toBeTruthy();
    expect(within(cell("t1")).getByText("3e")).toBeTruthy();
    expect(within(cell("run")).getByText("30e")).toBeTruthy();
  });

  it("n'affiche aucune position pour un segment que le classement n'a pas pu établir", () => {
    const { container } = renderRow({ steps: STEPS.filter((step) => step.segment !== "t1") });

    const t1 = container.querySelector('[data-segment="t1"]') as HTMLElement;
    expect(within(t1).queryByText(/^\d+(er|e)$/)).toBeNull();
    expect(t1.textContent).toContain("00:02:55");
  });

  it("rend un tiret pour un split absent, jamais un zéro", () => {
    const { container } = renderRow({
      row: participation({ splits: { swim: "00:22:52", bike: "01:01:07" } }),
    });

    const valeur = container.querySelector('[data-segment="t1"] [data-time]');
    expect(valeur?.textContent).toBe("—");
    expect(valeur?.textContent).not.toMatch(/\d/);
  });

  it("distingue les transitions des disciplines chronométrées", () => {
    const { container } = renderRow();

    const transition = (key: string) =>
      container.querySelector(`[data-segment="${key}"]`)?.getAttribute("data-transition");

    expect(transition("t1")).toBe("true");
    expect(transition("t2")).toBe("true");
    expect(transition("swim")).toBe("false");
    expect(transition("bike")).toBe("false");
    expect(transition("run")).toBe("false");
  });

  it("délègue le point de rupture de la grille des segments au CSS (#462)", () => {
    const { container } = renderRow();

    const grid = container.querySelector(".result-segments-grid") as HTMLElement;
    expect(grid).toBeTruthy();
    expect(grid.style.gridTemplateColumns).toBe("");
  });

  it("n'ouvre pas de colonne pour un segment que l'épreuve ne publie pas", () => {
    const { container } = renderRow({
      row: participation({
        course: { ...participation().course, event_type: "duathlon-s" },
        splits: { course1: "00:15:00", bike: "00:40:00", course2: "00:18:00" },
      }),
      segments: ["course1", "bike", "course2"],
      steps: [],
    });

    expect(container.querySelector('[data-segment="t1"]')).toBeNull();
    expect(container.querySelectorAll("[data-segment]").length).toBe(3);
  });
});
