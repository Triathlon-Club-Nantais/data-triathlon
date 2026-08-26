import { describe, it, expect } from "vitest";
import { rankRatio, bestRatio, progressionSeries } from "./ranking";
import type { Participation } from "@/lib/types";

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: { id: 1, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" },
    course: {
      id: 1,
      name: "Tri Z",
      event_date: "2026-05-16",
      event_type: "triathlon-m",
      provider: "manuel",
      source_url: "",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: null,
    bib_number: null,
    rank_overall: over.rank_overall ?? null,
    rank_category: null,
    rank_gender: null,
    total_time: "01:59:00",
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    course_finishers: over.course_finishers,
  };
}

describe("rankRatio", () => {
  it("rapporte la place au nombre de classés", () => {
    expect(rankRatio(part({ id: 1, rank_overall: 42, course_finishers: 300 }))).toEqual({
      ratio: { rank: 42, total: 300, percent: 14 },
    });
    expect(rankRatio(part({ id: 2, rank_overall: 20, course_finishers: 80 }))).toEqual({
      ratio: { rank: 20, total: 80, percent: 25 },
    });
  });

  it("arrondit au supérieur : jamais de « Top 0 % »", () => {
    expect(rankRatio(part({ id: 1, rank_overall: 1, course_finishers: 300 })).ratio?.percent).toBe(1);
  });

  it("renvoie ratio=null sans reason quand la place manque", () => {
    expect(rankRatio(part({ id: 1, rank_overall: null, course_finishers: 300 }))).toEqual({
      ratio: null,
      reason: "incomplete",
    });
  });

  it("renvoie ratio=null reason=incomplete sans compte de classés", () => {
    expect(rankRatio(part({ id: 1, rank_overall: 42, course_finishers: null }))).toEqual({
      ratio: null,
      reason: "incomplete",
    });
    expect(rankRatio(part({ id: 2, rank_overall: 42 }))).toEqual({
      ratio: null,
      reason: "incomplete",
    });
  });

  it("renvoie ratio=null reason=incomplete quand la place dépasse le compte", () => {
    expect(rankRatio(part({ id: 1, rank_overall: 42, course_finishers: 20 }))).toEqual({
      ratio: null,
      reason: "incomplete",
    });
  });

  it("renvoie ratio=null reason=incomplete sous deux classés", () => {
    expect(rankRatio(part({ id: 1, rank_overall: 1, course_finishers: 1 }))).toEqual({
      ratio: null,
      reason: "incomplete",
    });
  });

  it("renvoie ratio=null reason=unreliable quand la course est marquée non fiable", () => {
    // Même avec des données par ailleurs complètes, on distingue le refus
    // volontaire (`is_reliable=false`) d'un simple manque de données.
    const p = part({ id: 1, rank_overall: 3, course_finishers: 300 });
    p.course = { ...p.course, is_reliable: false };
    expect(rankRatio(p)).toEqual({ ratio: null, reason: "unreliable" });
  });

  it("produit un ratio quand la course est explicitement fiable", () => {
    const p = part({ id: 1, rank_overall: 3, course_finishers: 300 });
    p.course = { ...p.course, is_reliable: true };
    expect(rankRatio(p).ratio).not.toBeNull();
  });

  it("produit un ratio quand `is_reliable` est absent (non-régression)", () => {
    const p = part({ id: 1, rank_overall: 3, course_finishers: 300 });
    expect(rankRatio(p).ratio).not.toBeNull();
  });
});

describe("bestRatio", () => {
  it("retient le meilleur ratio, pas la meilleure place", () => {
    const best = bestRatio([
      part({ id: 1, rank_overall: 42, course_finishers: 300 }),
      part({ id: 2, rank_overall: 20, course_finishers: 80 }),
    ]);
    expect(best?.participation.id).toBe(1);
    expect(best?.ratio.percent).toBe(14);
  });

  it("départage deux ratios égaux par la place absolue", () => {
    const best = bestRatio([
      part({ id: 1, rank_overall: 20, course_finishers: 200 }),
      part({ id: 2, rank_overall: 10, course_finishers: 100 }),
    ]);
    expect(best?.participation.id).toBe(2);
  });

  it("départage aussi deux ratios égaux non représentables en binaire (1/3)", () => {
    const best = bestRatio([
      part({ id: 1, rank_overall: 2, course_finishers: 6 }),
      part({ id: 2, rank_overall: 1, course_finishers: 3 }),
    ]);
    expect(best?.participation.id).toBe(2);
  });

  it("ignore les participations sans ratio exploitable", () => {
    expect(bestRatio([part({ id: 1, rank_overall: 42, course_finishers: 20 })])).toBeNull();
    expect(bestRatio([])).toBeNull();
  });

  it("ignore les participations dont la course est non fiable", () => {
    const p = part({ id: 1, rank_overall: 3, course_finishers: 300 });
    p.course = { ...p.course, is_reliable: false };
    expect(bestRatio([p])).toBeNull();
  });
});

describe("progressionSeries", () => {
  it("ordonne chronologiquement, du plus ancien au plus récent", () => {
    const recent = part({ id: 1, rank_overall: 10, course_finishers: 100 });
    recent.course = { ...recent.course, event_date: "2026-06-01" };
    const ancien = part({ id: 2, rank_overall: 5, course_finishers: 50 });
    ancien.course = { ...ancien.course, event_date: "2026-01-10" };

    const series = progressionSeries([recent, ancien]);
    expect(series.map((point) => point.participationId)).toEqual([2, 1]);
  });

  it("exclut les participations sans ratio exploitable", () => {
    const sansRang = part({ id: 1, rank_overall: null, course_finishers: 100 });
    const avecRatio = part({ id: 2, rank_overall: 5, course_finishers: 50 });
    avecRatio.course = { ...avecRatio.course, event_date: "2026-01-10" };

    const series = progressionSeries([sansRang, avecRatio]);
    expect(series).toHaveLength(1);
    expect(series[0].participationId).toBe(2);
  });

  it("exclut les participations sans date d'épreuve : l'ordre chronologique n'a pas de sens sans elle", () => {
    const sansDate = part({ id: 1, rank_overall: 5, course_finishers: 50 });
    sansDate.course = { ...sansDate.course, event_date: null };

    expect(progressionSeries([sansDate])).toEqual([]);
  });

  it("renvoie une série vide sur une liste vide", () => {
    expect(progressionSeries([])).toEqual([]);
  });

  it("porte le pourcentage de ratio de chaque point", () => {
    const p = part({ id: 1, rank_overall: 42, course_finishers: 300 });
    p.course = { ...p.course, event_date: "2026-05-16" };
    expect(progressionSeries([p])).toEqual([{ participationId: 1, eventDate: "2026-05-16", percent: 14 }]);
  });
});
