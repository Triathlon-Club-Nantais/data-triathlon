import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { ComparisonRow } from "@/lib/types";
import { ComparisonTable } from "./ComparisonTable";

const SEGMENTS = ["swim", "t1", "bike", "t2", "run"];

const ROWS: ComparisonRow[] = [
  {
    position_label: "1er",
    rank: 1,
    percentages: { swim: 141.6, t1: 137.8, bike: 124.9, t2: 139.0, run: 124.0, total: 128.0 },
  },
  {
    position_label: "10e",
    rank: 10,
    percentages: { swim: 112.8, t1: 130.6, bike: 112.4, t2: 115.2, run: 109.0, total: 112.0 },
  },
];

function renderTable(rows = ROWS, segments = SEGMENTS, eventType = "triathlon-m") {
  return render(<ComparisonTable rows={rows} segments={segments} eventType={eventType} />);
}

describe("ComparisonTable", () => {
  it("rend une ligne par position de référence fournie", () => {
    renderTable();

    expect(screen.getByRole("row", { name: /1er/ })).toBeTruthy();
    expect(screen.getByRole("row", { name: /10e/ })).toBeTruthy();
  });

  it("affiche les pourcentages par segment et sur le total", () => {
    renderTable();

    const premiere = screen.getByRole("row", { name: /1er/ });
    expect(within(premiere).getByText("141,6 %")).toBeTruthy();
    expect(within(premiere).getByText("128,0 %")).toBeTruthy();
  });

  it("n'affiche pas les positions que l'épreuve n'atteint pas", () => {
    renderTable();

    expect(screen.queryByRole("row", { name: /100e/ })).toBeNull();
    expect(screen.getAllByRole("row").length).toBe(3); // en-tête + deux positions
  });

  it("rend un tiret quand un pourcentage n'a pas pu être calculé", () => {
    renderTable([{ position_label: "1er", rank: 1, percentages: { bike: 124.9, total: 128.0 } }]);

    const ligne = screen.getByRole("row", { name: /1er/ });
    expect(within(ligne).getAllByText("—").length).toBe(4); // swim, t1, t2, run
  });

  it("garde la colonne de position étroite, le reste de la largeur allant aux segments", () => {
    renderTable();

    const position = screen.getAllByRole("columnheader")[0] as HTMLElement;
    expect(position.style.width).toBe("72px");
  });

  it("limite les colonnes aux segments publiés par l'épreuve", () => {
    renderTable(
      [{ position_label: "1er", rank: 1, percentages: { course1: 120.0, total: 118.0 } }],
      ["course1", "bike", "course2"],
      "duathlon-s",
    );

    expect(screen.queryByRole("columnheader", { name: /T1/ })).toBeNull();
    // trois segments + la colonne de position + la colonne total
    expect(screen.getAllByRole("columnheader").length).toBe(5);
  });
});
