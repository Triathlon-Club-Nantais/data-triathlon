import { describe, expect, it } from "vitest";
import { tintedStyle } from "./sport-colors";
import {
  SURFACES,
  contrast,
  ecartDeTeinte,
  evalue,
  resolve,
  surSurface,
  versOklch,
} from "@/test/couleur";

/**
 * Les six couleurs que `eventTypeColor` et `splitSegments` font entrer dans
 * `tintedStyle` — badges de discipline et libellés de segment.
 */
const DISCIPLINES = ["--tri", "--bike", "--swim", "--run", "--violet", "--muted-foreground"];

/** Celles qui codent réellement une discipline par leur couleur, pas par leur valeur. */
const CHROMATIQUES = DISCIPLINES.filter((nom) => versOklch(resolve(nom))[1] >= 0.05);

describe("tintedStyle", () => {
  it.each(DISCIPLINES)("%s : son libellé atteint 4,5:1 sur son propre aplat", (nom) => {
    // WCAG 1.4.3. L'aplat est semi-transparent : il se compose sur la surface,
    // et c'est le résultat composité qui porte le texte.
    const { color, background } = tintedStyle(`var(${nom})`);
    const libelle = evalue(String(color)).hex;
    for (const surface of SURFACES) {
      const aplat = surSurface(evalue(String(background)), resolve(surface));
      expect(contrast(libelle, aplat)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it.each(CHROMATIQUES)("%s : son libellé garde la teinte de la discipline", (nom) => {
    // Le piège d'OKLCH, mesuré sur #469 : vers une encre quasi neutre mais
    // bleutée, l'arc de teinte le plus court fait passer l'orange de marque par
    // le prune (#E9530E → #863c6c, 39,6° → 342,9°). Le badge Triathlon
    // n'affichait plus l'orange TCN mais une couleur qui n'est pas de la palette.
    const { color } = tintedStyle(`var(${nom})`);
    expect(ecartDeTeinte(evalue(String(color)).hex, resolve(nom))).toBeLessThanOrEqual(15);
  });

  it.each(CHROMATIQUES)("%s : son libellé reste coloré, pas repeint en encre", (nom) => {
    // Le seuil de contraste seul serait satisfait par une part d'encre de 100 %,
    // qui rendrait tous les libellés identiques : le codage par discipline
    // disparaîtrait au lieu d'être réparé.
    const { color } = tintedStyle(`var(${nom})`);
    const chromaMixe = versOklch(evalue(String(color)).hex)[1];
    expect(chromaMixe).toBeGreaterThanOrEqual(versOklch(resolve(nom))[1] * 0.5);
  });
});
