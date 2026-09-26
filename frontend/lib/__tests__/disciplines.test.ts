import { describe, expect, it } from "vitest";
import { eventTypeLabel } from "@/lib/constants";

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
