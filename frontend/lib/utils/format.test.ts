import { describe, it, expect } from "vitest";
import { disciplineOf, motCompte, ordinalFr } from "./format";

describe("ordinalFr", () => {
  it("écrit « 1er » pour la première place", () => {
    expect(ordinalFr(1)).toBe("1er");
  });

  it("écrit « ne » pour les autres places", () => {
    expect(ordinalFr(2)).toBe("2e");
    expect(ordinalFr(42)).toBe("42e");
    expect(ordinalFr(300)).toBe("300e");
  });
});

describe("disciplineOf", () => {
  it("met le format de côté : les tailles d'une discipline se ramènent à elle", () => {
    expect(disciplineOf("triathlon-m")).toBe("triathlon");
    expect(disciplineOf("triathlon-xl")).toBe("triathlon");
    expect(disciplineOf("duathlon-s")).toBe("duathlon");
    expect(disciplineOf("swimrun-l")).toBe("swimrun");
  });

  it("ramène aussi les formats nommés de la course à pied", () => {
    expect(disciplineOf("course-a-pied-semi")).toBe("course-a-pied");
    expect(disciplineOf("course-a-pied-10k")).toBe("course-a-pied");
    expect(disciplineOf("cyclisme-clm")).toBe("cyclisme");
  });

  it("laisse intacte une discipline qui n'a pas de format", () => {
    expect(disciplineOf("trail")).toBe("trail");
    expect(disciplineOf("bike-run")).toBe("bike-run");
    expect(disciplineOf("raid-multisport")).toBe("raid-multisport");
  });

  it("ne confond pas le cross triathlon avec le triathlon", () => {
    expect(disciplineOf("cross-triathlon")).toBe("cross-triathlon");
  });

  it("rend tel quel un type inconnu, et la chaîne vide pour une absence", () => {
    expect(disciplineOf("natation-eau-libre")).toBe("natation-eau-libre");
    expect(disciplineOf(null)).toBe("");
    expect(disciplineOf(undefined)).toBe("");
  });
});

describe("motCompte", () => {
  it("laisse le singulier à 1", () => {
    expect(motCompte(1, "podium")).toBe("1 podium");
  });

  it("accorde au pluriel au-delà", () => {
    expect(motCompte(2, "podium")).toBe("2 podiums");
    expect(motCompte(4, "épreuve")).toBe("4 épreuves");
  });

  // Le zéro français est singulier — « 0 podium », pas « 0 podiums ».
  it("laisse le singulier à 0", () => {
    expect(motCompte(0, "épreuve")).toBe("0 épreuve");
  });
});
