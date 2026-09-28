import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Toute variable CSS lue doit être déclarée (#1066). Une `var(--x)` sans
 * déclaration ne lève rien : la propriété devient invalide au calcul, et le
 * rendu perd sa couleur en silence (les médailles du podium sans leur teint).
 */
const racine = fileURLToPath(new URL("..", import.meta.url));

/** Posées à l'exécution, hors de toute feuille : `next/font` et un `style` en ligne. */
const POSEES_A_L_EXECUTION = new Set([
  "--font-anton",
  "--font-barlow",
  "--font-barlow-cond",
  "--segments-count",
]);

function sources(dossier: string): string[] {
  return readdirSync(join(racine, dossier), { recursive: true, encoding: "utf8" })
    .filter((f) => /\.(tsx?|css)$/.test(f) && !/\.test\.tsx?$/.test(f))
    .map((f) => join(racine, dossier, f));
}

function declarees(): Set<string> {
  const feuilles = [
    join(racine, "app/globals.css"),
    join(racine, "node_modules/shadcn/dist/tailwind.css"),
  ];
  return new Set(
    feuilles.flatMap((f) => [...readFileSync(f, "utf8").matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1])),
  );
}

describe("variables CSS", () => {
  it("toute variable lue est déclarée", () => {
    const connues = declarees();
    const orphelines = new Set<string>();
    for (const fichier of ["app", "components", "lib"].flatMap(sources)) {
      for (const [, nom] of readFileSync(fichier, "utf8").matchAll(/var\(\s*(--[\w-]+)/g)) {
        if (!connues.has(nom) && !POSEES_A_L_EXECUTION.has(nom)) orphelines.add(nom);
      }
    }
    expect([...orphelines].sort()).toEqual([]);
  });
});
