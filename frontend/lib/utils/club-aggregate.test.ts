import { describe, it, expect } from "vitest";
import {
  bestPodiumRank,
  bestRank,
  isTopN,
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

describe("bestRank", () => {
  it("retient le meilleur rang hors top-3", () => {
    const p = part({ id: 1, rank_overall: 40, rank_category: 7 });
    expect(bestRank(p)).toEqual({ rank: 7, scope: "category" });
  });
  it("privilégie le général à rang égal", () => {
    const p = part({ id: 1, rank_overall: 5, rank_gender: 5 });
    expect(bestRank(p)).toEqual({ rank: 5, scope: "overall" });
  });
  it("renvoie null sans aucun classement", () => {
    expect(bestRank(part({ id: 1 }))).toBeNull();
  });

  it("mode scratch : ne regarde que rank_overall", () => {
    // rank_category=1 (victoire cat) mais mode scratch → uniquement rank_overall
    const p = part({ id: 1, rank_overall: 25, rank_category: 1, rank_gender: 3 });
    expect(bestRank(p, "scratch")).toEqual({ rank: 25, scope: "overall" });
  });
  it("mode scratch : null si rank_overall absent, même avec les autres rangs présents", () => {
    const p = part({ id: 1, rank_category: 1, rank_gender: 1 });
    expect(bestRank(p, "scratch")).toBeNull();
  });

  it("mode category : ne regarde que rank_category", () => {
    const p = part({ id: 1, rank_overall: 1, rank_category: 12, rank_gender: 1 });
    expect(bestRank(p, "category")).toEqual({ rank: 12, scope: "category" });
  });
  it("mode category : null si rank_category absent", () => {
    const p = part({ id: 1, rank_overall: 3, rank_gender: 1 });
    expect(bestRank(p, "category")).toBeNull();
  });

  it("mode gender : ne regarde que rank_gender", () => {
    const p = part({ id: 1, rank_overall: 42, rank_category: 5, rank_gender: 2 });
    expect(bestRank(p, "gender")).toEqual({ rank: 2, scope: "gender" });
  });
  it("mode gender : null si rank_gender absent", () => {
    const p = part({ id: 1, rank_overall: 1, rank_category: 1 });
    expect(bestRank(p, "gender")).toBeNull();
  });

  it("mode all : préserve exactement le comportement du défaut (min des trois)", () => {
    const p = part({ id: 1, rank_overall: 40, rank_category: 7, rank_gender: 15 });
    expect(bestRank(p, "all")).toEqual(bestRank(p));
    expect(bestRank(p, "all")).toEqual({ rank: 7, scope: "category" });
  });
  it("mode all : privilégie 'overall' > 'gender' > 'category' à rang égal", () => {
    const p = part({ id: 1, rank_overall: 5, rank_gender: 5, rank_category: 5 });
    expect(bestRank(p, "all")).toEqual({ rank: 5, scope: "overall" });
  });
});

describe("isTopN", () => {
  it("compte un top-10 décroché sur le classement de catégorie", () => {
    expect(isTopN(part({ id: 1, rank_overall: 180, rank_category: 7 }), 10)).toBe(true);
  });
  it("exclut au-delà du seuil sur les trois classements", () => {
    expect(isTopN(part({ id: 1, rank_overall: 180, rank_category: 40 }), 10)).toBe(false);
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

  it("mode scratch : ne montre que les podiums où rank_overall ≤ 3", () => {
    const parts = [
      part({ id: 1, rank_overall: 30, rank_category: 1 }), // podium cat → exclu
      part({ id: 2, rank_overall: 2 }), // podium scratch → inclus
      part({ id: 3, rank_gender: 1 }), // podium genre → exclu
    ];
    const result = listPodiums(parts, "scratch");
    expect(result.map((e) => e.participation.id)).toEqual([2]);
    expect(result.every((e) => e.best.scope === "overall")).toBe(true);
  });

  it("mode category : ne montre que les podiums où rank_category ≤ 3", () => {
    const parts = [
      part({ id: 1, rank_overall: 1 }), // podium scratch → exclu
      part({ id: 2, rank_category: 3 }), // podium cat → inclus
      part({ id: 3, rank_gender: 2 }), // podium genre → exclu
    ];
    const result = listPodiums(parts, "category");
    expect(result.map((e) => e.participation.id)).toEqual([2]);
    expect(result.every((e) => e.best.scope === "category")).toBe(true);
  });

  it("mode all : préserve le mélange des trois scopes (comportement actuel)", () => {
    const parts = [
      part({ id: 1, rank_overall: 1 }),
      part({ id: 2, rank_category: 2 }),
      part({ id: 3, rank_gender: 3 }),
      part({ id: 4, rank_overall: 20 }),
    ];
    expect(listPodiums(parts, "all")).toEqual(listPodiums(parts));
    expect(listPodiums(parts, "all")).toHaveLength(3);
  });
});

describe("isPodium / isTopN — paramètre rankType", () => {
  it("mode scratch : ignore les podiums non-scratch", () => {
    // Podium catégorie mais pas scratch → false en mode scratch.
    const p = part({ id: 1, rank_overall: 100, rank_category: 1 });
    expect(isPodium(p, "scratch")).toBe(false);
    expect(isPodium(p, "category")).toBe(true);
  });

  it("mode category : compte un top 10 catégorie", () => {
    const p = part({ id: 1, rank_overall: 200, rank_category: 8 });
    expect(isTopN(p, 10, "category")).toBe(true);
    expect(isTopN(p, 10, "scratch")).toBe(false);
  });

  it("défaut sans rankType : comportement historique inchangé", () => {
    const p = part({ id: 1, rank_overall: 200, rank_category: 3 });
    expect(isPodium(p)).toBe(true);
    expect(isTopN(p, 10)).toBe(true);
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
