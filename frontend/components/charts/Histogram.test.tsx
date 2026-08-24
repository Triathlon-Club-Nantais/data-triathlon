import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Histogram } from "./Histogram";

describe("Histogram", () => {
  it("trace une barre par tranche de temps", () => {
    const { container } = render(
      <Histogram bars={[2, 5, 3]} max={5} startSec={0} bucketSec={300} />,
    );
    expect(container.querySelectorAll("rect").length).toBe(3);
  });

  it("la barre avec le plus de finishers est la plus haute", () => {
    const { container } = render(
      <Histogram bars={[2, 5, 3]} max={5} startSec={0} bucketSec={300} />,
    );
    const heights = [...container.querySelectorAll("rect")].map((r) =>
      Number(r.getAttribute("height")),
    );
    expect(heights[1]).toBeGreaterThan(heights[0]);
    expect(heights[1]).toBeGreaterThan(heights[2]);
  });

  it("n'affiche aucune barre quand max est nul (aucun finisher)", () => {
    const { container } = render(
      <Histogram bars={[0, 0]} max={0} startSec={0} bucketSec={300} />,
    );
    const heights = [...container.querySelectorAll("rect")].map((r) =>
      Number(r.getAttribute("height")),
    );
    expect(heights).toEqual([0, 0]);
  });

  it("aligne les graduations X sur des multiples ronds du pas (#129)", () => {
    // 6 tranches de 15 min = 90 min de fenêtre → pas de 15 min (histogram-ticks.ts).
    const { container } = render(
      <Histogram bars={[1, 1, 1, 1, 1, 1]} max={1} startSec={0} bucketSec={900} />,
    );
    const labels = [...container.querySelectorAll("[data-x-tick]")].map((t) => t.textContent);
    expect(labels).toContain("0:15");
    expect(labels).toContain("1:30");
  });

  it("ne met plus aucun texte dans le SVG", () => {
    // Un <text> dans un viewBox étiré à width:100% se réduit à 3,5px sur un
    // iPhone SE (facteur 0,32). Aucune unité CSS ne l'en empêche : le texte doit
    // sortir du SVG (#480, RESP-2).
    const { container } = render(
      <Histogram bars={[1, 2, 3]} max={3} startSec={0} bucketSec={300} />,
    );
    expect(container.querySelectorAll("svg text").length).toBe(0);
  });

  it("garde une hauteur en pixels, pour que les libellés HTML s'alignent", () => {
    const { container } = render(
      <Histogram bars={[1, 2, 3]} max={3} startSec={0} bucketSec={300} />,
    );
    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("preserveAspectRatio")).toBe("none");
    expect((svg as unknown as HTMLElement).style.height).toBe("200px");
  });

  it("gradue l'axe Y de 0 au maximum, en HTML", () => {
    const { container } = render(
      <Histogram bars={[10]} max={10} startSec={0} bucketSec={60} />,
    );
    const ticks = [...container.querySelectorAll("[data-y-tick]")].map(
      (n) => n.textContent,
    );
    expect(ticks).toContain("0");
    expect(ticks).toContain("10");
  });

  it("récapitule la distribution pour un lecteur d'écran", () => {
    render(<Histogram bars={[2, 5, 3]} max={5} startSec={1800} bucketSec={300} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Distribution des temps d'arrivée, de 0:30 à 0:45, maximum 5 finishers sur une tranche.",
    );
  });

  it("reste un bandeau large plutôt qu'un pavé", () => {
    const { container } = render(
      <Histogram bars={[1, 2, 3]} max={3} startSec={0} bucketSec={300} />,
    );
    const [, , w, h] = container
      .querySelector("svg")!
      .getAttribute("viewBox")!
      .split(" ")
      .map(Number);
    expect(h / w).toBeLessThanOrEqual(0.3);
  });

  it("garde les lignes de graduation Y également espacées quand max n'est pas divisible par 5", () => {
    // Regression test: max=3 n'est pas divisible par 5 (yTicks).
    // Les lignes doivent rester espacées régulièrement par indice i,
    // pas collapsées parce qu'on aurait arrondi (max/yTicks)*i.
    const { container } = render(
      <Histogram bars={[1, 2, 3]} max={3} startSec={0} bucketSec={300} />,
    );
    const lines = [...container.querySelectorAll("line")].filter(
      (line) => line.getAttribute("x1") !== line.getAttribute("x2"),
    ); // Sélectionne les lignes Y (horizontales) uniquement
    const y1Values = lines.map((line) => Number(line.getAttribute("y1")));
    // 6 lignes Y (i=0 à 5), i.e. 6 positions distinctes
    expect(y1Values.length).toBe(6);
    const uniqueY1 = new Set(y1Values);
    expect(uniqueY1.size).toBe(6);
    // Espace constant entre les positions successives
    const differences = [];
    for (let i = 1; i < y1Values.length; i++) {
      differences.push(y1Values[i - 1] - y1Values[i]);
    }
    const expectedStep = 35.2; // (BOTTOM - TOP) / Y_TICKS = (188 - 12) / 5 = 35.2
    differences.forEach((diff) => {
      expect(Math.abs(diff - expectedStep)).toBeLessThan(0.01);
    });
  });

  it("garde les lignes de graduation Y également espacées même quand max=0", () => {
    // Regression test: avec max=0, les gridlines ne doivent pas s'effondrer
    // toutes sur bottom. L'espace-i-basé doit persister.
    const { container } = render(
      <Histogram bars={[0, 0]} max={0} startSec={0} bucketSec={300} />,
    );
    const lines = [...container.querySelectorAll("line")].filter(
      (line) => line.getAttribute("x1") !== line.getAttribute("x2"),
    ); // Lignes Y uniquement
    const y1Values = lines.map((line) => Number(line.getAttribute("y1")));
    // 6 lignes Y (i=0 à 5), i.e. 6 positions distinctes (pas toutes à bottom=190)
    expect(y1Values.length).toBe(6);
    const uniqueY1 = new Set(y1Values);
    expect(uniqueY1.size).toBe(6);
    // Espace constant
    const differences = [];
    for (let i = 1; i < y1Values.length; i++) {
      differences.push(y1Values[i - 1] - y1Values[i]);
    }
    const expectedStep = 35.2; // (BOTTOM - TOP) / Y_TICKS = (188 - 12) / 5 = 35.2
    differences.forEach((diff) => {
      expect(Math.abs(diff - expectedStep)).toBeLessThan(0.01);
    });
  });
});
