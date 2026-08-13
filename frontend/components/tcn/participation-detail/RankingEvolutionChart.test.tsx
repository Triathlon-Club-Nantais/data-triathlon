import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { RankingEvolutionStep } from "@/lib/types";
import { RankingEvolutionChart } from "./RankingEvolutionChart";

const STEPS: RankingEvolutionStep[] = [
  { segment: "swim", scratch_position: 91, segment_position: 88 },
  { segment: "t1", scratch_position: 91, segment_position: 112 },
  { segment: "bike", scratch_position: 74, segment_position: 68 },
  { segment: "t2", scratch_position: 63, segment_position: 60 },
  { segment: "run", scratch_position: 56, segment_position: 63 },
];

function renderChart(steps = STEPS) {
  return render(<RankingEvolutionChart steps={steps} eventType="triathlon-m" />);
}

const y = (el: Element | null) => Number(el?.getAttribute("data-y"));

describe("RankingEvolutionChart", () => {
  it("trace un point de position scratch par étape", () => {
    const { container } = renderChart();

    const points = container.querySelectorAll('[data-role="scratch"]');
    expect([...points].map((p) => p.getAttribute("data-step"))).toEqual([
      "swim",
      "t1",
      "bike",
      "t2",
      "run",
    ]);
  });

  it("trace une barre de position sur le segment isolé par étape", () => {
    const { container } = renderChart();

    expect(container.querySelectorAll('[data-role="segment"]').length).toBe(5);
  });

  it("place la meilleure position en haut du graphique", () => {
    const { container } = renderChart();

    const meilleure = container.querySelector('[data-role="scratch"][data-step="run"]'); // 56e
    const pire = container.querySelector('[data-role="scratch"][data-step="swim"]'); // 91e
    expect(y(meilleure)).toBeLessThan(y(pire));
  });

  it("calcule ses bornes sur les positions de la course, pas sur une échelle figée", () => {
    const { container } = render(
      <RankingEvolutionChart
        steps={[
          { segment: "swim", scratch_position: 3, segment_position: 4 },
          { segment: "run", scratch_position: 1, segment_position: 2 },
        ]}
        eventType="aquathlon"
      />,
    );

    // Sur une course où l'athlète oscille entre la 1re et la 4e place, l'écart
    // vertical entre ses deux points doit rester lisible, pas écrasé.
    const premier = container.querySelector('[data-role="scratch"][data-step="run"]');
    const troisieme = container.querySelector('[data-role="scratch"][data-step="swim"]');
    expect(y(troisieme) - y(premier)).toBeGreaterThan(20);
  });

  it("affiche l'étape et la position scratch au survol d'un point", async () => {
    const user = userEvent.setup();
    const { container } = renderChart();

    await user.hover(container.querySelector('[data-role="scratch"][data-step="bike"]')!);

    const infobulle = screen.getByRole("tooltip");
    expect(infobulle.textContent).toContain("Vélo");
    expect(infobulle.textContent).toContain("74");
  });

  it("affiche la position sur le segment au survol d'une barre", async () => {
    const user = userEvent.setup();
    const { container } = renderChart();

    await user.hover(container.querySelector('[data-role="segment"][data-step="bike"]')!);

    const infobulle = screen.getByRole("tooltip");
    expect(infobulle.textContent).toContain("Vélo");
    expect(infobulle.textContent).toContain("68");
  });

  it("ne montre qu'une seule infobulle à la fois", async () => {
    const user = userEvent.setup();
    const { container } = renderChart();

    await user.hover(container.querySelector('[data-role="scratch"][data-step="swim"]')!);
    await user.hover(container.querySelector('[data-role="scratch"][data-step="run"]')!);

    expect(screen.getAllByRole("tooltip").length).toBe(1);
    expect(screen.getByRole("tooltip").textContent).toContain("56");
  });

  it("n'affiche aucune infobulle tant que rien n'est survolé", () => {
    renderChart();

    expect(screen.queryByRole("tooltip")).toBeNull();
  });
});
