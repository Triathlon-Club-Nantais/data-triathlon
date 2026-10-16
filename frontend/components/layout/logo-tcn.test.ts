import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Poids du logo préchargé sur chaque page (#1504). Affiché à 26 px de haut au
 * plus (`AppNav.tsx`), il doit rester net sur un écran 3x sans redevenir le PNG
 * 2000 x 638 de 37 Ko qui concurrençait les ressources critiques.
 */
const LOGO = readFileSync(join(__dirname, "../../public/logo-tcn.png"));
const MAX_DISPLAY_HEIGHT = 26;

describe("public/logo-tcn.png", () => {
  it("weighs under 10 KB", () => {
    expect(LOGO.byteLength).toBeLessThan(10 * 1024);
  });

  it("keeps at least three times its displayed height", () => {
    // IHDR : largeur puis hauteur, entiers 32 bits big-endian aux octets 16 et 20.
    expect(LOGO.readUInt32BE(20)).toBeGreaterThanOrEqual(3 * MAX_DISPLAY_HEIGHT);
  });
});
