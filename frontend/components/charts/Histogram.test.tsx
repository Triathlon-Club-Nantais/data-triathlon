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

  it("gradue l'axe Y de 0 au maximum", () => {
    const { container } = render(
      <Histogram bars={[10]} max={10} startSec={0} bucketSec={60} />,
    );
    const labels = [...container.querySelectorAll("text")].map((t) => t.textContent);
    expect(labels).toContain("0");
    expect(labels).toContain("10");
  });

  it("aligne les graduations X sur des multiples ronds du pas (#129)", () => {
    // 6 tranches de 15 min = 90 min de fenêtre → pas de 15 min (histogram-ticks.ts).
    const { container } = render(
      <Histogram bars={[1, 1, 1, 1, 1, 1]} max={1} startSec={0} bucketSec={900} />,
    );
    const labels = [...container.querySelectorAll("text")].map((t) => t.textContent);
    expect(labels).toContain("0:15");
    expect(labels).toContain("1:30");
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
});
