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
});
