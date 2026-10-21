import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ProgressionChart, type ProgressionAxis } from "./ProgressionChart";
import { formatDuration } from "@/lib/utils/duration";
import type { ProgressionPoint } from "@/lib/utils/ranking";

function point(over: Partial<ProgressionPoint> & { id: number }): ProgressionPoint {
  return {
    id: over.id,
    eventDate: over.eventDate ?? "2026-01-01",
    value: over.value ?? 20,
  };
}

describe("ProgressionChart", () => {
  it("trace un point par participation exploitable", () => {
    const { container } = render(
      <ProgressionChart
        points={[
          point({ id: 1, eventDate: "2026-01-10", value: 40 }),
          point({ id: 2, eventDate: "2026-03-10", value: 25 }),
          point({ id: 3, eventDate: "2026-05-10", value: 10 }),
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
          point({ id: 1, eventDate: "2026-01-10", value: 40 }),
          point({ id: 2, eventDate: "2026-03-10", value: 25 }),
          point({ id: 3, eventDate: "2026-05-10", value: 10 }),
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
          point({ id: 1, eventDate: "2026-01-10", value: 40 }),
          point({ id: 2, eventDate: "2026-03-10", value: 25 }),
          point({ id: 3, eventDate: "2026-05-10", value: 10 }),
        ]}
      />,
    );
    expect(getByText("Top 40 %")).toBeInTheDocument();
    expect(getByText("Top 25 %")).toBeInTheDocument();
    expect(getByText("Top 10 %")).toBeInTheDocument();
  });

  it("lie chaque « % » à son nombre par une espace fine insécable (#1600)", () => {
    const { container, getByText } = render(
      <ProgressionChart
        points={[
          point({ id: 1, eventDate: "2026-01-10", value: 40 }),
          point({ id: 2, eventDate: "2026-03-10", value: 25 }),
          point({ id: 3, eventDate: "2026-05-10", value: 10 }),
        ]}
      />,
    );
    expect(getByText("Top 40 %").textContent).toBe("Top 40\u202f%");
    for (const tick of container.querySelectorAll("[data-tick]")) {
      expect(tick.textContent).toMatch(/^\d+\u202f%$/);
    }
  });

  it("ne grade jamais l'axe au-delà de 100 % (#677, revue de code)", () => {
    // Un dernier de course a percent=100 (rankRatio refuse rank > total) : la
    // marge ajoutée à `worst` ne doit pas produire une graduation « 114 % ».
    const { container } = render(
      <ProgressionChart
        points={[
          point({ id: 1, eventDate: "2026-01-10", value: 10 }),
          point({ id: 2, eventDate: "2026-03-10", value: 50 }),
          point({ id: 3, eventDate: "2026-05-10", value: 100 }),
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
          point({ id: 1, eventDate: "2026-01-10", value: 40 }),
          point({ id: 2, eventDate: "2026-03-10", value: 25 }),
          point({ id: 3, eventDate: "2026-05-10", value: 10 }),
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
          point({ id: 1, eventDate: "2026-01-10", value: 40 }),
          point({ id: 2, eventDate: "2026-03-10", value: 25 }),
          point({ id: 3, eventDate: "2026-05-10", value: 10 }),
        ]}
      />,
    );
    getByText(/classement au sein du peloton/i);
  });

  it("affiche un état vide explicite sous 3 points de données", () => {
    const { container, getByText } = render(
      <ProgressionChart points={[point({ id: 1 }), point({ id: 2 })]} />,
    );
    expect(container.querySelector("svg")).toBeNull();
    getByText(/pas encore assez d.épreuves/i);
  });

  // The last label used to stick out by half a column past the right edge,
  // which made the whole athlete page scroll horizontally (#1139).
  it.each([3, 5, 12])("keeps every label box inside the chart row with %i points (#1139)", (count) => {
    const points = Array.from({ length: count }, (_, index) =>
      point({ id: index + 1, eventDate: "2026-01-10", value: 10 + index }),
    );
    const { getByText } = render(<ProgressionChart points={points} />);

    for (const p of points) {
      const box = getByText(`Top ${p.value} %`).parentElement as HTMLElement;
      expect(box.style.left).toMatch(/^[\d.]+%$/);
      expect(box.style.width).toMatch(/^[\d.]+%$/);
      const left = parseFloat(box.style.left);
      expect(left).toBeGreaterThanOrEqual(0);
      expect(left + parseFloat(box.style.width)).toBeLessThanOrEqual(100 + 1e-9);
    }
  });

  // Rabattre les boîtes d'extrémité ne doit pas les faire chevaucher leur voisine.
  it.each([3, 5, 12])("keeps neighbouring label boxes apart with %i points (#1139)", (count) => {
    const points = Array.from({ length: count }, (_, index) =>
      point({ id: index + 1, eventDate: "2026-01-10", value: 10 + index }),
    );
    const { getByText } = render(<ProgressionChart points={points} />);

    const boxes = points.map((p) => {
      const style = (getByText(`Top ${p.value} %`).parentElement as HTMLElement).style;
      return { left: parseFloat(style.left), right: parseFloat(style.left) + parseFloat(style.width) };
    });
    for (let index = 0; index + 1 < boxes.length; index++) {
      expect(boxes[index + 1].left).toBeGreaterThanOrEqual(boxes[index].right - 1e-9);
    }
  });

  it("affiche un état vide explicite sans aucun point", () => {
    const { container } = render(<ProgressionChart points={[]} />);
    expect(container.querySelector("svg")).toBeNull();
  });
});

describe("ProgressionChart axe", () => {
  it("trace une durée avec son propre axe", () => {
    const axis: ProgressionAxis = {
      max: 864000,
      tick: formatDuration,
      label: formatDuration,
      spoken: (v) => formatDuration(v),
      caption: "Durée du test, plus bas, meilleur.",
      ariaLabel: "Évolution de la durée",
      emptyTitle: "Pas encore assez de tests",
      emptyDescription: "Trois tests sont nécessaires.",
    };
    const { container, getByText, queryByText } = render(
      <ProgressionChart
        axis={axis}
        points={[
          point({ id: 1, eventDate: "2026-01-10", value: 450 }),
          point({ id: 2, eventDate: "2026-03-10", value: 430 }),
          point({ id: 3, eventDate: "2026-05-10", value: 423 }),
        ]}
      />,
    );
    getByText("42,3 s");
    getByText("Durée du test, plus bas, meilleur.");
    expect(queryByText(/classement au sein du peloton/i)).toBeNull();
    expect(container.textContent).not.toContain("%");
  });
});

describe("ProgressionChart comparaison", () => {
  it("draws the comparison dashed", () => {
    const serie = [10, 20, 30].map((value, i) => point({ id: i + 1, eventDate: `2026-0${i + 1}-10`, value }));
    const { container } = render(<ProgressionChart points={serie} comparaison={serie.map((p) => ({ ...p, id: p.id + 10 }))} />);
    expect(container.querySelectorAll("svg path")).toHaveLength(2);
    expect(container.querySelectorAll("svg path")[1]).toHaveAttribute("stroke-dasharray");
  });
});

describe("ProgressionChart alignement", () => {
  it("puts the same calendar day of two seasons at the same x", () => {
    const courant = [point({ id: 1, eventDate: "2026-10-15", value: 30 }), point({ id: 2, eventDate: "2027-01-10", value: 20 }), point({ id: 3, eventDate: "2027-03-10", value: 10 })];
    const precedent = [point({ id: 10, eventDate: "2025-09-20", value: 50 }), point({ id: 11, eventDate: "2025-10-15", value: 40 }), point({ id: 12, eventDate: "2026-02-10", value: 35 })];
    const { container } = render(<ProgressionChart points={courant} comparaison={precedent} />);
    const [plein, tirets] = Array.from(container.querySelectorAll("svg path")).map((p) => p.getAttribute("d")!);
    expect(plein.split("L")[0].slice(1).split(",")[0]).toBe(tirets.split("L")[1].split(",")[0]);
  });
});
