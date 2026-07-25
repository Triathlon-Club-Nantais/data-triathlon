import { describe, it, expect } from "vitest";
import { ordinalFr } from "./format";

describe("ordinalFr", () => {
  it("écrit « 1er » pour la première place", () => {
    expect(ordinalFr(1)).toBe("1er");
  });

  it("écrit « ne » pour les autres places", () => {
    expect(ordinalFr(2)).toBe("2e");
    expect(ordinalFr(42)).toBe("42e");
    expect(ordinalFr(300)).toBe("300e");
  });
});
