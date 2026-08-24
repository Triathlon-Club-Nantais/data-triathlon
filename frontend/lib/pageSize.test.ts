import { describe, it, expect } from "vitest";
import { parsePageSize, pageSizeLabel, PAGE_SIZE_DEFAUT } from "./pageSize";

describe("parsePageSize", () => {
  it("accepte les quatre tailles proposées", () => {
    expect(parsePageSize("20")).toBe(20);
    expect(parsePageSize("50")).toBe(50);
    expect(parsePageSize("200")).toBe(200);
    expect(parsePageSize("all")).toBe("all");
  });

  it("retombe sur le défaut quand le paramètre est absent ou illisible", () => {
    expect(parsePageSize(undefined)).toBe(PAGE_SIZE_DEFAUT);
    expect(parsePageSize(null)).toBe(PAGE_SIZE_DEFAUT);
    expect(parsePageSize("")).toBe(PAGE_SIZE_DEFAUT);
    expect(parsePageSize("beaucoup")).toBe(PAGE_SIZE_DEFAUT);
  });

  it("refuse une taille hors liste, même acceptée par le backend", () => {
    // Le backend accepte 1..200 : sans liste blanche, `page_size=137`
    // afficherait une taille que le sélecteur ne sait pas représenter.
    expect(parsePageSize("137")).toBe(PAGE_SIZE_DEFAUT);
    expect(parsePageSize("500")).toBe(PAGE_SIZE_DEFAUT);
    expect(parsePageSize("0")).toBe(PAGE_SIZE_DEFAUT);
    expect(parsePageSize("-20")).toBe(PAGE_SIZE_DEFAUT);
  });
});

describe("pageSizeLabel", () => {
  it("nomme les tailles chiffrées et l'échappatoire", () => {
    expect(pageSizeLabel(50)).toBe("50 lignes");
    expect(pageSizeLabel("all")).toBe("Tout");
  });
});
