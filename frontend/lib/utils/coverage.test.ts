import { describe, it, expect } from "vitest";
import { monthlyCoverage } from "./coverage";

function event(event_date: string | null) {
  return { event_date };
}

describe("monthlyCoverage", () => {
  it("compte les épreuves par mois", () => {
    const result = monthlyCoverage([
      event("2025-01-05"),
      event("2025-01-20"),
      event("2025-02-14"),
    ]);
    expect(result).toEqual([
      { month: "2025-01", count: 2 },
      { month: "2025-02", count: 1 },
    ]);
  });

  it("signale les mois sans épreuve dans la plage couverte, comptés à zéro", () => {
    const result = monthlyCoverage([event("2025-01-10"), event("2025-04-03")]);
    expect(result).toEqual([
      { month: "2025-01", count: 1 },
      { month: "2025-02", count: 0 },
      { month: "2025-03", count: 0 },
      { month: "2025-04", count: 1 },
    ]);
  });

  it("couvre un passage d'année", () => {
    const result = monthlyCoverage([event("2024-11-01"), event("2025-01-15")]);
    expect(result.map((r) => r.month)).toEqual(["2024-11", "2024-12", "2025-01"]);
  });

  it("ignore les épreuves sans date", () => {
    const result = monthlyCoverage([event(null), event("2025-01-10")]);
    expect(result).toEqual([{ month: "2025-01", count: 1 }]);
  });

  it("renvoie une liste vide sans épreuve datée", () => {
    expect(monthlyCoverage([])).toEqual([]);
    expect(monthlyCoverage([event(null)])).toEqual([]);
  });
});
