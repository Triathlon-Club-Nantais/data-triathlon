import { describe, expect, it } from "vitest";
import { eventTypeColor, tintedStyle } from "./sport-colors";
import {
  SURFACES,
  contrast,
  ecartDeTeinte,
  evalue,
  resolve,
  surSurface,
  versOklch,
} from "@/test/couleur";

/** Un `event_type` représentatif par famille. */
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
  ...Object.entries(REPRESENTATIVE_TYPE).map(([name, type]) => ({
    name,
    color: eventTypeColor(type),
  })),
  { name: "swim", color: "var(--swim)" },
  { name: "bike", color: "var(--bike)" },
  { name: "run", color: "var(--run)" },
  { name: "transition", color: "var(--muted-foreground)" },
];

describe("échelle unique des disciplines", () => {
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
    expect(eventTypeColor(type)).toBe(eventTypeColor(REPRESENTATIVE_TYPE[expected]));
  });

  it("donne à chaque famille une couleur de la palette TCN", () => {
    for (const type of Object.values(REPRESENTATIVE_TYPE)) {
      expect(eventTypeColor(type)).toMatch(/^var\(--tcn-[a-z0-9-]+\)$/);
    }
  });

  it("ne rend plus la même couleur à un trail et à un triathlon (#480)", () => {
    // `--run` et `--tri` valaient tous deux `--tcn-orange` : le grief de VIZ-1.
    expect(eventTypeColor("trail-court")).not.toBe(eventTypeColor("triathlon-m"));
  });
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
