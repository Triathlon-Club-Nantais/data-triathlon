import { describe, it, expect } from "vitest";
import { foldAccents } from "./text";

describe("foldAccents", () => {
  it("gives the same key regardless of case and accents", () => {
    expect(foldAccents("Élodie")).toBe(foldAccents("élodie"));
    expect(foldAccents("Élodie")).toBe("elodie");
  });

  it("strips combining diacritics and lowercases", () => {
    expect(foldAccents("Bénévole")).toBe("benevole");
    expect(foldAccents("CÔTE À PIED ÇA")).toBe("cote a pied ca");
    expect(foldAccents("Noël Müller")).toBe("noel muller");
  });

  it("folds precomposed and decomposed input alike", () => {
    expect(foldAccents("é")).toBe(foldAccents("é"));
  });

  it("keeps whitespace, apostrophes and punctuation untouched", () => {
    expect(foldAccents("  L'Été ")).toBe("  l'ete ");
    expect(foldAccents("d’Arc-en-Ciel")).toBe("d’arc-en-ciel");
  });

  it("leaves ligatures as they are (NFD does not split them)", () => {
    expect(foldAccents("Œuvre Æ")).toBe("œuvre æ");
  });
});
