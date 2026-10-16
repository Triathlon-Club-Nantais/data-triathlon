import { describe, it, expect } from "vitest";
import { commonParticipations, formatDelta, headToHead } from "./athlete-comparison";
import type { Participation, CourseBrief, AthleteBrief } from "@/lib/types";

const athlete = (id: number): AthleteBrief => ({ id, nom: "Nom", prenom: "Prenom", gender: "F", club: "TCN" });

const course = (id: number, name: string, eventDate: string | null): CourseBrief => ({
  id,
  name,
  event_date: eventDate,
  event_type: "triathlon",
  provider: "manuel",
  source_url: "",
  is_relay: false,
});

const participation = (
  id: number,
  courseId: number,
  courseName: string,
  eventDate: string | null,
  totalTime: string | null,
): Participation => ({
  id,
  athlete: athlete(1),
  course: course(courseId, courseName, eventDate),
  club: "TCN",
  is_tcn: true,
  category: null,
  bib_number: null,
  rank_overall: null,
  rank_category: null,
  rank_gender: null,
  total_time: totalTime,
  status: "finisher",
  is_relay: false,
  splits: null,
  created_at: null,
});

describe("commonParticipations", () => {
  it("apparie les participations sur des épreuves communes, triées par date", () => {
    const mine = [
      participation(1, 10, "Triathlon A", "2026-06-01", "02:00:00"),
      participation(2, 20, "Triathlon B", "2026-03-01", "01:50:00"),
      participation(3, 30, "Triathlon C (solo)", "2026-08-01", "02:10:00"),
    ];
    const theirs = [
      participation(11, 20, "Triathlon B", "2026-03-01", "01:55:00"),
      participation(12, 10, "Triathlon A", "2026-06-01", "01:58:00"),
      participation(13, 40, "Triathlon D (autre)", "2026-01-01", "02:30:00"),
    ];

    const result = commonParticipations(mine, theirs);

    expect(result.map((r) => r.courseId)).toEqual([20, 10]);
    expect(result[0].mineSeconds).toBe(6600);
    expect(result[0].theirsSeconds).toBe(6900);
  });

  it("ne renvoie rien sans épreuve commune", () => {
    const mine = [participation(1, 10, "Triathlon A", "2026-06-01", "02:00:00")];
    const theirs = [participation(11, 99, "Autre épreuve", "2026-06-01", "01:55:00")];

    expect(commonParticipations(mine, theirs)).toEqual([]);
  });

  it("place les épreuves sans date connue en fin de liste", () => {
    const mine = [
      participation(1, 10, "Sans date", null, "02:00:00"),
      participation(2, 20, "Avec date", "2026-01-01", "01:50:00"),
    ];
    const theirs = [
      participation(11, 20, "Avec date", "2026-01-01", "01:55:00"),
      participation(12, 10, "Sans date", null, "01:58:00"),
    ];

    expect(commonParticipations(mine, theirs).map((r) => r.courseId)).toEqual([20, 10]);
  });
});

describe("formatDelta", () => {
  it("annonce un retard quand mon temps est le plus long", () => {
    // 3 min 25 s de plus que le coéquipier.
    expect(formatDelta(12205, 12000)).toBe("3 min 25 s de retard");
  });

  it("annonce une avance quand mon temps est le plus court", () => {
    expect(formatDelta(100, 145)).toBe("45 s d'avance");
  });

  it("annonce un temps identique sans écart", () => {
    expect(formatDelta(3600, 3600)).toBe("Temps identique");
  });

  it("compte les heures dans l'écart, sans les secondes", () => {
    // 1 h 05 min 00 s de retard.
    expect(formatDelta(7500, 3600)).toBe("1 h 05 min de retard");
  });

  it("n'affiche que les secondes sous la minute", () => {
    expect(formatDelta(45, 20)).toBe("25 s de retard");
  });
});

describe("commonParticipations reads times like the finishers list (#1063)", () => {
  it.each([
    ["01:23:45", 5025],
    ["23:45", 1425],
    ["01:23:45.6", null],
    ["01:75:00", null],
    ["1:23:45 ", null],
  ])("parses %j as %j seconds", (temps, attendu) => {
    const mine = [participation(1, 10, "Tri", "2026-06-01", temps)];
    const theirs = [participation(2, 10, "Tri", "2026-06-01", temps)];

    const [ligne] = commonParticipations(mine, theirs);

    expect(ligne.mineSeconds).toBe(attendu);
    expect(ligne.theirsSeconds).toBe(attendu);
  });
});

describe("commonParticipations and zero times (#1480)", () => {
  it("treats 00:00:00 as an absent time, so the chart draws no 0 s bar", () => {
    const mine = [participation(1, 10, "Tri", "2026-06-01", "00:00:00")];
    const theirs = [participation(2, 10, "Tri", "2026-06-01", "01:00:00")];

    const [ligne] = commonParticipations(mine, theirs);

    expect(ligne.mineSeconds).toBeNull();
    expect(ligne.theirsSeconds).toBe(3600);
  });
});

describe("headToHead (#1543)", () => {
  const pair = (courseId: number, mineTime: string | null, theirsTime: string | null) => ({
    mine: participation(courseId * 10, courseId, `Tri ${courseId}`, "2026-06-01", mineTime),
    theirs: participation(courseId * 10 + 1, courseId, `Tri ${courseId}`, "2026-06-01", theirsTime),
  });
  const tally = (pairs: { mine: Participation; theirs: Participation }[]) =>
    headToHead(
      commonParticipations(
        pairs.map((p) => p.mine),
        pairs.map((p) => p.theirs),
      ),
    );

  it("counts wins, losses and ties on shared races", () => {
    const pairs = [
      pair(1, "01:00:00", "01:05:00"),
      pair(2, "01:00:00", "01:05:00"),
      pair(3, "01:10:00", "01:05:00"),
      pair(4, "01:05:00", "01:05:00"),
    ];

    expect(tally(pairs)).toEqual({ wins: 2, losses: 1, ties: 1 });
  });

  it("ignores races where either time is missing or zero", () => {
    const pairs = [pair(1, null, "01:05:00"), pair(2, "01:00:00", "00:00:00"), pair(3, "01:00:00", "01:05:00")];

    expect(tally(pairs)).toEqual({ wins: 1, losses: 0, ties: 0 });
  });

  it("applies the best times exclusions: relay, pending, unreliable course, non finisher", () => {
    const relay = pair(1, "01:00:00", "01:05:00");
    relay.theirs = { ...relay.theirs, is_relay: true };
    const relayCourse = pair(2, "01:00:00", "01:05:00");
    relayCourse.mine = { ...relayCourse.mine, course: { ...relayCourse.mine.course, is_relay: true } };
    const pending = pair(3, "01:00:00", "01:05:00");
    pending.theirs = { ...pending.theirs, is_pending_validation: true };
    const unreliable = pair(4, "01:00:00", "01:05:00");
    unreliable.mine = { ...unreliable.mine, course: { ...unreliable.mine.course, is_reliable: false } };
    const dnf = pair(5, "01:00:00", "01:05:00");
    dnf.theirs = { ...dnf.theirs, status: "DNF" };
    const kept = pair(6, "01:10:00", "01:05:00");

    expect(tally([relay, relayCourse, pending, unreliable, dnf, kept])).toEqual({ wins: 0, losses: 1, ties: 0 });
  });

  it("returns an empty tally without shared races", () => {
    expect(headToHead([])).toEqual({ wins: 0, losses: 0, ties: 0 });
  });
});
