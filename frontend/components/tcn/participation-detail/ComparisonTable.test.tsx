import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { ComparisonRow, MedianRow } from "@/lib/types";
import { ComparisonTable, pctTint } from "./ComparisonTable";
import { contrast, evalue, resolve, surSurface } from "@/test/couleur";

const SEGMENTS = ["swim", "t1", "bike", "t2", "run"];

// Athlète au chronométrage complet : un tiret sur une médiane n'y vient que de l'effectif.
const ATHLETE = {
  splits: { swim: "00:20:00", t1: "00:01:30", bike: "01:05:00", t2: "00:01:00", run: "00:40:00" },
  total_time: "02:07:30",
};

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
  return render(<ComparisonTable rows={rows} segments={segments} eventType={eventType} athlete={ATHLETE} />);
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

  // #657 : les pourcentages n'indiquaient pas à quoi ils se comparaient.
  it("#657 : explique au survol ce que compare la colonne Référence", () => {
    renderTable();

    // #1362 : « Référence » plutôt que « Position », une médiane n'en est pas une.
    const reference = screen.getByRole("columnheader", { name: "Référence" });
    expect(reference.title).toMatch(/classement scratch/i);
    expect(reference.title).toMatch(/médiane/i);
  });

  it("#657 : explique au survol ce que représente un pourcentage de segment", () => {
    renderTable();

    const natation = screen.getByRole("columnheader", { name: "Natation" });
    expect(natation.title).toMatch(/pourcentage du temps/i);
    expect(natation.title).toMatch(/référence de la ligne, position ou médiane/i);
  });

  it("#657 : explique au survol le pourcentage total différemment d'un segment", () => {
    renderTable();

    const total = screen.getByRole("columnheader", { name: "Total" });
    expect(total.title).toMatch(/ensemble de l'épreuve/i);
    // Un seul « athlète » par phrase : l'autre temps est celui de la référence.
    expect(total.title).toMatch(/du temps de référence de la ligne/i);
    // La page s'ouvre pour n'importe quel participant, pas pour le seul lecteur (#1086).
    for (const entete of screen.getAllByRole("columnheader")) {
      expect(entete.title).not.toMatch(/votre/i);
    }
  });

  // #853 : la barre de taille par cellule a été retirée au profit d'un léger
  // dégradé de fond (orange = plus lent, vert = plus rapide que la référence).
  it("#853 : teinte en orange une cellule au-dessus de 100 % (plus lent que la référence)", () => {
    renderTable([{ position_label: "1er", rank: 1, percentages: { bike: 124.9, total: 128.0 } }]);

    const ligne = screen.getByRole("row", { name: /1er/ });
    const cellule = within(ligne).getByText("124,9 %").closest("td") as HTMLElement;
    expect(cellule.style.background).toContain("var(--tcn-orange)");
  });

  it("#853 : teinte en vert une cellule au-dessous de 100 % (plus rapide que la référence)", () => {
    renderTable([{ position_label: "1er", rank: 1, percentages: { bike: 90.0, total: 92.0 } }]);

    const ligne = screen.getByRole("row", { name: /1er/ });
    const cellule = within(ligne).getByText("90,0 %").closest("td") as HTMLElement;
    expect(cellule.style.background).toContain("var(--tcn-success)");
  });

  it("#853 : ne teinte pas une cellule exactement à 100 % ou sans pourcentage calculé", () => {
    renderTable([{ position_label: "1er", rank: 1, percentages: { bike: 100.0, total: 118.0 } }]);

    const ligne = screen.getByRole("row", { name: /1er/ });
    const celluleEgale = within(ligne).getByText("100,0 %").closest("td") as HTMLElement;
    expect(celluleEgale.style.background).toBe("");

    const celluleAbsente = within(ligne).getAllByText("—")[0].closest("td") as HTMLElement;
    expect(celluleAbsente.style.background).toBe("");
  });
});

describe("#1362 : médianes", () => {
  const MEDIANES: MedianRow[] = [
    { kind: "median", label: "Médiane", sample_size: 58, percentages: { swim: 95.0, total: 97.5 } },
    {
      kind: "category_median",
      label: "Médiane catégorie",
      sample_size: 12,
      percentages: { swim: 99.0, total: 101.2 },
      mine_seconds: { total: 3640 },
      theirs_seconds: { total: 3600 },
    },
  ];

  function renderWithMedians(medians: MedianRow[] = MEDIANES, athlete = ATHLETE) {
    return render(
      <ComparisonTable
        rows={ROWS}
        medians={medians}
        segments={SEGMENTS}
        eventType="triathlon-m"
        athlete={athlete}
      />,
    );
  }

  it("rend les médianes après les positions de référence", () => {
    renderWithMedians();

    const lignes = screen.getAllByRole("row").map((ligne) => ligne.textContent ?? "");
    expect(lignes.length).toBe(5);
    expect(lignes[3]).toMatch(/^Médiane58 classés/);
    expect(lignes[4]).toMatch(/^Médiane catégorie12 classés/);
  });

  it("compare chaque segment à la médiane, pourcentage et écart brut", () => {
    renderWithMedians();

    const categorie = screen.getByRole("row", { name: /Médiane catégorie/ });
    expect(within(categorie).getByText("101,2 %")).toBeTruthy();
    expect(within(categorie).getByText("+40 s")).toBeTruthy();
  });

  it("n'affiche aucune ligne de médiane quand l'effectif n'en permet aucune", () => {
    renderWithMedians([]);

    expect(screen.queryByText(/Médiane/)).toBeNull();
    expect(screen.queryByText(/classés/)).toBeNull();
  });

  it("tolère une réponse sans bloc de médianes", () => {
    renderTable();

    expect(screen.getAllByRole("row").length).toBe(3);
  });

  it("sépare la première médiane des positions par un filet", () => {
    renderWithMedians();

    const lignes = screen.getAllByRole("row");
    const premiereMediane = within(lignes[3]).getByRole("rowheader");
    expect(premiereMediane.style.borderTop).toContain("var(--tcn-border)");
    expect(within(lignes[4]).getByRole("rowheader").style.borderTop).toBe("");
    expect(within(lignes[2]).getByRole("rowheader").style.borderTop).toBe("");
  });

  it("explique le tiret d'une médiane faute de classés suffisants", () => {
    renderWithMedians();

    expect(screen.getByText(/trop peu de classés ont publié/)).toBeTruthy();
  });

  it("ne l'explique pas quand chaque médiane couvre toutes les colonnes", () => {
    const completes = MEDIANES.map((row) => ({
      ...row,
      percentages: Object.fromEntries([...SEGMENTS, "total"].map((key) => [key, 100.0])),
    }));
    renderWithMedians(completes);

    expect(screen.queryByText(/trop peu de classés/)).toBeNull();
  });

  it("#1470 : ne blâme pas l'effectif quand c'est l'athlète qui n'a pas le segment", () => {
    // 300 classés, natation publiée par la majorité : seul l'athlète n'a pas de temps de natation.
    render(
      <ComparisonTable
        rows={[]}
        medians={[{ kind: "median", label: "Médiane", sample_size: 300, percentages: { bike: 95, run: 101, total: 98 } }]}
        segments={["swim", "bike", "run"]}
        eventType="triathlon-m"
        athlete={{ splits: { bike: "01:05:00", run: "00:40:00" }, total_time: "02:07:30" }}
      />,
    );

    expect(within(screen.getByRole("row", { name: /Médiane/ })).getByText("—")).toBeTruthy();
    expect(screen.queryByText(/trop peu de classés/)).toBeNull();
  });

  it("#1470 : ne nomme que les segments manquants faute d'effectif", () => {
    render(
      <ComparisonTable
        rows={[]}
        medians={[{ kind: "median", label: "Médiane", sample_size: 300, percentages: { run: 101, total: 98 } }]}
        segments={["swim", "bike", "run"]}
        eventType="triathlon-m"
        athlete={{ splits: { bike: "01:05:00", run: "00:40:00" }, total_time: "02:07:30" }}
      />,
    );

    expect(
      screen.getByText("Médiane non calculée pour Vélo : trop peu de classés ont publié ce segment."),
    ).toBeTruthy();
  });

  it("#1470 : accorde la note au pluriel", () => {
    renderWithMedians();

    expect(
      screen.getByText(
        "Médiane non calculée pour T1, Vélo, T2, Course : trop peu de classés ont publié ces segments.",
      ),
    ).toBeTruthy();
  });

  it("#1470 : un temps illisible chez l'athlète compte comme absent", () => {
    const sansTotal = { ...ATHLETE, total_time: "02:07:30.4" };
    const completes = MEDIANES.map((row) => ({
      ...row,
      percentages: Object.fromEntries(SEGMENTS.map((key) => [key, 100.0])),
    }));
    renderWithMedians(completes, sansTotal);

    expect(screen.queryByText(/trop peu de classés/)).toBeNull();
  });

  it("marque les segments courts comme indicatifs", () => {
    renderWithMedians();

    expect(screen.getByText(/segments courts \(T1, T2\) sont indicatifs/)).toBeTruthy();
  });
});

describe("#853 : contraste WCAG 1.4.3 du dégradé de teinte", () => {
  // La teinte est un fond composite (`color-mix(..., transparent)` sur la
  // carte, `--tcn-surface`) : c'est ce mélange, pas le token seul, qui porte
  // le texte. Au plafond (10 %, ≥ 50 points d'écart, un cas réaliste — comparer
  // un temps de club à une position de référence élite), relevé en revue
  // ui-ux à 4,594:1 / 4,595:1 — au-dessus du seuil mais avec ~2 % de marge.
  // Verrouillé ici pour qu'une retouche future de `--tcn-orange`,
  // `--tcn-success` ou `--tcn-text-faint` ne le fasse pas passer sous AA en
  // silence (patron de `lib/sport-colors.test.ts`).
  const SURFACE = resolve("--tcn-surface"); // fond réel de la carte qui porte le tableau
  const CAS_LIMITES = [
    { nom: "orange (plus lent, écart maximal)", pourcentage: 150 },
    { nom: "vert (plus rapide, écart maximal)", pourcentage: 50 },
  ];

  it.each(CAS_LIMITES)(
    "le sous-texte d'écart (`--tcn-text-faint`) reste ≥ 4,5:1 sur la teinte $nom",
    ({ pourcentage }) => {
      const fond = pctTint(pourcentage);
      expect(fond).toBeDefined();
      const composite = surSurface(evalue(fond as string), SURFACE);
      expect(contrast(resolve("--tcn-text-faint"), composite)).toBeGreaterThanOrEqual(4.5);
    },
  );

  it.each(CAS_LIMITES)(
    "le pourcentage (`--tcn-text-body`) reste ≥ 4,5:1 sur la teinte $nom",
    ({ pourcentage }) => {
      const fond = pctTint(pourcentage);
      const composite = surSurface(evalue(fond as string), SURFACE);
      expect(contrast(resolve("--tcn-text-body"), composite)).toBeGreaterThanOrEqual(4.5);
    },
  );
});
