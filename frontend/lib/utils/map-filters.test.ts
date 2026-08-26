import { describe, it, expect } from "vitest";
import { distanceKm, upcomingEvents, sortByDistance, POINT_REFERENCE } from "./map-filters";
import type { GeoEvent } from "@/lib/types";

function event(overrides: Partial<GeoEvent> = {}): GeoEvent {
  return {
    course_id: 1,
    event_name: "Épreuve",
    event_date: "2026-06-01",
    event_type: "triathlon",
    count: 10,
    tcn_count: 2,
    lat: 47.2,
    lon: -1.5,
    ...overrides,
  };
}

describe("distanceKm", () => {
  it("renvoie 0 pour deux points identiques", () => {
    expect(distanceKm(POINT_REFERENCE, POINT_REFERENCE)).toBe(0);
  });

  it("calcule une distance connue Nantes-Paris (~340 km à vol d'oiseau)", () => {
    const paris = { lat: 48.8566, lon: 2.3522 };
    const distance = distanceKm(POINT_REFERENCE, paris);
    expect(distance).toBeGreaterThan(330);
    expect(distance).toBeLessThan(350);
  });

  it("est symétrique", () => {
    const a = { lat: 47.2, lon: -1.5 };
    const b = { lat: 43.6, lon: 1.4 };
    expect(distanceKm(a, b)).toBeCloseTo(distanceKm(b, a), 6);
  });
});

describe("upcomingEvents", () => {
  const reference = new Date("2026-06-15T00:00:00Z");

  it("ne garde que les épreuves postérieures à la date de référence", () => {
    const events = [
      event({ course_id: 1, event_date: "2026-06-20" }),
      event({ course_id: 2, event_date: "2026-06-10" }),
    ];
    const result = upcomingEvents(events, reference);
    expect(result.map((e) => e.course_id)).toEqual([1]);
  });

  it("exclut les épreuves sans date connue", () => {
    const events = [event({ course_id: 1, event_date: null })];
    expect(upcomingEvents(events, reference)).toEqual([]);
  });

  it("renvoie un tableau vide sans épreuve à venir", () => {
    const events = [event({ event_date: "2020-01-01" })];
    expect(upcomingEvents(events, reference)).toEqual([]);
  });
});

describe("sortByDistance", () => {
  it("trie du plus proche au plus lointain, sans muter l'entrée", () => {
    const loin = event({ course_id: 1, lat: 48.8566, lon: 2.3522 });
    const proche = event({ course_id: 2, lat: POINT_REFERENCE.lat, lon: POINT_REFERENCE.lon });
    const events = [loin, proche];
    const sorted = sortByDistance(events);
    expect(sorted.map((e) => e.course_id)).toEqual([2, 1]);
    expect(events.map((e) => e.course_id)).toEqual([1, 2]);
  });
});
