// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { COULEURS_CARTE } from "@/components/map/carte";

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

/** Nom de la couche `@layer` qui contient un sélecteur, `null` s'il est hors couche. */
function layerOf(selector: string): string | null {
  const position = css.indexOf(`${selector} {`);
  if (position < 0) throw new Error(`sélecteur ${selector} absent de globals.css`);
  const couches = [...css.slice(0, position).matchAll(/@layer\s+([a-z-]+)\s*\{/g)];
  return couches.length > 0 ? couches[couches.length - 1][1] : null;
}

/** Corps d'une règle CSS, désigné par son sélecteur exact. */
function rule(selector: string): string {
  const echappe = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const found = new RegExp(`(?:^|[,{}\\s])${echappe}\\s*\\{([^}]*)\\}`, "m").exec(css);
  if (!found) throw new Error(`règle ${selector} absente de globals.css`);
  return found[1];
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

  /**
   * Les fonds oranges qui portent du texte blanc.
   *
   * Arbitrage produit de #299, pris **au rendu** : le texte reste blanc — l'encre
   * sur orange a été essayée et écartée — et c'est le fond qui descend d'un cran.
   * `--tcn-orange` lui-même est intact ; il n'est donc pas dans cette liste,
   * puisqu'il ne porte plus de texte nulle part.
   */
  const FONDS_A_TEXTE_BLANC = ["--tcn-orange-deep", "--tcn-orange-deeper"];

  it.each(FONDS_A_TEXTE_BLANC)("%s porte du blanc à 4,5:1", (nom) => {
    expect(contrast("#ffffff", token(nom))).toBeGreaterThanOrEqual(4.5);
  });

  it("garde `-deep` au plus près de l'orange de marque, saturation pleine", () => {
    // Le premier fond assombri (#c04008) a été refusé au rendu comme trop terne.
    // Ce test borne la correction des deux côtés : au-dessus du seuil (assuré
    // ci-dessus) mais aussi **le plus vif possible** — un canal vert ou bleu qui
    // remonterait dépenserait de la luminance sans gagner en éclat, la saturation
    // étant ce qu'on voit. Bleu à zéro, vert au maximum que le seuil autorise.
    const deep = token("--tcn-orange-deep").replace("#", "");
    const [rouge, vert, bleu] = [0, 2, 4].map((i) => parseInt(deep.slice(i, i + 2), 16));
    expect(bleu).toBe(0);
    expect(rouge).toBeGreaterThanOrEqual(0xd0);
    expect(contrast("#ffffff", token("--tcn-orange-deep"))).toBeLessThan(4.75);
    expect(vert).toBeGreaterThan(0);
  });

  it("porte du blanc aux deux extrémités du dégradé, libellé de 13px compris", () => {
    // Tuile hero, avatar et carte hero. Le seuil est celui du **petit** texte :
    // le nombre de 86px atteignait déjà 3:1 avant, le libellé de 13px non.
    const grad = /--tcn-orange-grad:\s*linear-gradient\([^,]+,\s*(#[0-9a-fA-F]{6}),\s*(#[0-9a-fA-F]{6})\)/.exec(css);
    expect(grad).not.toBeNull();

    for (const extremite of [grad![1], grad![2]]) {
      expect(contrast("#ffffff", extremite)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("fait suivre le pont shadcn : bg-primary est l'orange profond, son texte du blanc", () => {
    // `bg-primary text-primary-foreground` est le variant par défaut
    // d'`ui/button` et d'`ui/badge`, plus `ScopeToggle`. Sans ça les deux
    // bibliothèques afficheraient deux oranges sous le même blanc, et `ui/`
    // resterait à 3,68:1 sur sept écrans publics.
    expect(token("--primary")).toBe("var(--tcn-orange-deep)");
    expect(token("--primary-foreground")).toBe("#fff");
  });

  it("garde l'anneau de focus au-dessus du seuil non-textuel sur papier", () => {
    // WCAG 1.4.11 — `outline: 2px solid var(--tcn-orange)` de `.tcn-input`.
    expect(contrast(token("--tcn-orange"), token("--tcn-paper"))).toBeGreaterThanOrEqual(3);
  });
});

describe("couleurs de la carte", () => {
  // `pathOptions` de Leaflet alimente un attribut SVG, où `var()` n'est pas
  // fiable : les littéraux y sont légitimes. C'est leur **désynchronisation** avec
  // les tokens qui était le défaut, la légende et la carte en portant chacune sa
  // copie (#299). Ce test est le joint.
  it.each([
    ["avecTcn", "remplissage", "--tcn-orange"],
    ["avecTcn", "trait", "--tcn-orange-deeper"],
    ["sansTcn", "remplissage", "--tcn-text-muted"],
    ["sansTcn", "trait", "--tcn-text-body"],
  ] as const)("%s.%s reste égal à %s", (categorie, role, nom) => {
    expect(COULEURS_CARTE[categorie][role].toLowerCase()).toBe(token(nom).toLowerCase());
  });

  it("garde la pastille neutre au-dessus du seuil non-textuel sur papier", () => {
    // WCAG 1.4.11 — #b0aaa0 (`--tcn-grey-400`) n'y tenait que 2,08:1.
    expect(contrast(COULEURS_CARTE.sansTcn.remplissage, token("--tcn-paper"))).toBeGreaterThanOrEqual(3);
  });
});

describe("bouton TCN", () => {
  // `components/tcn/` stylait tout en `CSSProperties` en ligne, où `:hover`,
  // `:active`, `:focus-visible` et `disabled` sont **inexprimables** : c'était la
  // cause commune des trois défauts que ces règles referment (#299).

  it("vit dans une couche que Tailwind v4 conserve", () => {
    // Le piège qui a rendu le bouton entièrement nu en dev sans que rien ne
    // bronche — ni `npm run build`, ni le lint, ni les tests d'ici, qui lisent la
    // **source** et non le CSS compilé : Tailwind v4 **jette le contenu** d'un
    // `@layer components` écrit à la main, n'en laissant qu'un `@layer components;`
    // vide. Le `@layer utilities` du même fichier, lui, est conservé.
    expect(css).not.toMatch(/@layer\s+components\s*\{/);
    expect(layerOf(".tcn-btn")).toBe("base");
  });

  it("rend le focus clavier visible, à l'identique de .tcn-input", () => {
    // WCAG 2.4.7 — le seul reste était l'anneau UA teinté par `outline-ring/50`,
    // soit l'orange à 50 % d'alpha : 1,86:1 composité sur papier pour 3:1 requis.
    expect(rule(".tcn-btn:focus-visible")).toContain("outline: 2px solid var(--tcn-orange)");
    expect(rule(".tcn-btn:focus-visible")).toContain("outline-offset: 2px");
  });

  it("pose son blanc sur l'orange profond, pas sur l'orange de marque", () => {
    const primaire = rule(".tcn-btn--primary");
    expect(primaire).toContain("color: #fff");
    expect(primaire).toContain("background: var(--tcn-orange-deep)");
  });

  it("donne 44px de cible tactile aux deux tailles qui n'y arrivaient pas", () => {
    // `sm` faisait 31px et `md` — le défaut du composant — 38px, paddings
    // inchangés. `lg` atteignait déjà 45px.
    expect(rule(".tcn-btn--sm")).toContain("min-height: 44px");
    expect(rule(".tcn-btn--md")).toContain("min-height: 44px");
  });

  it("donne un rendu à disabled", () => {
    // L'attribut était transmis et réellement utilisé (TcnScrapeForm), mais rien
    // ne changeait : même fond orange, même ombre, `cursor: pointer` conservé.
    const desactive = rule(".tcn-btn:disabled");
    expect(desactive).toContain("cursor: not-allowed");
    expect(desactive).toContain("box-shadow: none");
  });
});

describe("mouvement réduit", () => {
  it("neutralise animations et transitions sous prefers-reduced-motion", () => {
    // WCAG 2.3.3 — 21 usages `animate-*` et les entrées de tw-animate-css
    // n'étaient coupables par personne avant #299.
    expect(css).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)/);
  });
});
