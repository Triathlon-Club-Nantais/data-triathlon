import { existsSync } from "node:fs";
import path from "node:path";
import { describe, it, expect } from "vitest";
import { GUIDE_ADMIN } from "./guide-content.admin";

const IDS_ATTENDUS = [
  "epreuves",
  "fournisseurs",
  "doublons",
  "identites",
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
  "membres",
  "oppositions",
  "benevolat-validation",
  "validation-epreuves",
  "acces-backoffice",
  "jeunes",
  "pages-publiques",
];

// Sections ajoutées par #1245, dont les captures restent à prendre sur le jeu de démo.
const SANS_CAPTURE = new Set(["identites", "membres", "oppositions", "jeunes"]);

describe("GUIDE_ADMIN", () => {
  it("expose exactement les 21 ids attendus, dans l'ordre", () => {
    expect(GUIDE_ADMIN.map((section) => section.id)).toEqual(IDS_ATTENDUS);
  });

  it.each(IDS_ATTENDUS)("la section « %s » a des étapes, un cas d'usage et une capture", (id) => {
    const section = GUIDE_ADMIN.find((s) => s.id === id);
    expect(section).toBeDefined();
    expect(section!.etapes.length).toBeGreaterThanOrEqual(1);
    expect(section!.casUsage.trim().length).toBeGreaterThan(0);
    if (!SANS_CAPTURE.has(id)) expect(section!.captures.length).toBeGreaterThanOrEqual(1);
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

  it("names the athlete merge and split, and the course gestures (#1245)", () => {
    const texte = GUIDE_ADMIN.find((s) => s.id === "pages-publiques")!.etapes.join(" ");
    expect(texte).toMatch(/« Fusionner avec une autre fiche »/);
    expect(texte).toMatch(/« Séparer des résultats »/);
    expect(texte).toMatch(/« Retirer »/);
    expect(texte).toMatch(/« Corriger l'épreuve »/);
    expect(texte).toMatch(/« Avis de fiabilité »/);
    expect(texte).toMatch(/« Fusionner avec une autre épreuve »/);
    expect(texte).toMatch(/« Supprimer »/);
  });
});

describe("GUIDE_ADMIN new screens (#1245)", () => {
  const etapes = (id: string) => GUIDE_ADMIN.find((s) => s.id === id)!.etapes.join(" ");

  it("covers every gesture of the identity review, undo included", () => {
    const texte = etapes("identites");
    for (const geste of ["Séparer", "Rattacher", "Supprimer", "Confirmer ce club", "Fusionner", "Écarter", "Annuler"]) {
      expect(texte).toContain(`« ${geste} »`);
    }
  });

  it("covers members linking, its undo, and both list sources", () => {
    const texte = etapes("membres");
    for (const geste of ["Relire la liste FFTri", "Rattacher à une fiche", "Annuler", "Importer"]) {
      expect(texte).toContain(`« ${geste} »`);
    }
  });

  it("mentions the undo of ignored course pairs", () => {
    expect(etapes("doublons")).toContain("« Annuler »");
  });

  it("says an opposition is final", () => {
    expect(GUIDE_ADMIN.find((s) => s.id === "oppositions")!.casUsage).toMatch(/définitif/);
  });

  it("covers the three youth screens", () => {
    const texte = etapes("jeunes");
    for (const geste of ["Créer le profil", "Créer la séance", "Présent", "Appel de fin"]) {
      expect(texte).toContain(`« ${geste} »`);
    }
  });
});

describe("GUIDE_ADMIN results verification (#1162)", () => {
  it("documents reassigning a result to another athlete", () => {
    const texte = GUIDE_ADMIN.find((s) => s.id === "validation-epreuves")!.etapes.join(" ");
    expect(texte).toMatch(/« Réattribuer à »/);
    expect(texte).toMatch(/« Enregistrer »/);
    expect(texte).toMatch(/« Valider ce résultat »/);
  });
});
