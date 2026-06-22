import { describe, it, expect } from "vitest";
import { buildResultsQuery } from "./ResultsFilters";

describe("buildResultsQuery", () => {
  it("ignore les champs vides", () => {
    expect(buildResultsQuery({ name: "marie", event_type: "" })).toBe("name=marie");
  });
  it("encode plusieurs filtres", () => {
    const qs = buildResultsQuery({ name: "x", event_type: "triathlon-m", club: "nantais" });
    expect(qs).toContain("name=x");
    expect(qs).toContain("event_type=triathlon-m");
    expect(qs).toContain("club=nantais");
  });
  it("renvoie une chaîne vide si tout est vide", () => {
    expect(buildResultsQuery({})).toBe("");
  });
});
