import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ProgressionChart } from "./ProgressionChart";
import type { ProgressionPoint } from "@/lib/utils/ranking";

function point(over: Partial<ProgressionPoint> & { participationId: number }): ProgressionPoint {
  return {
    participationId: over.participationId,
    eventDate: over.eventDate ?? "2026-01-01",
    percent: over.percent ?? 20,
  };
}

describe("ProgressionChart", () => {
  it("trace un point par participation exploitable", () => {
    const { container } = render(
      <ProgressionChart
        points={[
          point({ participationId: 1, eventDate: "2026-01-10", percent: 40 }),
          point({ participationId: 2, eventDate: "2026-03-10", percent: 25 }),
          point({ participationId: 3, eventDate: "2026-05-10", percent: 10 }),
        ]}
      />,
    );
    // Rendu serveur pur : la géométrie est déjà dans le SVG initial, aucun
    // état ni effet ne doit conditionner son apparition.
    expect(container.querySelectorAll("[data-point]").length).toBe(3);
    expect(container.querySelector("path")).not.toBeNull();
  });

  it("affiche un axe des ordonnées gradué (#677)", () => {
    const { container } = render(
      <ProgressionChart
        points={[
          point({ participationId: 1, eventDate: "2026-01-10", percent: 40 }),
          point({ participationId: 2, eventDate: "2026-03-10", percent: 25 }),
          point({ participationId: 3, eventDate: "2026-05-10", percent: 10 }),
        ]}
      />,
    );
    expect(container.querySelectorAll("[data-tick]").length).toBeGreaterThanOrEqual(2);
    expect(container.querySelectorAll("svg line").length).toBeGreaterThanOrEqual(2);
  });

  it("affiche le pourcentage de chaque point en permanence, sans survol (#677)", () => {
    const { getByText } = render(
      <ProgressionChart
        points={[
          point({ participationId: 1, eventDate: "2026-01-10", percent: 40 }),
          point({ participationId: 2, eventDate: "2026-03-10", percent: 25 }),
          point({ participationId: 3, eventDate: "2026-05-10", percent: 10 }),
        ]}
      />,
    );
    expect(getByText("Top 40 %")).toBeInTheDocument();
    expect(getByText("Top 25 %")).toBeInTheDocument();
    expect(getByText("Top 10 %")).toBeInTheDocument();
  });

  it("ne grade jamais l'axe au-delà de 100 % (#677, revue de code)", () => {
    // Un dernier de course a percent=100 (rankRatio refuse rank > total) : la
    // marge ajoutée à `worst` ne doit pas produire une graduation « 114 % ».
    const { container } = render(
      <ProgressionChart
        points={[
          point({ participationId: 1, eventDate: "2026-01-10", percent: 10 }),
          point({ participationId: 2, eventDate: "2026-03-10", percent: 50 }),
          point({ participationId: 3, eventDate: "2026-05-10", percent: 100 }),
        ]}
      />,
    );
    const tickTexts = Array.from(container.querySelectorAll("[data-tick]")).map((el) => el.textContent ?? "");
    for (const text of tickTexts) {
      const value = Number(text.replace("%", "").trim());
      expect(value).toBeLessThanOrEqual(100);
    }
  });

  it("trace un segment droit entre les points, pas une courbe lissée (#677)", () => {
    const { container } = render(
      <ProgressionChart
        points={[
          point({ participationId: 1, eventDate: "2026-01-10", percent: 40 }),
          point({ participationId: 2, eventDate: "2026-03-10", percent: 25 }),
          point({ participationId: 3, eventDate: "2026-05-10", percent: 10 }),
        ]}
      />,
    );
    // `curveLinear` n'émet que des commandes M/L ; `curveMonotoneX` (rejeté,
    // #677) émettrait des courbes de Bézier cubiques (commande C) qui
    // dessineraient un creux ou un sommet absent des données.
    const d = container.querySelector("path")?.getAttribute("d") ?? "";
    expect(d).not.toMatch(/C/);
  });

  it("explique la lecture du graphique en légende (#677)", () => {
    const { getByText } = render(
      <ProgressionChart
        points={[
          point({ participationId: 1, eventDate: "2026-01-10", percent: 40 }),
          point({ participationId: 2, eventDate: "2026-03-10", percent: 25 }),
          point({ participationId: 3, eventDate: "2026-05-10", percent: 10 }),
        ]}
      />,
    );
    getByText(/classement au sein du peloton/i);
  });

  it("affiche un état vide explicite sous 3 points de données", () => {
    const { container, getByText } = render(
      <ProgressionChart points={[point({ participationId: 1 }), point({ participationId: 2 })]} />,
    );
    expect(container.querySelector("svg")).toBeNull();
    getByText(/pas encore assez d.épreuves/i);
  });

  // The last label used to stick out by half a column past the right edge,
  // which made the whole athlete page scroll horizontally (#1139).
  it.each([3, 5, 12])("keeps every label box inside the chart row with %i points (#1139)", (count) => {
    const points = Array.from({ length: count }, (_, index) =>
      point({ participationId: index + 1, eventDate: "2026-01-10", percent: 10 + index }),
    );
    const { getByText } = render(<ProgressionChart points={points} />);

    for (const p of points) {
      const box = getByText(`Top ${p.percent} %`).parentElement as HTMLElement;
      expect(box.style.left).toMatch(/^[\d.]+%$/);
      expect(box.style.width).toMatch(/^[\d.]+%$/);
      const left = parseFloat(box.style.left);
      expect(left).toBeGreaterThanOrEqual(0);
      expect(left + parseFloat(box.style.width)).toBeLessThanOrEqual(100 + 1e-9);
    }
  });

  it("affiche un état vide explicite sans aucun point", () => {
    const { container } = render(<ProgressionChart points={[]} />);
    expect(container.querySelector("svg")).toBeNull();
  });
});
