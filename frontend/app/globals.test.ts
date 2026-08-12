// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const css = readFileSync(fileURLToPath(new URL("globals.css", import.meta.url)), "utf8");

/** Valeur littérale d'un token `--tcn-*` déclaré sur `:root`. */
function token(name: string): string {
  const found = new RegExp(`${name}:\\s*([^;]+);`).exec(css);
  if (!found) throw new Error(`token ${name} absent de globals.css`);
  return found[1].trim();
}

function relativeLuminance(hex: string): number {
  const clean = hex.replace("#", "");
  const channels = [0, 2, 4].map((i) => parseInt(clean.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Ratio de contraste WCAG 2.1 entre deux couleurs hexadécimales. */
function contrast(a: string, b: string): number {
  const [hi, lo] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** Les trois surfaces sur lesquelles du texte se pose réellement. */
const SURFACES = ["--tcn-surface", "--tcn-paper", "--tcn-surface-sunk"];

/**
 * Tokens de texte gardés au seuil du texte courant (WCAG 1.4.3, 4,5:1).
 *
 * `--tcn-text-muted` (3,97:1 sur blanc) en est **délibérément absent** : arbitré
 * ouvert dans #299 — l'assombrir touche 28 usages et se décide avec le sort de la
 * rampe neutre. L'ajouter ici sans le corriger rendrait la suite rouge ; le
 * corriger en passant élargirait le périmètre sans arbitrage.
 */
const TOKENS_TEXTE = ["--tcn-text", "--tcn-text-body", "--tcn-text-faint"];

describe("palette de texte TCN", () => {
  it.each(TOKENS_TEXTE)("%s atteint 4,5:1 sur les trois surfaces", (nom) => {
    for (const surface of SURFACES) {
      expect(contrast(token(nom), token(surface))).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("porte l'encre, pas du blanc, sur l'orange de marque et ses deux extrémités de dégradé", () => {
    // Arbitrage produit de #299 : l'orange ne bouge pas, le texte devient encre.
    // Du blanc n'y tenait que 3,68:1 pour 4,5:1 requis.
    const encre = token("--tcn-ink");
    const grad = /--tcn-orange-grad:\s*linear-gradient\([^,]+,\s*(#[0-9a-fA-F]{6}),\s*(#[0-9a-fA-F]{6})\)/.exec(css);
    expect(grad).not.toBeNull();

    for (const fond of [token("--tcn-orange"), grad![1], grad![2]]) {
      expect(contrast(encre, fond)).toBeGreaterThanOrEqual(4.5);
      expect(contrast("#ffffff", fond)).toBeLessThan(4.5);
    }
  });

  it("garde l'anneau de focus au-dessus du seuil non-textuel sur papier", () => {
    // WCAG 1.4.11 — `outline: 2px solid var(--tcn-orange)` de `.tcn-input`.
    expect(contrast(token("--tcn-orange"), token("--tcn-paper"))).toBeGreaterThanOrEqual(3);
  });
});

describe("mouvement réduit", () => {
  it("neutralise animations et transitions sous prefers-reduced-motion", () => {
    // WCAG 2.3.3 — 21 usages `animate-*` et les entrées de tw-animate-css
    // n'étaient coupables par personne avant #299.
    expect(css).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)/);
  });
});
