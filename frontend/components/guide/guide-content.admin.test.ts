import { existsSync } from "node:fs";
import path from "node:path";
import { describe, it, expect } from "vitest";
import { GUIDE_ADMIN } from "./guide-content.admin";

const IDS_ATTENDUS = [
  "epreuves",
  "fournisseurs",
  "doublons",
  "droits",
  "quality",
  "batches",
  "groupes",
  "utilisateurs",
  "journal",
  "maintenance",
  "retours-utilisateurs",
  "variantes-club",
  "portee-compteurs",
  "benevolat-validation",
  "acces-backoffice",
];

describe("GUIDE_ADMIN", () => {
  it("expose exactement les 15 ids attendus, dans l'ordre", () => {
    expect(GUIDE_ADMIN.map((section) => section.id)).toEqual(IDS_ATTENDUS);
  });

  it.each(IDS_ATTENDUS)("la section « %s » a des étapes, un cas d'usage et une capture", (id) => {
    const section = GUIDE_ADMIN.find((s) => s.id === id);
    expect(section).toBeDefined();
    expect(section!.etapes.length).toBeGreaterThanOrEqual(1);
    expect(section!.casUsage.trim().length).toBeGreaterThan(0);
    expect(section!.captures.length).toBeGreaterThanOrEqual(1);
  });

  it("chaque `captures[].src` résout vers un fichier présent sous public/", () => {
    for (const section of GUIDE_ADMIN) {
      for (const capture of section.captures) {
        const fichier = path.join(__dirname, "..", "..", "public", capture.src);
        expect(existsSync(fichier), `${section.id} : ${capture.src}`).toBe(true);
      }
    }
  });

  it("chaque capture est marquée `placeholder: true` (aucune vraie capture admin pour l'instant, #874)", () => {
    for (const section of GUIDE_ADMIN) {
      for (const capture of section.captures) {
        expect(capture.placeholder, `${section.id} : ${capture.src}`).toBe(true);
      }
    }
  });
});
