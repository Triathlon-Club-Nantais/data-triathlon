import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

// Garde-fou de la règle de copie #478 (`frontend/AGENTS.md`) : vouvoiement
// sur tout écran public, et « épreuve » seul mot lu pour l'objet importé.
// Sans lui, la règle a déjà rechuté (#1032).
const RACINE = join(__dirname, "..");
const DOSSIERS = ["app", "components"];

const INTERDITS: { motif: RegExp; raison: string }[] = [
  { motif: /\bClique\b/, raison: "tutoiement" },
  { motif: /\bChange de\b/, raison: "tutoiement" },
  { motif: /\bajoute les\b/, raison: "tutoiement" },
  { motif: /\b(?:la|de la|à la|une) course\b(?! à pied)/, raison: "« épreuve », pas « course »" },
  { motif: /\b(?:des|les) courses\b(?! à pied)/, raison: "« épreuves », pas « courses »" },
];

function sources(dossier: string): string[] {
  return readdirSync(dossier).flatMap((nom) => {
    const chemin = join(dossier, nom);
    if (statSync(chemin).isDirectory()) return sources(chemin);
    return /\.tsx?$/.test(nom) && !/\.test\.tsx?$/.test(nom) ? [chemin] : [];
  });
}

function estCommentaire(ligne: string): boolean {
  return /^\s*(\/\/|\*|\/\*|\{\/\*)/.test(ligne);
}

describe("copy rules (#478)", () => {
  it("keeps user-facing copy in the vouvoiement and names the imported object « épreuve »", () => {
    const ecarts: string[] = [];
    for (const fichier of DOSSIERS.flatMap((d) => sources(join(RACINE, d)))) {
      readFileSync(fichier, "utf8")
        .split("\n")
        .forEach((ligne, index) => {
          if (estCommentaire(ligne)) return;
          for (const { motif, raison } of INTERDITS) {
            if (motif.test(ligne)) ecarts.push(`${relative(RACINE, fichier)}:${index + 1} (${raison})`);
          }
        });
    }
    expect(ecarts).toEqual([]);
  });
});
