import { describe, expect, it } from "vitest";
import { estToutRecent, moisDeSaison, titreSortie } from "./home";

describe("titreSortie", () => {
  it("says « Ce week-end » within 7 days", () => {
    expect(titreSortie("2026-10-11", new Date("2026-10-15T12:00:00"))).toBe("Ce week-end");
    expect(titreSortie("2026-10-11", new Date("2026-10-17T23:00:00"))).toBe("Ce week-end");
  });

  it("adds the year when the outing is not in the current season", () => {
    expect(titreSortie("2024-06-10", new Date("2026-10-15T12:00:00"))).toBe("Dernière sortie · 10 juin 2024");
  });

  it("dates an older outing", () => {
    expect(titreSortie("2026-09-06", new Date("2026-10-15T12:00:00"))).toBe("Dernière sortie · 6 sept.");
  });
});

describe("moisDeSaison", () => {
  it("lays the twelve season months out from September, zero when empty", () => {
    const mois = moisDeSaison({ "2026-09": 40, "2026-11": 5, "2025-12": 99 }, 2026);
    expect(mois).toHaveLength(12);
    expect(mois[0]).toEqual({ mois: "2026-09", libelle: "sept.", valeur: 40 });
    expect(mois[1].valeur).toBe(0);
    expect(mois[2].valeur).toBe(5);
    expect(mois[11].mois).toBe("2027-08");
  });
});

describe("estToutRecent", () => {
  it("is true from the day itself up to 2 days after", () => {
    expect(estToutRecent("2026-10-11", new Date("2026-10-13T12:00:00"))).toBe(true);
    expect(estToutRecent("2026-10-11", new Date("2026-10-11T08:00:00"))).toBe(true);
  });

  it("is false after 2 days", () => {
    expect(estToutRecent("2026-10-11", new Date("2026-10-14T12:00:00"))).toBe(false);
  });
});
