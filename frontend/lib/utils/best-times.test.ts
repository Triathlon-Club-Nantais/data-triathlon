import { describe, it, expect } from "vitest";
import type { CourseBrief, Participation } from "@/lib/types";
import { bestTimes } from "./best-times";

function part(
  over: Partial<Omit<Participation, "course">> & { id: number; course?: Partial<CourseBrief> },
): Participation {
  const { course, ...rest } = over;
  return {
    athlete: { id: 7, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" },
    club: "TCN",
    is_tcn: true,
    category: null,
    bib_number: null,
    rank_overall: null,
    rank_category: null,
    rank_gender: null,
    total_time: "02:10:00",
    status: "finisher",
    is_relay: false,
    is_pending_validation: false,
    splits: null,
    ...rest,
    course: {
      id: over.id,
      name: `Course ${over.id}`,
      event_date: "2026-05-16",
      event_type: "triathlon-m",
      provider: "manuel",
      source_url: "",
      is_relay: false,
      ...course,
    },
  } as Participation;
}

const ids = (parts: Participation[]) => bestTimes(parts).map((line) => line.participation.id);

describe("bestTimes", () => {
  it("returns nothing without participations", () => {
    expect(bestTimes([])).toEqual([]);
  });

  it("keeps the fastest time per discipline and format", () => {
    const lines = bestTimes([
      part({ id: 1, total_time: "02:20:00" }),
      part({ id: 2, total_time: "2:05:30" }),
      part({ id: 3, total_time: "02:15:00" }),
    ]);

    expect(lines).toHaveLength(1);
    expect(lines[0]).toMatchObject({ discipline: "triathlon", format: "M", seconds: 7530 });
    expect(lines[0].participation.id).toBe(2);
  });

  it("splits a triathlon M from a duathlon M", () => {
    const lines = bestTimes([
      part({ id: 1, course: { event_type: "triathlon-m" } }),
      part({ id: 2, course: { event_type: "duathlon-m" } }),
    ]);

    expect(lines.map((line) => [line.discipline, line.format])).toEqual([
      ["duathlon", "M"],
      ["triathlon", "M"],
    ]);
  });

  it("orders by discipline label, then by time", () => {
    const lines = bestTimes([
      part({ id: 1, total_time: "04:30:00", course: { event_type: "triathlon-l" } }),
      part({ id: 2, total_time: "01:05:00", course: { event_type: "triathlon-s" } }),
      part({ id: 3, total_time: "01:20:00", course: { event_type: "duathlon-s" } }),
    ]);

    expect(lines.map((line) => line.participation.id)).toEqual([3, 2, 1]);
  });

  it("keeps the earliest participation on a tie, whatever the input order", () => {
    expect(
      ids([
        part({ id: 1, total_time: "02:00:00", course: { event_date: "2026-06-01" } }),
        part({ id: 2, total_time: "02:00:00", course: { event_date: "2025-06-01" } }),
      ]),
    ).toEqual([2]);
  });

  it("uses the distance as format when the event type carries none", () => {
    const lines = bestTimes([
      part({ id: 1, total_time: "00:45:00", course: { event_type: "course-a-pied", distance_km: 10 } }),
    ]);

    expect(lines[0]).toMatchObject({ discipline: "course-a-pied", format: "10km" });
  });

  it("excludes a relay result, flagged on the result or on the event", () => {
    expect(
      ids([
        part({ id: 1, total_time: "01:00:00", is_relay: true }),
        part({ id: 2, total_time: "01:00:00", course: { is_relay: true } }),
        part({ id: 3, total_time: "02:00:00" }),
      ]),
    ).toEqual([3]);
  });

  it("excludes a result pending validation", () => {
    expect(
      ids([part({ id: 1, total_time: "01:00:00", is_pending_validation: true }), part({ id: 2 })]),
    ).toEqual([2]);
  });

  it("excludes an unreliable event, but keeps one never evaluated", () => {
    expect(
      ids([
        part({ id: 1, total_time: "01:00:00", course: { is_reliable: false } }),
        part({ id: 2, total_time: "01:30:00", course: { is_reliable: null } }),
      ]),
    ).toEqual([2]);
  });

  it("excludes a missing or unreadable time", () => {
    expect(
      ids([part({ id: 1, total_time: null }), part({ id: 2, total_time: "n/a" })]),
    ).toEqual([]);
  });

  it("treats a zero time as absent, so it never hides the real best", () => {
    expect(
      ids([
        part({ id: 1, total_time: "02:10:00" }),
        part({ id: 2, total_time: "00:00:00", status: "" }),
        part({ id: 3, total_time: "0:00", status: "" }),
      ]),
    ).toEqual([1]);
  });

  it("excludes a non-finisher even with a time", () => {
    expect(ids([part({ id: 1, total_time: "01:00:00", status: "DSQ" })])).toEqual([]);
  });

  it("excludes an unknown format", () => {
    expect(ids([part({ id: 1, course: { event_type: "triathlon" } })])).toEqual([]);
  });

  it("excludes a format that only names the discipline, so distances never mix", () => {
    expect(
      ids([
        part({ id: 1, total_time: "01:35:00", course: { event_type: "course-a-pied-semi" } }),
        part({ id: 2, total_time: "03:30:00", course: { event_type: "course-a-pied-marathon" } }),
        part({ id: 3, course: { event_type: "trail" } }),
        part({ id: 4, course: { event_type: "cyclisme-clm" } }),
        part({ id: 5, course: { event_type: "aquathlon" } }),
      ]),
    ).toEqual([]);
  });

  it("excludes an event without discipline", () => {
    expect(ids([part({ id: 1, course: { event_type: "", distance_km: 10 } })])).toEqual([]);
  });
});
