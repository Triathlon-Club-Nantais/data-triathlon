// @vitest-environment node
import { describe, expect, it } from "vitest";
import { depuisOklab, ecartDeTeinte, evalue, resolve, surSurface, versOklch } from "./couleur";

// Ces tests calent l'outil : sans eux, une erreur de matrice ou d'analyse
// rendrait verts, pour de mauvaises raisons, les tests de couleur qui s'appuient
// dessus (`app/globals.test.ts`, `lib/sport-colors.test.ts`).

describe("arithmétique OKLab", () => {
  it("place le rouge pur là où la référence Ottosson l'attend", () => {
    const [clarte, chroma, teinte] = versOklch("#ff0000");
    expect(clarte).toBeCloseTo(0.6279, 3);
    expect(chroma).toBeCloseTo(0.2577, 3);
    expect(teinte).toBeCloseTo(29.23, 1);
  });

  it("fait l'aller-retour sans perte sur l'orange de marque", () => {
    const [clarte, chroma, teinte] = versOklch("#e9530e");
    const radians = (teinte * Math.PI) / 180;
    expect(depuisOklab([clarte, chroma * Math.cos(radians), chroma * Math.sin(radians)])).toBe("#e9530e");
  });
});

describe("évaluation de color-mix()", () => {
  it("suit les var() jusqu'au littéral", () => {
    expect(evalue("var(--run)").hex).toBe(resolve("--run").toLowerCase());
  });

  it("rend un aplat mélangé à transparent comme un alpha, sans toucher la couleur", () => {
    // La forme de `tintedStyle` : `color-mix(in oklch, C 14%, transparent)`.
    // L'interpolation étant prémultipliée, `transparent` ne colore pas.
    const aplat = evalue("color-mix(in oklch, #e9530e 14%, transparent)");
    expect(aplat).toEqual({ hex: "#e9530e", alpha: 0.14 });
    expect(surSurface(aplat, "#ffffff")).toBe("#fce7dd");
  });

  it("déduit le complément quand un seul pourcentage est écrit", () => {
    expect(evalue("color-mix(in oklab, #ffffff, #000000 100%)").hex).toBe("#000000");
    expect(evalue("color-mix(in oklab, #ffffff 100%, #000000)").hex).toBe("#ffffff");
  });

  it("reproduit le détour de teinte d'oklch, que oklab n'a pas", () => {
    // Le défaut mesuré sur #469 : vers une encre quasi neutre mais bleutée,
    // l'arc de teinte le plus court fait passer l'orange par le prune.
    const encre = "#1c1e22";
    const parOklch = evalue(`color-mix(in oklch, #e9530e, ${encre} 42%)`).hex;
    const parOklab = evalue(`color-mix(in oklab, #e9530e, ${encre} 42%)`).hex;
    expect(ecartDeTeinte(parOklch, "#e9530e")).toBeGreaterThan(50);
    expect(ecartDeTeinte(parOklab, "#e9530e")).toBeLessThan(10);
  });
});
