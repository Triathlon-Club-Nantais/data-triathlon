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
  "validation-epreuves",
  "acces-backoffice",
  "pages-publiques",
];

describe("GUIDE_ADMIN", () => {
  it("expose exactement les 17 ids attendus, dans l'ordre", () => {
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
});

describe("GUIDE_ADMIN wording (#1046)", () => {
  const etapes = (id: string) => GUIDE_ADMIN.find((s) => s.id === id)!.etapes.join(" ");

  it("names the real quality verdict buttons", () => {
    expect(etapes("quality")).toMatch(/« Marquer fiable ».*« Marquer douteuse ».*« Revenir à l'avis calculé »/);
  });

  it("covers the four cards of the access screen", () => {
    const texte = etapes("acces-backoffice");
    expect(texte).toMatch(/adresse/i);
    expect(texte).toMatch(/code d'accès/i);
    expect(texte).toMatch(/bénévoles/i);
    expect(texte).toMatch(/sessions/i);
  });
});

describe("GUIDE_ADMIN public-page gestures (#1046)", () => {
  it("names the admin buttons shown on public pages", () => {
    const texte = GUIDE_ADMIN.find((s) => s.id === "pages-publiques")!.etapes.join(" ");
    expect(texte).toMatch(/« Corriger la fiche »/);
    expect(texte).toMatch(/« Valider la saison »/);
    expect(texte).toMatch(/« Rattacher »/);
  });
});

describe("GUIDE_ADMIN results verification (#1162)", () => {
  const section = () => GUIDE_ADMIN.find((s) => s.id === "validation-epreuves")!;

  it("documents reassigning a result to another athlete", () => {
    const texte = section().etapes.join(" ");
    expect(texte).toMatch(/« Réattribuer à »/);
    expect(texte).toMatch(/« Enregistrer »/);
    expect(texte).toMatch(/« Valider ce résultat »/);
  });

  it("stays visible without `pages:preview`", () => {
    expect(section().destination).toBeUndefined();
  });
});
