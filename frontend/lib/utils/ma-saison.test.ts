import { describe, it, expect } from "vitest";
import type { Participation } from "@/lib/types";
import { compteMaSaison } from "./ma-saison";

/** Participation minimale : seuls les champs que le comptage lit sont posés. */
function participation(over: {
  courseId: number;
  rank_overall?: number | null;
  rank_category?: number | null;
  rank_gender?: number | null;
  is_pending_validation?: boolean;
}): Participation {
  return {
    course: { id: over.courseId },
    rank_overall: over.rank_overall ?? null,
    rank_category: over.rank_category ?? null,
    rank_gender: over.rank_gender ?? null,
    is_pending_validation: over.is_pending_validation ?? false,
  } as unknown as Participation;
}

describe("compteMaSaison", () => {
  // Un 0 est une donnée aberrante du chronométreur, pas une victoire —
  // `isPodium`/`bestRank` (club-aggregate.ts) l'exigent `>= 1`.
  it("n'est pas un podium au rang 0", () => {
    const lignes = [participation({ courseId: 1, rank_overall: 0 })];
    expect(compteMaSaison(lignes, "scratch").podiums).toBe(0);
  });

  it("compte les courses distinctes, pas les dossards", () => {
    // Solo + relais sur la même course : une seule épreuve courue.
    const lignes = [
      participation({ courseId: 7, rank_overall: 40 }),
      participation({ courseId: 7, rank_overall: 2 }),
      participation({ courseId: 9, rank_overall: 15 }),
    ];
    expect(compteMaSaison(lignes, "scratch").epreuves).toBe(2);
  });

  it("compte un podium à partir du rang 3 inclus", () => {
    const lignes = [
      participation({ courseId: 1, rank_overall: 1 }),
      participation({ courseId: 2, rank_overall: 3 }),
      participation({ courseId: 3, rank_overall: 4 }),
      participation({ courseId: 4, rank_overall: null }),
    ];
    expect(compteMaSaison(lignes, "scratch").podiums).toBe(2);
  });

  it("change de compte selon le mode de rang", () => {
    const lignes = [
      participation({ courseId: 1, rank_overall: 40, rank_category: 2, rank_gender: 25 }),
    ];
    expect(compteMaSaison(lignes, "scratch").podiums).toBe(0);
    expect(compteMaSaison(lignes, "category").podiums).toBe(1);
    expect(compteMaSaison(lignes, "gender").podiums).toBe(0);
    expect(compteMaSaison(lignes, "all").podiums).toBe(1);
  });

  it("exclut les résultats en attente de validation", () => {
    const lignes = [
      participation({ courseId: 1, rank_overall: 1 }),
      participation({ courseId: 2, rank_overall: 1, is_pending_validation: true }),
    ];
    expect(compteMaSaison(lignes, "scratch")).toEqual({ epreuves: 1, podiums: 1 });
  });

  it("rend deux zéros sur une liste vide", () => {
    expect(compteMaSaison([], "scratch")).toEqual({ epreuves: 0, podiums: 0 });
  });
});
