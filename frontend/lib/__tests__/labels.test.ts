import { describe, expect, it } from "vitest";
import { rankTypeLabel, podiumScopeLabel } from "@/lib/labels";

describe("rankTypeLabel — forme courte (défaut)", () => {
  it("libelle les 4 modes canoniques", () => {
    expect(rankTypeLabel("scratch")).toBe("Général");
    expect(rankTypeLabel("category")).toBe("Catégorie");
    expect(rankTypeLabel("gender")).toBe("Genre");
    expect(rankTypeLabel("all")).toBe("Tous");
  });
});

describe("rankTypeLabel — forme longue (delta des StatCard)", () => {
  it("rend la version minuscule utilisée sous les compteurs", () => {
    expect(rankTypeLabel("scratch", { form: "long" })).toBe("général");
    expect(rankTypeLabel("category", { form: "long" })).toBe("catégorie");
    expect(rankTypeLabel("gender", { form: "long" })).toBe("genre");
    expect(rankTypeLabel("all", { form: "long" })).toBe("général, genre ou catégorie");
  });
});

describe("podiumScopeLabel", () => {
  it("libelle les 3 scopes de podium", () => {
    expect(podiumScopeLabel("overall")).toBe("Général");
    expect(podiumScopeLabel("gender")).toBe("Genre");
    expect(podiumScopeLabel("category")).toBe("Catégorie");
  });

  it("scratch (mode toggle) et overall (scope) rendent le MÊME libellé (AC5)", () => {
    expect(rankTypeLabel("scratch")).toBe(podiumScopeLabel("overall"));
  });
});
