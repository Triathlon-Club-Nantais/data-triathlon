import { describe, it, expect } from "vitest";
import { trouverRang } from "./rang";

describe("trouverRang", () => {
  it("rend le rang 1-indexé d'un id présent dans la liste", () => {
    expect(trouverRang(30, [10, 20, 30, 40])).toBe(3);
  });

  it("rend 1 quand l'id est en tête de liste", () => {
    expect(trouverRang(10, [10, 20, 30])).toBe(1);
  });

  it("rend null quand l'id est absent de la liste", () => {
    expect(trouverRang(99, [10, 20, 30])).toBeNull();
  });
});
