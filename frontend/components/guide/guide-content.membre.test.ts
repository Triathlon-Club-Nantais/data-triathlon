import { existsSync } from "node:fs";
import path from "node:path";
import { describe, it, expect } from "vitest";
import { GUIDE_MEMBRE } from "./guide-content.membre";

const IDS_ATTENDUS = ["dashboard", "club", "resultats", "fiche-athlete", "comparaison", "ajouter", "benevolat"];
const IDS_GESTES = [
  { id: "rattachement", libelle: "« C'est moi »" },
  { id: "objectifs", libelle: "« Ajouter un objectif »" },
  { id: "recap-saison", libelle: "« Récap de la saison passée »" },
  { id: "carte-resultat", libelle: "« Ma carte résultat »" },
  { id: "reclamer-resultat", libelle: "« Ce résultat est à moi »" },
  { id: "supprimer-compte", libelle: "« Supprimer mon compte »" },
];
const IDS_COMPLETS = [...IDS_ATTENDUS, ...IDS_GESTES.map((geste) => geste.id)];

describe("GUIDE_MEMBRE", () => {
  it("expose exactement les 13 ids attendus, dans l'ordre", () => {
    expect(GUIDE_MEMBRE.map((section) => section.id)).toEqual(IDS_COMPLETS);
  });

  it.each(IDS_ATTENDUS)("la section « %s » a des étapes, un cas d'usage et une capture", (id) => {
    const section = GUIDE_MEMBRE.find((s) => s.id === id);
    expect(section).toBeDefined();
    expect(section!.etapes.length).toBeGreaterThanOrEqual(1);
    expect(section!.casUsage.trim().length).toBeGreaterThan(0);
    expect(section!.captures.length).toBeGreaterThanOrEqual(1);
  });

  it.each(IDS_GESTES)("la section « $id » a des étapes, un cas d'usage et cite $libelle", ({ id, libelle }) => {
    const section = GUIDE_MEMBRE.find((s) => s.id === id);
    expect(section).toBeDefined();
    expect(section!.etapes.length).toBeGreaterThanOrEqual(1);
    expect(section!.casUsage.trim().length).toBeGreaterThan(0);
    expect(section!.etapes.join(" ")).toContain(libelle);
  });

  it("aucun texte ne parle de « course » ni de « coureur »", () => {
    for (const geste of IDS_GESTES) {
      const section = GUIDE_MEMBRE.find((s) => s.id === geste.id);
      const texte = [section?.titre, section?.casUsage, ...(section?.etapes ?? [])].join(" ");
      expect(texte).not.toMatch(/\bcourses?\b|coureur/i);
    }
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

describe("GUIDE_MEMBRE home capture (#1626)", () => {
  it("shows the club home, not the old dashboard", () => {
    const [capture] = GUIDE_MEMBRE.find((s) => s.id === "dashboard")!.captures;
    expect(capture.src).toBe("/guide/membre/accueil.jpg");
    expect(capture.alt).toMatch(/dernière sortie/);
  });
});

describe("GUIDE_MEMBRE athlete page (#1041)", () => {
  it("covers the athlete search shortcut and the athlete choice", () => {
    const texte = GUIDE_MEMBRE.find((s) => s.id === "fiche-athlete")!.etapes.join(" ");
    expect(texte).toMatch(/Ctrl K/);
    expect(texte).toMatch(/« Choisir cet athlète »/);
    expect(texte).toMatch(/Mon espace/);
  });
});
