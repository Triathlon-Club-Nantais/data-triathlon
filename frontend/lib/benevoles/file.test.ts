import { describe, expect, it } from "vitest";
import type { Participation } from "@/lib/types";
import { suivantApresRetrait } from "./file";

/** Seul l'`id` compte ici : la fonction ne lit rien d'autre. */
const liste = (...ids: number[]) => ids.map((id) => ({ id }) as Participation);

describe("suivantApresRetrait", () => {
  it("prend l'entrée qui glisse dans la place libérée", () => {
    expect(suivantApresRetrait(liste(1, 2, 3), 2)).toBe(3);
  });

  it("prend la précédente quand la dernière est retirée", () => {
    expect(suivantApresRetrait(liste(1, 2, 3), 3)).toBe(2);
  });

  it("rend null quand la file se vide", () => {
    expect(suivantApresRetrait(liste(1), 1)).toBeNull();
  });

  it("rend null quand l'entrée retirée n'était pas dans cette liste", () => {
    expect(suivantApresRetrait(liste(1, 2), 9)).toBeNull();
  });

  it("garde la première quand c'est la première qui part", () => {
    expect(suivantApresRetrait(liste(1, 2, 3), 1)).toBe(2);
  });
});
