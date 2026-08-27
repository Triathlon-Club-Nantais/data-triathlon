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
    expect(screen.queryByText("Épreuve 10")).not.toBeInTheDocument();
  });

  it("affiche le nom de l'épreuve, les deux temps et l'écart chiffré (#689)", () => {
    const mine = [participation(1, 10, "2026-06-01", "02:00:00")];
    const theirs = [participation(11, 10, "2026-06-01", "01:55:00")];

    render(<AthleteComparisonResult mine={mine} theirs={theirs} theirsName="Camarade" />);

    expect(screen.queryByText(/aucune épreuve commune/i)).not.toBeInTheDocument();
    // Le nom de l'épreuve, jusque-là réservé à l'aria-label, est visible.
    expect(screen.getByText("Épreuve 10")).toBeInTheDocument();
    // Les deux temps, jusque-là réservés à l'aria-label, sont visibles.
    // « 02:00:00 » apparaît deux fois : sur la barre « Vous » et comme repère
    // max de l'axe, puisque c'est ici le plus long des deux temps.
    expect(screen.getAllByText("02:00:00").length).toBe(2);
    expect(screen.getByText("01:55:00")).toBeInTheDocument();
    // L'écart chiffré entre les deux temps — l'info recherchée par #689.
    expect(screen.getByText(/5 min 00 s de retard/)).toBeInTheDocument();
  });
});
