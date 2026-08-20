/**
 * Évaluation des couleurs de `globals.css` côté test.
 *
 * `color-mix()`, `var()` et la composition d'un aplat semi-transparent ne sont
 * calculés ni par JSDOM ni par le lint : sans ce module, un mélange invalide ou
 * illisible ne se voit qu'à l'œil, sur un écran, une fois déployé (#469).
 *
 * Réservé aux tests — rien ici n'est importé par du code d'application.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";

/**
 * Lit `app/globals.css` sans passer par `import.meta.url` — sous jsdom c'est une
 * URL http, que `fileURLToPath` refuse — ni par un import `?raw`, que le plugin
 * CSS de Vite intercepte en rendant une chaîne vide. On remonte donc depuis le
 * répertoire courant jusqu'au dossier qui porte le fichier.
 */
function litGlobalsCss(): string {
  let repertoire = process.cwd();
  for (let remontee = 0; remontee < 5; remontee++) {
    const chemin = join(repertoire, "app", "globals.css");
    if (existsSync(chemin)) return readFileSync(chemin, "utf8");
    repertoire = dirname(repertoire);
  }
  throw new Error(`app/globals.css introuvable depuis ${process.cwd()}`);
}

const css = litGlobalsCss();

/** Valeur littérale d'un token déclaré sur `:root`. */
export function token(name: string): string {
  const found = new RegExp(`${name}:\\s*([^;]+);`).exec(css);
  if (!found) throw new Error(`token ${name} absent de globals.css`);
  return found[1].trim();
}

/** Valeur littérale d'un token, en suivant les chaînes de `var(--…)`. */
export function resolve(name: string): string {
  let valeur = token(name);
  for (let saut = 0; saut < 8; saut++) {
    const indirection = /^var\((--[a-z0-9-]+)\)$/.exec(valeur);
    if (!indirection) return valeur;
    valeur = token(indirection[1]);
  }
  throw new Error(`chaîne de var() trop profonde depuis ${name}`);
}

/* ── WCAG ─────────────────────────────────────────────────────────────── */

function relativeLuminance(hex: string): number {
  const clean = hex.replace("#", "");
  const channels = [0, 2, 4].map((i) => parseInt(clean.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Ratio de contraste WCAG 2.1 entre deux couleurs hexadécimales. */
export function contrast(a: string, b: string): number {
  const [hi, lo] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/* ── OKLab / OKLCH ────────────────────────────────────────────────────────
   Matrices d'Ottosson, calées sur des valeurs connues par `couleur.test.ts`. */

function versLineaire(canal: number): number {
  return canal <= 0.04045 ? canal / 12.92 : ((canal + 0.055) / 1.055) ** 2.4;
}

function versSrgb(canal: number): number {
  const gamma = canal <= 0.0031308 ? canal * 12.92 : 1.055 * canal ** (1 / 2.4) - 0.055;
  return Math.min(1, Math.max(0, gamma));
}

/** Hex sRGB → OKLab `[L, a, b]`. */
export function versOklab(hex: string): [number, number, number] {
  const clean = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => versLineaire(parseInt(clean.slice(i, i + 2), 16) / 255));
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

/** OKLab `[L, a, b]` → hex sRGB, canaux écrêtés dans le gamut. */
export function depuisOklab([clarte, axeA, axeB]: [number, number, number]): string {
  const l = (clarte + 0.3963377774 * axeA + 0.2158037573 * axeB) ** 3;
  const m = (clarte - 0.1055613458 * axeA - 0.0638541728 * axeB) ** 3;
  const s = (clarte - 0.0894841775 * axeA - 1.291485548 * axeB) ** 3;
  const canaux = [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
  return `#${canaux.map((c) => Math.round(versSrgb(c) * 255).toString(16).padStart(2, "0")).join("")}`;
}

/** Hex sRGB → OKLCH `[L, C, h°]`. */
export function versOklch(hex: string): [number, number, number] {
  const [clarte, axeA, axeB] = versOklab(hex);
  const teinte = (Math.atan2(axeB, axeA) * 180) / Math.PI;
  return [clarte, Math.hypot(axeA, axeB), teinte < 0 ? teinte + 360 : teinte];
}

/** Écart de teinte en degrés entre deux couleurs, par l'arc le plus court. */
export function ecartDeTeinte(a: string, b: string): number {
  const ecart = Math.abs(versOklch(a)[2] - versOklch(b)[2]);
  return ecart > 180 ? 360 - ecart : ecart;
}

/* ── color-mix() ──────────────────────────────────────────────────────── */

/** Couleur évaluée : hex opaque, plus l'alpha que `transparent` a pu introduire. */
export type Couleur = { hex: string; alpha: number };

function melange(base: Couleur, cible: Couleur, poids: number, espace: string): Couleur {
  const alpha = base.alpha + (cible.alpha - base.alpha) * poids;
  if (espace === "oklab") {
    const [a, b] = [versOklab(base.hex), versOklab(cible.hex)];
    // `transparent` ne contribue à aucun canal (interpolation prémultipliée) :
    // le mélange vaut alors la couleur de base, seul son alpha descend.
    if (cible.alpha === 0) return { hex: base.hex, alpha };
    if (base.alpha === 0) return { hex: cible.hex, alpha };
    return { hex: depuisOklab(a.map((v, i) => v + (b[i] - v) * poids) as [number, number, number]), alpha };
  }
  if (espace === "oklch") {
    if (cible.alpha === 0) return { hex: base.hex, alpha };
    if (base.alpha === 0) return { hex: cible.hex, alpha };
    const [clarteA, chromaA, teinteA] = versOklch(base.hex);
    const [clarteB, chromaB, teinteB] = versOklch(cible.hex);
    let arc = teinteB - teinteA;
    if (arc > 180) arc -= 360;
    if (arc < -180) arc += 360;
    const radians = ((teinteA + arc * poids) * Math.PI) / 180;
    const chroma = chromaA + (chromaB - chromaA) * poids;
    return {
      hex: depuisOklab([
        clarteA + (clarteB - clarteA) * poids,
        chroma * Math.cos(radians),
        chroma * Math.sin(radians),
      ]),
      alpha,
    };
  }
  throw new Error(`espace d'interpolation non géré par les tests : ${espace}`);
}

/** Découpe les arguments d'un `color-mix()` au premier niveau de parenthèses. */
function argumentsDe(contenu: string): string[] {
  const parts: string[] = [];
  let profondeur = 0;
  let courant = "";
  for (const caractere of contenu) {
    if (caractere === "(") profondeur++;
    if (caractere === ")") profondeur--;
    if (caractere === "," && profondeur === 0) {
      parts.push(courant.trim());
      courant = "";
      continue;
    }
    courant += caractere;
  }
  parts.push(courant.trim());
  return parts;
}

/**
 * Évalue une expression de couleur CSS telle que le code la produit :
 * hex, `transparent`, `var(--token)` et `color-mix(in <espace>, A, B p%)`.
 */
export function evalue(expression: string): Couleur {
  const expr = expression.trim();

  if (expr === "transparent") return { hex: "#000000", alpha: 0 };
  if (/^#[0-9a-fA-F]{6}$/.test(expr)) return { hex: expr.toLowerCase(), alpha: 1 };
  if (/^#[0-9a-fA-F]{3}$/.test(expr)) {
    const [r, g, b] = expr.slice(1);
    return { hex: `#${r}${r}${g}${g}${b}${b}`.toLowerCase(), alpha: 1 };
  }

  const indirection = /^var\((--[a-z0-9-]+)\)$/.exec(expr);
  if (indirection) return evalue(resolve(indirection[1]));

  const mix = /^color-mix\((.*)\)$/s.exec(expr);
  if (mix) {
    const [espace, base, cible] = argumentsDe(mix[1]);
    const nomEspace = /^in\s+([a-z]+)$/.exec(espace.trim());
    if (!nomEspace) throw new Error(`color-mix sans espace d'interpolation : ${expr}`);
    const [couleurBase, poidsBase] = partsDe(base);
    const [couleurCible, poidsCible] = partsDe(cible);
    // Un seul pourcentage suffit à CSS ; l'autre côté prend le complément.
    const poids = poidsCible ?? (poidsBase === undefined ? 50 : 100 - poidsBase);
    return melange(evalue(couleurBase), evalue(couleurCible), poids / 100, nomEspace[1]);
  }

  throw new Error(`expression de couleur non gérée par les tests : ${expr}`);
}

/** Un pourcentage littéral, ou le token qui en porte un (`var(--ink-mix)`). */
function pourcentageDe(brut: string): number {
  const litteral = /^(\d+(?:\.\d+)?)%$/.exec(brut);
  if (litteral) return Number(litteral[1]);
  const indirection = /^var\((--[a-z0-9-]+)\)$/.exec(brut);
  if (indirection) return pourcentageDe(resolve(indirection[1]));
  throw new Error(`pourcentage de color-mix illisible : ${brut}`);
}

/** Sépare `<couleur> [<pourcentage>]`, le pourcentage étant lu où CSS l'accepte. */
function partsDe(argument: string): [string, number | undefined] {
  const avec = /^(.*?)\s+((?:\d+(?:\.\d+)?%)|(?:var\(--[a-z0-9-]+\)))$/s.exec(argument.trim());
  if (avec) return [avec[1], pourcentageDe(avec[2])];
  const avant = /^(\d+(?:\.\d+)?%)\s+(.*)$/s.exec(argument.trim());
  if (avant) return [avant[2], pourcentageDe(avant[1])];
  return [argument.trim(), undefined];
}

/** Aplatit une couleur évaluée sur une surface opaque (mélange sRGB, comme le rendu). */
export function surSurface(couche: Couleur, surface: string): string {
  if (couche.alpha >= 1) return couche.hex;
  const [avant, arriere] = [couche.hex.replace("#", ""), surface.replace("#", "")];
  const canaux = [0, 2, 4].map((i) => {
    const dessus = parseInt(avant.slice(i, i + 2), 16);
    const dessous = parseInt(arriere.slice(i, i + 2), 16);
    return Math.round(dessus * couche.alpha + dessous * (1 - couche.alpha));
  });
  return `#${canaux.map((c) => c.toString(16).padStart(2, "0")).join("")}`;
}

/** Les trois surfaces sur lesquelles du texte se pose réellement. */
export const SURFACES = ["--tcn-surface", "--tcn-paper", "--tcn-surface-sunk"];
