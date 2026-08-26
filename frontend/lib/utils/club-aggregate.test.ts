import { describe, it, expect } from "vitest";
import { recentParticipations } from "./club-aggregate";
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
    is_tcn: over.is_tcn ?? true,
    category: over.category ?? "S4",
    bib_number: over.bib_number ?? "1",
    rank_overall: over.rank_overall ?? null,
    rank_category: over.rank_category ?? null,
    rank_gender: over.rank_gender ?? null,
    total_time: over.total_time ?? "02:00:00",
    status: "finisher",
    is_relay: over.is_relay ?? false,
    splits: over.splits ?? null,
    created_at: over.created_at ?? "2026-05-11T10:00:00Z",
  };
}

describe("recentParticipations", () => {
  it("trie par date d'épreuve décroissante", () => {
    const parts = [
      part({ id: 1, course: { id: 1, name: "old", event_date: "2026-01-01", event_type: "triathlon-s", provider: "k", source_url: "u", is_relay: false } }),
      part({ id: 2, course: { id: 2, name: "new", event_date: "2026-06-01", event_type: "triathlon-s", provider: "k", source_url: "u", is_relay: false } }),
    ];
    expect(recentParticipations(parts).map((p) => p.id)).toEqual([2, 1]);
  });
});

