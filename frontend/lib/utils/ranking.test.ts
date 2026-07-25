import { describe, it, expect } from "vitest";
import { rankRatio, bestRatio } from "./ranking";
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
      rank: 42,
      total: 300,
      percent: 14,
    });
    expect(rankRatio(part({ id: 2, rank_overall: 20, course_finishers: 80 }))).toEqual({
      rank: 20,
      total: 80,
      percent: 25,
    });
  });

  it("arrondit au supérieur : jamais de « Top 0 % »", () => {
    expect(rankRatio(part({ id: 1, rank_overall: 1, course_finishers: 300 }))?.percent).toBe(1);
  });

  it("renvoie null sans place", () => {
    expect(rankRatio(part({ id: 1, rank_overall: null, course_finishers: 300 }))).toBeNull();
  });

  it("renvoie null sans compte de classés", () => {
    expect(rankRatio(part({ id: 1, rank_overall: 42, course_finishers: null }))).toBeNull();
    expect(rankRatio(part({ id: 2, rank_overall: 42 }))).toBeNull();
  });

  it("renvoie null quand la place dépasse le compte (import partiel)", () => {
    expect(rankRatio(part({ id: 1, rank_overall: 42, course_finishers: 20 }))).toBeNull();
  });

  it("renvoie null sous deux classés : un « 1er sur 1 » ne dit rien", () => {
    expect(rankRatio(part({ id: 1, rank_overall: 1, course_finishers: 1 }))).toBeNull();
  });

  it("renvoie null quand la course est explicitement marquée non fiable", () => {
    const p = part({ id: 1, rank_overall: 3, course_finishers: 300 });
    p.course = { ...p.course, is_reliable: false };
    expect(rankRatio(p)).toBeNull();
  });

  it("produit un ratio quand la course est explicitement fiable", () => {
    const p = part({ id: 1, rank_overall: 3, course_finishers: 300 });
    p.course = { ...p.course, is_reliable: true };
    expect(rankRatio(p)).not.toBeNull();
  });

  it("produit un ratio quand `is_reliable` est absent (non-régression)", () => {
    const p = part({ id: 1, rank_overall: 3, course_finishers: 300 });
    expect(rankRatio(p)).not.toBeNull();
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

  it("ignore les participations sans ratio exploitable", () => {
    expect(bestRatio([part({ id: 1, rank_overall: 42, course_finishers: 20 })])).toBeNull();
    expect(bestRatio([])).toBeNull();
  });
});
