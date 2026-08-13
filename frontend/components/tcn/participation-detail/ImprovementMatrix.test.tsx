import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { ImprovementRow } from "@/lib/types";
import { ImprovementMatrix } from "./ImprovementMatrix";

const ROWS: ImprovementRow[] = [
  { segment: "swim", gains: { "0.5": 1, "1": 2, "2": 4, "5": 10, "10": 18, "25": 39 } },
  { segment: "t1", gains: { "0.5": 0, "1": 1, "2": 1, "5": 1, "10": 2, "25": 5 } },
  { segment: "bike", gains: { "0.5": 2, "1": 5, "2": 11, "5": 26, "10": 40, "25": 62 } },
];

function renderMatrix(rows = ROWS, eventType = "triathlon-m") {
  return render(<ImprovementMatrix rows={rows} eventType={eventType} />);
}

describe("ImprovementMatrix", () => {
  it("rend une ligne par segment fourni", () => {
    renderMatrix();

    expect(screen.getByRole("row", { name: /Natation/ })).toBeTruthy();
    expect(screen.getByRole("row", { name: /Vélo/ })).toBeTruthy();
    expect(screen.getAllByRole("row").length).toBe(4); // en-tête + trois segments
  });

  it("affiche les six colonnes de pourcentage", () => {
    renderMatrix();

    for (const pct of ["0,5 %", "1 %", "2 %", "5 %", "10 %", "25 %"]) {
      expect(screen.getByRole("columnheader", { name: pct })).toBeTruthy();
    }
  });

  it("affiche le nombre de places gagnées tel que l'API le fournit", () => {
    renderMatrix();

    const velo = screen.getByRole("row", { name: /Vélo/ });
    expect(within(velo).getByText("62")).toBeTruthy();
    expect(within(velo).getByText("11")).toBeTruthy();
  });

  it("affiche un gain nul sans le maquiller", () => {
    const t1 = renderMatrix().container.querySelector('[data-segment="t1"]');

    expect(within(t1 as HTMLElement).getAllByText("0").length).toBe(1);
  });

  it("n'ouvre pas de ligne pour un segment absent du calcul", () => {
    renderMatrix([{ segment: "bike", gains: { "0.5": 2, "1": 5, "2": 11, "5": 26, "10": 40, "25": 62 } }]);

    expect(screen.queryByRole("row", { name: /Natation/ })).toBeNull();
    expect(screen.getAllByRole("row").length).toBe(2);
  });
});
