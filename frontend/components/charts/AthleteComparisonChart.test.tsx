import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AthleteComparisonResult } from "./AthleteComparisonChart";
import type { Participation, CourseBrief, AthleteBrief } from "@/lib/types";

const athlete = (id: number): AthleteBrief => ({ id, nom: "Nom", prenom: "Prenom", gender: "F", club: "TCN" });

const course = (id: number, eventDate: string | null): CourseBrief => ({
  id,
  name: `Épreuve ${id}`,
  event_date: eventDate,
  event_type: "triathlon",
  provider: "manuel",
  source_url: "",
  is_relay: false,
});

const participation = (id: number, courseId: number, eventDate: string | null, totalTime: string | null): Participation => ({
  id,
  athlete: athlete(1),
  course: course(courseId, eventDate),
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

describe("AthleteComparisonResult", () => {
  it("affiche un message explicite sans épreuve commune", () => {
    const mine = [participation(1, 10, "2026-06-01", "02:00:00")];
    const theirs = [participation(11, 99, "2026-06-01", "01:55:00")];

    render(<AthleteComparisonResult mine={mine} theirs={theirs} theirsName="Camarade" />);

    expect(screen.getByText(/aucune épreuve commune/i)).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("affiche un graphique de comparaison sur épreuve commune", () => {
    const mine = [participation(1, 10, "2026-06-01", "02:00:00")];
    const theirs = [participation(11, 10, "2026-06-01", "01:55:00")];

    render(<AthleteComparisonResult mine={mine} theirs={theirs} theirsName="Camarade" />);

    expect(screen.queryByText(/aucune épreuve commune/i)).not.toBeInTheDocument();
    expect(screen.getByRole("img")).toBeInTheDocument();
  });
});
