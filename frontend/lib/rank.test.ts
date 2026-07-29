import { describe, it, expect } from "vitest";
import { RANK_DEFAULT, RANK_PARAM, rankTypeFromParam, type RankType } from "./rank";

describe("RANK_PARAM", () => {
  it("utilise la clé 'rank' dans l'URL", () => {
    expect(RANK_PARAM).toBe("rank");
  });
});

describe("RANK_DEFAULT", () => {
  it("vaut 'scratch' (cas d'usage AG cité par #104)", () => {
    expect(RANK_DEFAULT).toBe("scratch");
  });
});

describe("rankTypeFromParam", () => {
  it.each<[string, RankType]>([
    ["scratch", "scratch"],
    ["category", "category"],
    ["gender", "gender"],
    ["all", "all"],
  ])("accepte la valeur canonique %s", (input, expected) => {
    expect(rankTypeFromParam(input)).toBe(expected);
  });

  it("retombe sur le défaut quand le paramètre est absent", () => {
    expect(rankTypeFromParam(undefined)).toBe(RANK_DEFAULT);
  });

  it("retombe sur le défaut quand le paramètre est vide", () => {
    expect(rankTypeFromParam("")).toBe(RANK_DEFAULT);
  });

  it.each(["foo", "SCRATCH", "Category", "women", "men", "toto"])(
    "retombe sur le défaut sur la valeur inconnue %s (pas d'alias, pas de casse insensible)",
    (bad) => {
      expect(rankTypeFromParam(bad)).toBe(RANK_DEFAULT);
    },
  );
});
