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

  it("ne porte `placeholder: true` que sur les captures qui n'en ont pas encore de réelle (#874)", () => {
    // 13/15 des captures admin ont été remplacées par de vraies captures en
    // dev local (session admin réelle) ; les 2 restantes exposent des
    // données personnelles réelles (liste d'utilisateurs, adresses
    // autorisées) qu'on ne persiste pas dans le dépôt sans plus de
    // précaution — elles restent des placeholders volontairement.
    const ENCORE_PLACEHOLDER = ["utilisateurs", "acces-backoffice"];
    for (const section of GUIDE_ADMIN) {
      const attendu = ENCORE_PLACEHOLDER.includes(section.id);
      for (const capture of section.captures) {
        expect(capture.placeholder ?? false, `${section.id} : ${capture.src}`).toBe(attendu);
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
