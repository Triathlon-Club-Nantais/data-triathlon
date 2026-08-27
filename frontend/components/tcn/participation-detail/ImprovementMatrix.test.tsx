import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { ImprovementRow } from "@/lib/types";
import { ImprovementMatrix } from "./ImprovementMatrix";

const ROWS: ImprovementRow[] = [
  { segment: "swim", gains: { "0.5": 1, "1": 2, "2": 4, "5": 10, "10": 18, "25": 39 } },
  { segment: "t1", gains: { "0.5": 0, "1": 0, "2": 0, "5": 0, "10": 0, "25": 0 } },
  { segment: "bike", gains: { "0.5": 2, "1": 5, "2": 11, "5": 26, "10": 40, "25": 62 } },
  { segment: "t2", gains: { "0.5": 0, "1": 0, "2": 0, "5": 0, "10": 0, "25": 0 } },
];

function renderMatrix(rows = ROWS, eventType = "triathlon-m") {
  return render(<ImprovementMatrix rows={rows} eventType={eventType} />);
}

describe("ImprovementMatrix", () => {
  it("annonce ce que mesurent les colonnes", () => {
    renderMatrix();

    expect(screen.getByText(/si ce segment avait été couru plus vite/i)).toBeTruthy();
  });

  it("affiche les six colonnes de pourcentage", () => {
    renderMatrix();

    for (const pct of ["0,5 %", "1 %", "2 %", "5 %", "10 %", "25 %"]) {
      expect(screen.getByRole("columnheader", { name: pct })).toBeTruthy();
    }
  });

  it("ne garde dans le tableau que les segments où des places sont à gagner", () => {
    renderMatrix();

    expect(screen.getByRole("row", { name: /Natation/ })).toBeTruthy();
    expect(screen.getByRole("row", { name: /Vélo/ })).toBeTruthy();
    expect(screen.queryByRole("row", { name: /T1/ })).toBeNull();
    expect(screen.getAllByRole("row").length).toBe(3); // en-tête + deux segments
  });

  it("marque les places gagnées d'un signe plus", () => {
    renderMatrix();

    const velo = screen.getByRole("row", { name: /Vélo/ });
    expect(within(velo).getByText("+62")).toBeTruthy();
    expect(within(velo).getByText("+11")).toBeTruthy();
  });

  it("nomme hors du tableau les segments qui ne rapportent rien", () => {
    renderMatrix();

    expect(screen.getByText(/T1 et T2 : aucune place gagnée, même 25 % plus vite/)).toBeTruthy();
  });

  it("ne rend aucun tableau quand aucun segment ne rapporte de place", () => {
    renderMatrix([{ segment: "swim", gains: { "0.5": 0, "1": 0, "2": 0, "5": 0, "10": 0, "25": 0 } }]);

    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getByText(/Natation : aucune place gagnée, même 25 % plus vite/)).toBeTruthy();
  });

  it("n'ouvre pas de ligne pour un segment absent du calcul", () => {
    renderMatrix([{ segment: "bike", gains: { "0.5": 2, "1": 5, "2": 11, "5": 26, "10": 40, "25": 62 } }]);

    expect(screen.queryByRole("row", { name: /Natation/ })).toBeNull();
    expect(screen.getAllByRole("row").length).toBe(2);
  });

  // Trois paliers suffisent à lire la courbe ; les autres s'interpolent à
  // l'œil entre eux, et le tableau tient alors dans ~300 px.
  it("ne garde que trois paliers sous sm", () => {
    renderMatrix();

    for (const masque of ["0,5 %", "2 %", "10 %"]) {
      expect(screen.getByRole("columnheader", { name: masque }).className).toContain(
        "hidden sm:table-cell",
      );
    }
    for (const garde of ["1 %", "5 %", "25 %"]) {
      expect(screen.getByRole("columnheader", { name: garde }).className ?? "").not.toContain(
        "hidden",
      );
    }
  });

  it("masque aussi les cellules de ces paliers", () => {
    renderMatrix();

    const natation = screen.getByRole("row", { name: /Natation/ });
    // +18 est le gain à 10 % de la ligne `swim` de `ROWS`.
    expect(within(natation).getByText("+18").className).toContain("hidden sm:table-cell");
  });

  // #657 : un pourcentage de palier n'indiquait pas à quoi il s'appliquait.
  it("#657 : explique au survol ce que représente un palier de pourcentage", () => {
    renderMatrix();

    const palier = screen.getByRole("columnheader", { name: "5 %" });
    expect(palier.title).toMatch(/5 % plus vite/i);
    expect(palier.title).toMatch(/places gagnées/i);
  });

  it("#657 : explique au survol pourquoi une cellule affiche un point plutôt qu'un chiffre", () => {
    renderMatrix([
      { segment: "swim", gains: { "0.5": 0, "1": 2, "2": 4, "5": 10, "10": 18, "25": 39 } },
    ]);

    const natation = screen.getByRole("row", { name: /Natation/ });
    const cellule = within(natation).getByText("·");
    expect(cellule.title).toMatch(/aucune place gagnée/i);
  });
});
