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

  it("avertit sur les segments courts (T1/T2), sensibles au bruit de chronométrage", () => {
    renderTable();

    expect(screen.getByText(/segments courts.*bruit de chronométrage/i)).toBeTruthy();
  });

  it("n'avertit pas quand l'épreuve ne publie aucun segment court", () => {
    renderTable(
      [{ position_label: "1er", rank: 1, percentages: { bike: 124.9, run: 120.0, total: 122.0 } }],
      ["bike", "run"],
      "bike-run",
    );

    expect(screen.queryByText(/bruit de chronométrage/i)).toBeNull();
  });

  it("ne nomme que les segments courts réellement publiés (aquarun, T1 sans T2)", () => {
    renderTable(
      [{ position_label: "1er", rank: 1, percentages: { swim: 120.0, t1: 130.0, run: 118.0, total: 119.0 } }],
      ["swim", "t1", "run"],
      "aquarun",
    );

    const note = screen.getByText(/bruit de chronométrage/i);
    expect(note.textContent).toContain("T1");
    expect(note.textContent).not.toContain("T2");
  });

  // Sept colonnes tombent à ~500 px de large : sur un téléphone, le tableau
  // défile dans sa carte. Les segments courts sortent les premiers — ils sont
  // déjà atténués, et déjà signalés comme bruités par la note du bas.
  it("masque les colonnes des segments courts sous sm", () => {
    renderTable();

    expect(screen.getByRole("columnheader", { name: "T1" }).className).toContain(
      "hidden sm:table-cell",
    );
    expect(screen.getByRole("columnheader", { name: "T2" }).className).toContain(
      "hidden sm:table-cell",
    );
    expect(screen.getByRole("columnheader", { name: "Natation" }).className ?? "").not.toContain(
      "hidden",
    );
  });

  it("masque aussi les cellules de ces colonnes, pas seulement leur en-tête", () => {
    renderTable();

    const premiere = screen.getByRole("row", { name: /1er/ });
    // 137,8 % est la valeur T1 de la première ligne de `ROWS`.
    expect(within(premiere).getByText("137,8 %").className).toContain("hidden sm:table-cell");
  });

  it("dit que les colonnes masquées se lisent sur écran large", () => {
    renderTable();

    expect(screen.getByText(/écran plus large/)).toBeTruthy();
  });

  it("ne réserve le rappel « écran plus large » qu'aux petits écrans, contrairement à l'avertissement sur le bruit (revue finale #461)", () => {
    // Cette phrase-là est fausse dès 640 px, où T1/T2 sont déjà visibles : le
    // lecteur y chercherait des colonnes qu'il a sous les yeux. L'avertissement
    // sur le bruit de chronométrage, lui, reste vrai à toute largeur.
    const { container } = renderTable();

    const rappel = container.querySelector('span[class~="sm:hidden"]');
    expect(rappel?.textContent).toMatch(/écran plus large/);

    const avertissement = screen.getByText(/segments courts.*bruit de chronométrage/i);
    expect(avertissement.className ?? "").not.toContain("sm:hidden");
  });

  it("US4 (#466) : affiche l'écart en secondes brutes sous le pourcentage quand il est fourni", () => {
    renderTable([
      {
        position_label: "1er",
        rank: 1,
        percentages: { bike: 125.0, total: 128.0 },
        mine_seconds: { bike: 4500, total: 7680 },
        theirs_seconds: { bike: 3600, total: 6000 },
      },
    ]);

    const ligne = screen.getByRole("row", { name: /1er/ });
    // 4500 - 3600 = 900 s = 15 min ; 7680 - 6000 = 1680 s = 28 min
    expect(within(ligne).getByText(/\+15 min/)).toBeTruthy();
    expect(within(ligne).getByText(/\+28 min/)).toBeTruthy();
  });

  it("US4 (#466) : n'affiche aucun écart en secondes quand mine_seconds/theirs_seconds sont absents", () => {
    renderTable([{ position_label: "1er", rank: 1, percentages: { bike: 124.9, total: 128.0 } }]);

    const ligne = screen.getByRole("row", { name: /1er/ });
    expect(within(ligne).queryByText(/min|s\)/)).toBeNull();
  });

  it("US4 (#466) : une performance plus rapide que la référence s'affiche en écart négatif", () => {
    renderTable([
      {
        position_label: "1er",
        rank: 1,
        percentages: { bike: 90.0 },
        mine_seconds: { bike: 3240 },
        theirs_seconds: { bike: 3600 },
      },
    ]);

    const ligne = screen.getByRole("row", { name: /1er/ });
    expect(within(ligne).getByText(/−6 min/)).toBeTruthy();
  });
});
