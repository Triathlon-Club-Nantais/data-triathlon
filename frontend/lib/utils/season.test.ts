import { describe, it, expect } from "vitest";
import {
  currentSeason,
  seasonOf,
  seasonLabel,
  parseSeasonsParam,
  serializeSeasons,
  toggleSeason,
  seasonSelectionLabel,
} from "./season";

describe("seasonOf", () => {
  it("31 août appartient à la saison de l'année précédente", () => {
    expect(seasonOf("2026-08-31")).toBe(2025);
  });
  it("1er septembre ouvre une nouvelle saison", () => {
    expect(seasonOf("2026-09-01")).toBe(2026);
  });
  it("janvier appartient à la saison de l'année précédente", () => {
    expect(seasonOf("2026-01-15")).toBe(2025);
  });
});

describe("currentSeason", () => {
  it("calcule depuis une date injectée", () => {
    expect(currentSeason(new Date("2026-06-27T10:00:00Z"))).toBe(2025);
    expect(currentSeason(new Date("2026-09-02T10:00:00Z"))).toBe(2026);
  });
});

describe("seasonLabel", () => {
  it("formate « Saison Y — Y+1 »", () => {
    expect(seasonLabel(2025)).toBe("Saison 2025 — 2026");
  });
});

describe("parseSeasonsParam / serializeSeasons", () => {
  it("parse un CSV, tolère espaces, ignore non entiers, dédoublonne", () => {
    expect(parseSeasonsParam(" 2025 , 2025, abc, 2023 ")).toEqual([2025, 2023]);
  });
  it("renvoie [] pour vide/null", () => {
    expect(parseSeasonsParam(null)).toEqual([]);
    expect(parseSeasonsParam("")).toEqual([]);
  });
  it("sérialise en CSV", () => {
    expect(serializeSeasons([2025, 2023])).toBe("2025,2023");
  });
});

describe("toggleSeason", () => {
  it("ajoute une saison absente", () => {
    expect(toggleSeason([2025], 2023)).toEqual([2025, 2023]);
  });
  it("retire une saison présente", () => {
    expect(toggleSeason([2025, 2023], 2025)).toEqual([2023]);
  });
});

describe("seasonSelectionLabel", () => {
  it("une saison → libellé complet", () => {
    expect(seasonSelectionLabel([2025])).toBe("Saison 2025 — 2026");
  });
  it("plusieurs saisons → décompte", () => {
    expect(seasonSelectionLabel([2025, 2023])).toBe("2 saisons sélectionnées");
  });
});
