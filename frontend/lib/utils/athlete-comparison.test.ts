import { describe, it, expect } from "vitest";
import { commonParticipations, formatDelta } from "./athlete-comparison";
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
