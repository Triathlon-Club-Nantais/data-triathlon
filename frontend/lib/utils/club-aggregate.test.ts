import { describe, it, expect } from "vitest";
import { recentParticipations, disciplinePerformance } from "./club-aggregate";
import type { Participation, DisciplinePodiumCounts } from "@/lib/types";

function counts(over: Partial<DisciplinePodiumCounts> = {}): DisciplinePodiumCounts {
  return { overall: 0, gender: 0, category: 0, all: 0, ...over };
}

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

describe("disciplinePerformance", () => {
  it("groupe le décompte d'épreuves et de podiums par discipline, format mis de côté (US10, #466, #642)", () => {
    // triathlon-m et triathlon-s → même discipline « triathlon ».
    const podiumsByType = {
      "triathlon-m": counts({ overall: 1, all: 1 }),
      "trail-l": counts({ overall: 1, all: 1 }),
    };
    const countByType = { "triathlon-m": 1, "triathlon-s": 1, "trail-l": 1 };

    const result = disciplinePerformance(podiumsByType, countByType);

    expect(result).toEqual([
      { discipline: "triathlon", count: 2, podiums: 1 },
      { discipline: "trail", count: 1, podiums: 1 },
    ]);
  });

  it("respecte le rankType passé", () => {
    const podiumsByType = { "trail-l": counts({ overall: 0, category: 1, all: 1 }) };
    const countByType = { "trail-l": 1 };

    expect(disciplinePerformance(podiumsByType, countByType, "scratch")[0].podiums).toBe(0);
    expect(disciplinePerformance(podiumsByType, countByType, "category")[0].podiums).toBe(1);
  });

  it("ignore les disciplines dont l'event_type ne se résout pas", () => {
    expect(disciplinePerformance({}, { "": 1 })).toEqual([]);
  });

  it("garde une discipline sans podium (compte issu de countByType seul)", () => {
    const result = disciplinePerformance({}, { "trail-l": 3 });
    expect(result).toEqual([{ discipline: "trail", count: 3, podiums: 0 }]);
  });

  it("trie par podiums décroissant puis par nombre d'épreuves décroissant", () => {
    // trail : 1 podium, 1 épreuve. cyclisme (deux sous-types fondus) :
    // aucun podium, 2 épreuves — le podium l'emporte malgré le volume.
    const podiumsByType = { "trail-l": counts({ overall: 1, all: 1 }) };
    const countByType = { "trail-l": 1, "cyclisme-clm": 1, "cyclisme-route": 1 };

    const result = disciplinePerformance(podiumsByType, countByType);

    expect(result.map((r) => r.discipline)).toEqual(["trail", "cyclisme"]);
  });
});
