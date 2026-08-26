import { describe, it, expect } from "vitest";
import { gridColumns, gridMinWidth, CHROME_RAIL_REPLIE, type Track } from "./table";

const TRACKS: Track[] = [120, { flexMin: 200 }, 90, 28];

describe("gridColumns", () => {
  it("rend les pistes fixes en px et la piste souple en minmax", () => {
    expect(gridColumns(TRACKS)).toBe("120px minmax(200px, 1fr) 90px 28px");
  });
});

describe("gridMinWidth", () => {
  it("additionne les pistes, les gouttières et le padding latéral", () => {
    // 120 + 200 + 90 + 28 = 438 ; 3 gouttières de 18 = 54 ; padding 2 × 26 = 52.
    expect(gridMinWidth(TRACKS, { gap: 18, paddingX: 26 })).toBe(544);
  });

  it("compte la largeur minimale de la piste souple, jamais zéro", () => {
    const sansSouple: Track[] = [120, 90, 28];
    expect(gridMinWidth(TRACKS, { gap: 0, paddingX: 0 })).toBe(
      gridMinWidth(sansSouple, { gap: 0, paddingX: 0 }) + 200,
    );
  });

  it("ne décompte aucune gouttière en deçà de deux pistes", () => {
    // Une grille d'une piste n'a pas de gouttière ; une grille vide non plus.
    expect(gridMinWidth([120], { gap: 18, paddingX: 26 })).toBe(172);
    expect(gridMinWidth([], { gap: 18, paddingX: 26 })).toBe(52);
  });
});

/**
 * Garde-fou du plancher de bascule grille/cartes des quatre écrans de #461
 * (revue UI/UX). Tailwind ne scanne que du texte littéral : le cran
 * `min-[Npx]:` posé dans chaque JSX ne peut pas référencer `CHROME_RAIL_REPLIE`
 * par le code, donc rien ne l'alerte si un écran gagne une colonne sans que
 * quelqu'un pense à relever son seuil — d'où ce test, qui rejoue l'addition à
 * la main. Le faire rougir est le signal : mettre à jour `MIN_WIDTH` (ou la
 * largeur en dur) ci-dessous **et** le cran `min-[Npx]:` du fichier concerné,
 * ensemble.
 */
describe("plancher de bascule grille/cartes (#461)", () => {
  const ECRANS = [
    { nom: "classement (RaceFinishers)", minWidth: 1080, seuil: 1237 },
    { nom: "fiche athlète (EventsTable)", minWidth: 988, seuil: 1145 },
    { nom: "/resultats (EventList)", minWidth: 948, seuil: 1105 },
    { nom: "/ajouter (recents)", minWidth: 480, seuil: 640 },
  ];

  it.each(ECRANS)("$nom : le seuil couvre MIN_WIDTH + CHROME_RAIL_REPLIE", ({ minWidth, seuil }) => {
    expect(seuil).toBeGreaterThanOrEqual(minWidth + CHROME_RAIL_REPLIE);
  });
});
