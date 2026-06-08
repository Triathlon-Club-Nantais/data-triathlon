import { describe, it, expect, vi, afterEach } from "vitest";
import { formatDate, timeAgo, formatMonth } from "./date";

describe("formatDate", () => {
  it("formate une date ISO en fr-FR", () => {
    expect(formatDate("2026-03-15")).toBe("15/03/2026");
  });
  it("renvoie une chaîne vide si null", () => {
    expect(formatDate(null)).toBe("");
  });
});

describe("formatMonth", () => {
  it("formate YYYY-MM en mois/année français", () => {
    expect(formatMonth("2026-03")).toBe("mars 2026");
  });
});

describe("timeAgo", () => {
  afterEach(() => vi.useRealTimers());
  it("renvoie aujourd'hui pour maintenant", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-07T12:00:00Z"));
    expect(timeAgo("2026-06-07T08:00:00Z")).toBe("aujourd'hui");
  });
  it("renvoie hier pour la veille", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-07T12:00:00Z"));
    expect(timeAgo("2026-06-06T08:00:00Z")).toBe("hier");
  });
  it("renvoie une chaîne vide si null", () => {
    expect(timeAgo(null)).toBe("");
  });
});
