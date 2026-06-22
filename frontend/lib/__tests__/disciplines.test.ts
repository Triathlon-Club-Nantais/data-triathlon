import { describe, expect, it } from "vitest";
import { disciplineLabel, eventTypeLabel } from "@/lib/constants";

describe("eventTypeLabel", () => {
  it("libelle les slugs nus", () => {
    expect(eventTypeLabel("triathlon")).toBe("Triathlon");
    expect(eventTypeLabel("duathlon")).toBe("Duathlon");
    expect(eventTypeLabel("swimrun")).toBe("SwimRun");
  });

  it("libelle les nouveaux mono-sports", () => {
    expect(eventTypeLabel("trail")).toBe("Trail");
    expect(eventTypeLabel("course-a-pied-marathon")).toBe("Marathon");
    expect(eventTypeLabel("cyclisme-clm")).toBe("Cyclisme (CLM)");
  });
});

describe("disciplineLabel", () => {
  it("ajoute le kilométrage quand présent", () => {
    expect(disciplineLabel({ event_type: "trail", distance_km: 23 })).toBe(
      "Trail · 23 km",
    );
  });

  it("omet le kilométrage si absent", () => {
    expect(disciplineLabel({ event_type: "trail", distance_km: null })).toBe(
      "Trail",
    );
  });
});
