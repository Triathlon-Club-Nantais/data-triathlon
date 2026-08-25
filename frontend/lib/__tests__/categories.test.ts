import { describe, it, expect } from "vitest";
import { categoryLabel, categoryTitle } from "@/lib/categories";

describe("categoryLabel", () => {
  it("rend le libellé d'un code de base", () => {
    expect(categoryLabel("S2")).toBe("Senior 2");
    expect(categoryLabel("V3")).toBe("Vétéran 3");
    expect(categoryLabel("CA")).toBe("Cadet");
    expect(categoryLabel("JU")).toBe("Junior");
  });

  it("dérive le genre accolé au code — trois lettres pour deux genres", () => {
    // Les chronométreurs n'ont pas de convention commune : M et H valent tous
    // deux « hommes ». Mesuré sur la base de dev : S2M, S2H et V3H coexistent.
    expect(categoryLabel("S2M")).toBe("Senior 2, hommes");
    expect(categoryLabel("S2H")).toBe("Senior 2, hommes");
    expect(categoryLabel("S2F")).toBe("Senior 2, femmes");
    expect(categoryLabel("V3H")).toBe("Vétéran 3, hommes");
  });

  it("dérive le genre en mot préfixe", () => {
    expect(categoryLabel("M SENIOR")).toBe("Senior, hommes");
    expect(categoryLabel("F VETERAN")).toBe("Vétéran, femmes");
    expect(categoryLabel("M JUNIOR")).toBe("Junior, hommes");
  });

  it("connaît les séries masters étrangères à la nomenclature fédérale", () => {
    expect(categoryLabel("M0")).toBe("Master 0");
    expect(categoryLabel("MA2")).toBe("Master 2");
  });

  it("connaît les codes d'équipe et de relais", () => {
    expect(categoryLabel("REX")).toBe("Relais mixte");
    expect(categoryLabel("EQM")).toBe("Équipe masculine");
  });

  it("ignore la casse et les accents de saisie", () => {
    expect(categoryLabel("CaM")).toBe("Cadet, hommes");
    expect(categoryLabel("  v2  ")).toBe("Vétéran 2");
    expect(categoryLabel("F VÉTÉRAN")).toBe("Vétéran, femmes");
  });

  it("rend null sur un code inconnu, plutôt qu'un libellé inventé", () => {
    // Queue mesurée : 37 codes pour 150 lignes, sans correspondance sûre.
    expect(categoryLabel("ZZZ9")).toBeNull();
    expect(categoryLabel("XX")).toBeNull();
  });

  it("rend null sur l'absence de catégorie", () => {
    expect(categoryLabel(null)).toBeNull();
    expect(categoryLabel(undefined)).toBeNull();
    expect(categoryLabel("")).toBeNull();
    // 65 lignes de la base de dev portent littéralement « - ».
    expect(categoryLabel("-")).toBeNull();
  });
});

describe("categoryTitle", () => {
  it("accole le libellé au code quand il est connu", () => {
    expect(categoryTitle("PoM")).toBe("PoM — Poussin, hommes");
  });

  it("rend le code seul quand la table ne le connaît pas", () => {
    expect(categoryTitle("ZZZ9")).toBe("ZZZ9");
  });
});
