import { describe, expect, it } from "vitest";
import type { Participation } from "@/lib/types";
import { chiffresSaison, ecart, fenetreSaisonPrecedente, formatTempsTotal } from "./mon-espace";

let id = 0;
function part(extra: Omit<Partial<Participation>, "course"> & { course?: Partial<Participation["course"]> } = {}): Participation {
  id += 1;
  const { course, ...rest } = extra;
  return {
    id,
    course: { id, name: "E", event_date: "2026-10-01", event_type: "triathlon-m", provider: "x", source_url: "", is_relay: false, is_reliable: true, distance_km: 50, ...course },
    rank_overall: 5, course_finishers: 100, rank_category: 9, rank_gender: 9, total_time: "2:00:00", status: "finisher",
    is_relay: false, is_pending_validation: false, ...rest,
  } as Participation;
}

describe("chiffresSaison", () => {
  it("sums figures, refusing the ratio of an unreliable course and skipping relays for personal figures", () => {
    const result = chiffresSaison([
      part({ rank_overall: 2, course_finishers: 100 }),
      part({ rank_overall: 10, course_finishers: 50, course: { is_reliable: false, distance_km: 20 }, total_time: "1:00:00" }),
      part({ is_relay: true, rank_overall: 1, course: { is_relay: true, distance_km: 100 }, total_time: "5:00:00" }),
      part({ course: { is_relay: true, distance_km: 30 }, total_time: "3:00:00" }),
    ]);
    expect(result).toEqual({ epreuves: 4, podiums: 1, km: 70, tempsSecondes: 10800, meilleurRatio: 2 });
  });

  it("has a null best ratio and zeros when empty", () => {
    expect(chiffresSaison([])).toEqual({ epreuves: 0, podiums: 0, km: 0, tempsSecondes: 0, meilleurRatio: null });
  });
});

describe("fenetreSaisonPrecedente", () => {
  it("covers the previous season up to the same date one year earlier", () => {
    expect(fenetreSaisonPrecedente(2026, new Date("2026-10-15T10:00:00Z"))).toEqual({ start: "2025-09-01", end: "2025-10-15" });
  });
  it("is bounded to the previous season for a closed season", () => {
    expect(fenetreSaisonPrecedente(2024, new Date("2026-10-15T10:00:00Z"))).toEqual({ start: "2023-09-01", end: "2024-08-31" });
  });
});

describe("ecart and formatTempsTotal", () => {
  it("subtracts", () => expect(ecart(5, 3)).toBe(2));
  it("formats hours and minutes", () => expect(formatTempsTotal(3600 * 12 + 300)).toBe("12 h 05"));
});
