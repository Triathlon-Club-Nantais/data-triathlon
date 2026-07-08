import { describe, it, expect } from "vitest";
import { orderParticipations, isNonFinisher, isFinisher, countOutcomes } from "./raceOrder";
import type { Participation } from "@/lib/types";

function p(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: { id: over.id, nom: over.athlete?.nom ?? "X", prenom: over.athlete?.prenom ?? "Y", gender: "M", club: null },
    course: { id: 1, event_name: "C", event_date: null, event_type: null },
    club: null,
    category: null,
    bib_number: null,
    rank_overall: over.rank_overall ?? null,
    rank_category: null,
    rank_gender: null,
    total_time: over.total_time ?? null,
    status: over.status ?? "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
  } as Participation;
}

describe("orderParticipations", () => {
  it("place les finishers avant les non-finishers, par rang", () => {
    const out = orderParticipations([
      p({ id: 3, status: "DNS", rank_overall: 1 }),
      p({ id: 1, status: "finisher", rank_overall: 2 }),
      p({ id: 2, status: "finisher", rank_overall: 1 }),
    ]);
    expect(out.map((x) => x.id)).toEqual([2, 1, 3]);
  });

  it("ordonne les groupes DNF → DSQ → DNS", () => {
    const out = orderParticipations([
      p({ id: 1, status: "DNS" }),
      p({ id: 2, status: "DSQ" }),
      p({ id: 3, status: "DNF" }),
    ]);
    expect(out.map((x) => x.id)).toEqual([3, 2, 1]);
  });

  it("dans un groupe, trie par temps croissant puis place les sans-temps en fin", () => {
    const out = orderParticipations([
      p({ id: 1, status: "DNF", total_time: null, athlete: { nom: "ZZZ" } as never }),
      p({ id: 2, status: "DNF", total_time: "01:10:00" }),
      p({ id: 3, status: "DNF", total_time: "00:50:00" }),
    ]);
    expect(out.map((x) => x.id)).toEqual([3, 2, 1]);
  });

  it("traite 00:00:00 comme une absence de temps", () => {
    const out = orderParticipations([
      p({ id: 1, status: "DNS", total_time: "00:00:00", athlete: { nom: "BBB" } as never }),
      p({ id: 2, status: "DNS", total_time: null, athlete: { nom: "AAA" } as never }),
    ]);
    // tous deux sans temps → tri alphabétique : AAA (2) avant BBB (1)
    expect(out.map((x) => x.id)).toEqual([2, 1]);
  });
});

describe("isNonFinisher", () => {
  it("reconnaît DNF/DNS/DSQ (toute casse) et rejette finisher/vide", () => {
    expect(isNonFinisher("DNF")).toBe(true);
    expect(isNonFinisher("dns")).toBe(true);
    expect(isNonFinisher("DSQ")).toBe(true);
    expect(isNonFinisher("finisher")).toBe(false);
    expect(isNonFinisher("")).toBe(false);
    expect(isNonFinisher(null)).toBe(false);
    expect(isNonFinisher(undefined)).toBe(false);
  });
});

describe("isFinisher", () => {
  it("ne reconnaît que le statut explicite « finisher » (toute casse)", () => {
    expect(isFinisher("finisher")).toBe(true);
    expect(isFinisher("Finisher")).toBe(true);
    expect(isFinisher("DNF")).toBe(false);
    expect(isFinisher("")).toBe(false);
    expect(isFinisher(null)).toBe(false);
    expect(isFinisher(undefined)).toBe(false);
  });
});

describe("countOutcomes", () => {
  it("décompte finishers / non-finishers / indéterminés séparément", () => {
    const out = countOutcomes([
      p({ id: 1, status: "finisher" }),
      p({ id: 2, status: "finisher" }),
      p({ id: 3, status: "DNF" }),
      p({ id: 4, status: "DNS" }),
      p({ id: 5, status: "DSQ" }),
      p({ id: 6, status: "" }),
      p({ id: 7, status: "en course" }),
    ]);
    expect(out).toEqual({ total: 7, finishers: 2, nonFinishers: 3, unknown: 2 });
  });

  it("gère une liste vide", () => {
    expect(countOutcomes([])).toEqual({ total: 0, finishers: 0, nonFinishers: 0, unknown: 0 });
  });
});
