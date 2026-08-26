import { describe, it, expect } from "vitest";
import { disciplineOf, disciplineBreakdownBySeason, motCompte, ordinalFr } from "./format";
import type { Participation } from "@/lib/types";

let nextId = 1;

function participation(eventType: string, eventDate: string, distanceKm: number | null = null): Participation {
  return {
    id: nextId++,
    athlete: { id: 1, nom: "", prenom: "", gender: "", club: null },
    course: {
      id: nextId,
      name: "",
      event_date: eventDate,
      event_type: eventType,
      provider: "manuel",
      source_url: "",
      is_relay: false,
      distance_km: distanceKm,
    },
    club: null,
    is_tcn: true,
    category: null,
    bib_number: null,
    rank_overall: null,
    rank_category: null,
    rank_gender: null,
    total_time: null,
    status: "ok",
    is_relay: false,
    splits: null,
    created_at: null,
  };
}

describe("ordinalFr", () => {
  it("écrit « 1er » pour la première place", () => {
    expect(ordinalFr(1)).toBe("1er");
  });

  it("écrit « ne » pour les autres places", () => {
    expect(ordinalFr(2)).toBe("2e");
    expect(ordinalFr(42)).toBe("42e");
    expect(ordinalFr(300)).toBe("300e");
  });
});

describe("disciplineOf", () => {
  it("met le format de côté : les tailles d'une discipline se ramènent à elle", () => {
    expect(disciplineOf("triathlon-m")).toBe("triathlon");
    expect(disciplineOf("triathlon-xl")).toBe("triathlon");
    expect(disciplineOf("duathlon-s")).toBe("duathlon");
    expect(disciplineOf("swimrun-l")).toBe("swimrun");
  });

  it("ramène aussi les formats nommés de la course à pied", () => {
    expect(disciplineOf("course-a-pied-semi")).toBe("course-a-pied");
    expect(disciplineOf("course-a-pied-10k")).toBe("course-a-pied");
    expect(disciplineOf("cyclisme-clm")).toBe("cyclisme");
  });

  it("laisse intacte une discipline qui n'a pas de format", () => {
    expect(disciplineOf("trail")).toBe("trail");
    expect(disciplineOf("bike-run")).toBe("bike-run");
    expect(disciplineOf("raid-multisport")).toBe("raid-multisport");
  });

  it("ne confond pas le cross triathlon avec le triathlon", () => {
    expect(disciplineOf("cross-triathlon")).toBe("cross-triathlon");
  });

  it("rend tel quel un type inconnu, et la chaîne vide pour une absence", () => {
    expect(disciplineOf("natation-eau-libre")).toBe("natation-eau-libre");
    expect(disciplineOf(null)).toBe("");
    expect(disciplineOf(undefined)).toBe("");
  });
});

describe("disciplineBreakdownBySeason", () => {
  it("groupe par saison (année de event_date), triée de la plus récente à la plus ancienne", () => {
    const parts = [
      participation("triathlon-m", "2024-06-01"),
      participation("trail", "2025-03-01"),
      participation("triathlon-s", "2025-09-01"),
    ];
    const breakdown = disciplineBreakdownBySeason(parts);
    expect(breakdown.map((b) => b.season)).toEqual(["2025", "2024"]);
  });

  it("compte chaque jeton de format par saison, pas seulement le mode", () => {
    const parts = [
      participation("triathlon-m", "2025-06-01"),
      participation("triathlon-m", "2025-07-01"),
      participation("trail", "2025-09-01"),
    ];
    const breakdown = disciplineBreakdownBySeason(parts);
    const season2025 = breakdown.find((b) => b.season === "2025");
    expect(season2025?.entries).toEqual(
      expect.arrayContaining([
        ["M", 2],
        ["TR", 1],
      ]),
    );
  });

  it("exclut les jetons non résolus (« — ») et les épreuves sans date", () => {
    const parts = [participation("inconnu-sans-taille", "2025-01-01"), participation("triathlon-m", "")];
    const breakdown = disciplineBreakdownBySeason(parts);
    expect(breakdown).toEqual([]);
  });

  it("rend une liste vide sur une liste de participations vide", () => {
    expect(disciplineBreakdownBySeason([])).toEqual([]);
  });
});

describe("motCompte", () => {
  it("laisse le singulier à 1", () => {
    expect(motCompte(1, "podium")).toBe("1 podium");
  });

  it("accorde au pluriel au-delà", () => {
    expect(motCompte(2, "podium")).toBe("2 podiums");
    expect(motCompte(4, "épreuve")).toBe("4 épreuves");
  });

  // Le zéro français est singulier — « 0 podium », pas « 0 podiums ».
  it("laisse le singulier à 0", () => {
    expect(motCompte(0, "épreuve")).toBe("0 épreuve");
  });
});
