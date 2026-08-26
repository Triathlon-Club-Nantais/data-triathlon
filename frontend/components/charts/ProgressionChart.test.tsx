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

  it("affiche un état vide explicite sous 3 points de données", () => {
    const { container, getByText } = render(
      <ProgressionChart points={[point({ participationId: 1 }), point({ participationId: 2 })]} />,
    );
    expect(container.querySelector("svg")).toBeNull();
    getByText(/pas encore assez d.épreuves/i);
  });

  it("affiche un état vide explicite sans aucun point", () => {
    const { container } = render(<ProgressionChart points={[]} />);
    expect(container.querySelector("svg")).toBeNull();
  });
});
