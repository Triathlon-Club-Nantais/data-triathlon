import { describe, expect, it } from "vitest";
import {
  FAMILY_ORDER,
  disciplineFamily,
  eventTypeColor,
  tintedStyle,
} from "./sport-colors";
import {
  SURFACES,
  contrast,
  ecartDeTeinte,
  evalue,
  resolve,
  surSurface,
  versOklch,
} from "@/test/couleur";

/** Seuil d'adjacence de deux familles voisines dans la barre empilée. */
const ADJACENCY_THRESHOLD = 1.6;

/**
 * Un `event_type` représentatif par famille, **dans l'ordre de FAMILY_ORDER**.
 * On ne peut pas retrouver une famille depuis son nom : `disciplineFamily` prend
 * un type d'épreuve, pas un libellé.
 */
const REPRESENTATIVE_TYPE: Record<string, string> = {
  Triathlon: "triathlon-m",
  "Swim & Run": "swimrun-l",
  Duathlon: "duathlon-s",
  Aquathlon: "aquathlon",
  "Run & Bike": "bike-run",
  Autres: "trail-court",
};

/** Les couleurs qui entrent dans `tintedStyle` : les six familles, plus les
 *  trois alias de splits et le neutre des transitions. */
const TINTS = [
  ...FAMILY_ORDER.map((name) => ({
    name: name,
    color: disciplineFamily(REPRESENTATIVE_TYPE[name]).color,
  })),
  { name: "swim", color: "var(--swim)" },
  { name: "bike", color: "var(--bike)" },
  { name: "run", color: "var(--run)" },
  { name: "transition", color: "var(--muted-foreground)" },
];

describe("échelle unique des disciplines", () => {
  it("nomme les six familles dans l'ordre d'empilement", () => {
    expect([...FAMILY_ORDER]).toEqual([
      "Triathlon",
      "Swim & Run",
      "Duathlon",
      "Aquathlon",
      "Run & Bike",
      "Autres",
    ]);
  });

  it.each([
    ["triathlon-m", "Triathlon"],
    ["swimrun-l", "Swim & Run"],
    ["duathlon-s", "Duathlon"],
    ["aquathlon", "Aquathlon"],
    ["aquarun", "Aquathlon"],
    ["bike-run", "Run & Bike"],
    ["trail-court", "Autres"],
    ["cyclisme-clm", "Autres"],
    ["", "Autres"],
    [null, "Autres"],
  ])("range %s dans « %s »", (type, expected) => {
    expect(disciplineFamily(type).name).toBe(expected);
  });

  it("donne à chaque famille une couleur de la palette TCN", () => {
    for (const name of FAMILY_ORDER) {
      expect(disciplineFamily(REPRESENTATIVE_TYPE[name]).color).toMatch(
        /^var\(--tcn-[a-z0-9-]+\)$/,
      );
    }
  });

  it("sépare d'au moins 1,6:1 deux familles voisines dans l'ordre complet", () => {
    // C'est la seule garde de l'arbitrage de la spec : la palette ne permet pas
    // de séparer les 15 paires, seulement les 5 qui se **touchent** dans la
    // barre empilée. Réordonner FAMILY_ORDER ou retoucher un token casse cette
    // séparation sans qu'aucun autre test ne bronche.
    //
    // Ce que ce test ne dit pas, et qu'aucun ne peut dire :
    // `aggregateDisciplines` n'émet que les familles présentes dans les
    // données, donc l'adjacence **rendue** dépend du club et de la saison. Sans
    // « Swim & Run », Triathlon et Duathlon se touchent à 1,45:1 ; sans
    // « Run & Bike », Aquathlon et Autres à 1,11:1. Ces paires-là ne sont pas
    // rattrapables dans la palette (cf. l'en-tête de `sport-colors.ts`) : ce
    // qui tient WCAG 1.4.1 pour tout sous-ensemble est le filet, le nom du
    // segment et la légende, gardés par `DisciplineBar.test.tsx`.
    const colors = FAMILY_ORDER.map(
      (name) => evalue(disciplineFamily(REPRESENTATIVE_TYPE[name]).color).hex,
    );
    for (let i = 0; i < colors.length - 1; i++) {
      expect(contrast(colors[i], colors[i + 1])).toBeGreaterThanOrEqual(ADJACENCY_THRESHOLD);
    }
  });

  it("ne rend plus la même couleur à un trail et à un triathlon (#480)", () => {
    // `--run` et `--tri` valaient tous deux `--tcn-orange` : le grief de VIZ-1.
    expect(eventTypeColor("trail-court")).not.toBe(eventTypeColor("triathlon-m"));
  });

  it.each(FAMILY_ORDER)(
    "« %s » porte son libellé de segment à 4,5:1 sur son propre aplat (#480)",
    (name) => {
      // WCAG 1.4.3, sur l'aplat plein (pas un fond teinté) : pas de composition
      // sur surface à faire, `evalue(...).hex` des deux côtés suffit.
      const { ink, color } = disciplineFamily(REPRESENTATIVE_TYPE[name]);
      expect(contrast(evalue(ink).hex, evalue(color).hex)).toBeGreaterThanOrEqual(4.5);
    },
  );
});

describe("tintedStyle", () => {
  it.each(TINTS)("$name : son libellé atteint 4,5:1 sur son propre aplat", ({ color }) => {
    // WCAG 1.4.3. L'aplat est semi-transparent : il se compose sur la surface,
    // et c'est le résultat composité qui porte le texte. C'est CETTE contrainte
    // qui exclut les trois tons pâles de la palette du jeu des familles.
    const { color: labelExpr, background } = tintedStyle(color);
    const label = evalue(String(labelExpr)).hex;
    for (const surface of SURFACES) {
      const fill = surSurface(evalue(String(background)), resolve(surface));
      expect(contrast(label, fill)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it.each(TINTS.filter(({ color }) => versOklch(evalue(color).hex)[1] >= 0.05))(
    "$name : son libellé garde la teinte de la discipline",
    ({ color }) => {
      // Le piège d'OKLCH, mesuré sur #469 : vers une encre quasi neutre mais
      // bleutée, l'arc de teinte le plus court fait passer l'orange de marque
      // par le prune (#E9530E → #863c6c).
      const { color: labelExpr } = tintedStyle(color);
      expect(
        ecartDeTeinte(evalue(String(labelExpr)).hex, evalue(color).hex),
      ).toBeLessThanOrEqual(15);
    },
  );

  it.each(TINTS.filter(({ color }) => versOklch(evalue(color).hex)[1] >= 0.05))(
    "$name : son libellé reste coloré, pas repeint en encre",
    ({ color }) => {
      // Le seuil de contraste seul serait satisfait par une part d'encre de
      // 100 %, qui rendrait tous les libellés identiques.
      const { color: labelExpr } = tintedStyle(color);
      expect(versOklch(evalue(String(labelExpr)).hex)[1]).toBeGreaterThanOrEqual(
        versOklch(evalue(color).hex)[1] * 0.5,
      );
    },
  );
});
