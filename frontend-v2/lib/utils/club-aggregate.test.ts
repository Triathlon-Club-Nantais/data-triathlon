import { describe, it, expect } from "vitest";
import {
  bestPodiumRank,
  isPodium,
  listPodiums,
  buildRoster,
  recentParticipations,
  clubSummary,
} from "./club-aggregate";
import type { Participation } from "@/lib/types";

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: over.athlete ?? {
      id: 1,
      nom: "Dupont",
      prenom: "Marie",
      gender: "F",
      club: "TCN",
    },
    course: over.course ?? {
      id: 10,
      name: "Triathlon de Nantes",
      event_date: "2026-05-10",
      event_type: "triathlon-m",
      provider: "klikego",
      source_url: "http://x",
      is_relay: false,
    },
    club: over.club ?? "TCN",
    category: over.category ?? "S4",
    bib_number: over.bib_number ?? "1",
    rank_overall: over.rank_overall ?? null,
    rank_category: over.rank_category ?? null,
    rank_gender: over.rank_gender ?? null,
    total_time: over.total_time ?? "02:00:00",
    status: "finisher",
    splits: over.splits ?? null,
    created_at: over.created_at ?? "2026-05-11T10:00:00Z",
  };
}

describe("bestPodiumRank", () => {
  it("retient le meilleur rang top-3 (général prioritaire)", () => {
    const p = part({ id: 1, rank_overall: 2, rank_category: 1, rank_gender: 3 });
    expect(bestPodiumRank(p)).toEqual({ rank: 1, scope: "category" });
  });
  it("renvoie null hors top-3", () => {
    expect(bestPodiumRank(part({ id: 1, rank_overall: 12 }))).toBeNull();
  });
  it("isPodium reflète bestPodiumRank", () => {
    expect(isPodium(part({ id: 1, rank_gender: 3 }))).toBe(true);
    expect(isPodium(part({ id: 1, rank_overall: 50 }))).toBe(false);
  });
});

describe("listPodiums", () => {
  it("filtre et trie par rang croissant", () => {
    const parts = [
      part({ id: 1, rank_overall: 3 }),
      part({ id: 2, rank_overall: 1 }),
      part({ id: 3, rank_overall: 20 }),
    ];
    const result = listPodiums(parts);
    expect(result.map((e) => e.participation.id)).toEqual([2, 1]);
  });
});

describe("buildRoster", () => {
  it("regroupe par athlète avec compteurs", () => {
    const a = { id: 1, nom: "A", prenom: "Alice", gender: "F", club: "TCN" };
    const b = { id: 2, nom: "B", prenom: "Bob", gender: "M", club: "TCN" };
    const parts = [
      part({ id: 1, athlete: a, rank_overall: 1, course: { id: 1, name: "C1", event_date: "2026-01-01", event_type: "triathlon-s", provider: "k", source_url: "u", is_relay: false } }),
      part({ id: 2, athlete: a, course: { id: 2, name: "C2", event_date: "2026-03-01", event_type: "triathlon-s", provider: "k", source_url: "u", is_relay: false } }),
      part({ id: 3, athlete: b, rank_overall: 12 }),
    ];
    const roster = buildRoster(parts);
    expect(roster[0].athleteId).toBe(1);
    expect(roster[0].count).toBe(2);
    expect(roster[0].podiums).toBe(1);
    expect(roster[0].lastDate).toBe("2026-03-01");
    expect(roster[0].lastEvent).toBe("C2");
    expect(roster[1].athleteId).toBe(2);
    expect(roster[1].count).toBe(1);
  });
});

describe("recentParticipations", () => {
  it("trie par date d'épreuve décroissante", () => {
    const parts = [
      part({ id: 1, course: { id: 1, name: "old", event_date: "2026-01-01", event_type: "triathlon-s", provider: "k", source_url: "u", is_relay: false } }),
      part({ id: 2, course: { id: 2, name: "new", event_date: "2026-06-01", event_type: "triathlon-s", provider: "k", source_url: "u", is_relay: false } }),
    ];
    expect(recentParticipations(parts).map((p) => p.id)).toEqual([2, 1]);
  });
});

describe("clubSummary", () => {
  it("compte résultats, athlètes, épreuves et podiums", () => {
    const a = { id: 1, nom: "A", prenom: "Alice", gender: "F", club: "TCN" };
    const b = { id: 2, nom: "B", prenom: "Bob", gender: "M", club: "TCN" };
    const parts = [
      part({ id: 1, athlete: a, rank_overall: 1 }),
      part({ id: 2, athlete: b, rank_overall: 30 }),
    ];
    const s = clubSummary(parts);
    expect(s.results).toBe(2);
    expect(s.athletes).toBe(2);
    expect(s.events).toBe(1);
    expect(s.podiums).toBe(1);
  });
});
