import { describe, it, expect, vi, afterEach } from "vitest";
import { calculerAge } from "./age";

function aujourdhuiLe(annee: number, mois: number, jour: number) {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(annee, mois - 1, jour, 12, 0));
}

describe("calculerAge", () => {
  afterEach(() => vi.useRealTimers());

  it("ne compte pas l'année en cours la veille de l'anniversaire", () => {
    aujourdhuiLe(2026, 4, 11);
    expect(calculerAge("2015-04-12")).toBe(10);
  });

  it("compte l'année en cours le jour de l'anniversaire", () => {
    aujourdhuiLe(2026, 4, 12);
    expect(calculerAge("2015-04-12")).toBe(11);
  });

  it("n'avance un 29 février qu'au 1er mars d'une année non bissextile", () => {
    aujourdhuiLe(2026, 2, 28);
    expect(calculerAge("2016-02-29")).toBe(9);

    aujourdhuiLe(2026, 3, 1);
    expect(calculerAge("2016-02-29")).toBe(10);
  });

  it("ignore la partie heure d'un horodatage ISO", () => {
    aujourdhuiLe(2026, 4, 12);
    expect(calculerAge("2015-04-12T00:00:00Z")).toBe(11);
  });

  it("rend null sans date de naissance", () => {
    expect(calculerAge(null)).toBeNull();
    expect(calculerAge(undefined)).toBeNull();
    expect(calculerAge("")).toBeNull();
  });

  it("rend null pour une date mal formée", () => {
    expect(calculerAge("12/04/2015")).toBeNull();
    expect(calculerAge("pas une date")).toBeNull();
  });
});
