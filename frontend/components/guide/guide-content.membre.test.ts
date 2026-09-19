import { existsSync } from "node:fs";
import path from "node:path";
import { describe, it, expect } from "vitest";
import { GUIDE_MEMBRE } from "./guide-content.membre";

const IDS_ATTENDUS = ["dashboard", "club", "resultats", "comparaison", "ajouter", "benevolat"];

describe("GUIDE_MEMBRE", () => {
  it("expose exactement les 6 ids attendus, dans l'ordre", () => {
    expect(GUIDE_MEMBRE.map((section) => section.id)).toEqual(IDS_ATTENDUS);
  });

  it.each(IDS_ATTENDUS)("la section « %s » a des étapes, un cas d'usage et une capture", (id) => {
    const section = GUIDE_MEMBRE.find((s) => s.id === id);
    expect(section).toBeDefined();
    expect(section!.etapes.length).toBeGreaterThanOrEqual(1);
    expect(section!.casUsage.trim().length).toBeGreaterThan(0);
    expect(section!.captures.length).toBeGreaterThanOrEqual(1);
  });

  it("chaque `captures[].src` résout vers un fichier présent sous public/", () => {
    for (const section of GUIDE_MEMBRE) {
      for (const capture of section.captures) {
        const fichier = path.join(__dirname, "..", "..", "public", capture.src);
        expect(existsSync(fichier), `${section.id} : ${capture.src}`).toBe(true);
      }
    }
  });
});
