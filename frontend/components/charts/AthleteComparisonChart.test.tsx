import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AthleteComparisonChart, AthleteComparisonResult } from "./AthleteComparisonChart";

const { searchAthletes, getAthlete } = vi.hoisted(() => ({
  searchAthletes: vi.fn(),
  getAthlete: vi.fn(),
}));
vi.mock("@/lib/api/client", () => ({ apiClient: { searchAthletes, getAthlete } }));
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

describe("AthleteComparisonResult head-to-head line (#1543)", () => {
  it("sums up wins and losses above the races, without ties when there are none", () => {
    const mine = [
      participation(1, 10, "2026-03-01", "01:00:00"),
      participation(2, 20, "2026-04-01", "01:00:00"),
      participation(3, 30, "2026-05-01", "01:10:00"),
    ];
    const theirs = [
      participation(11, 10, "2026-03-01", "01:05:00"),
      participation(12, 20, "2026-04-01", "01:05:00"),
      participation(13, 30, "2026-05-01", "01:05:00"),
    ];

    render(<AthleteComparisonResult mine={mine} theirs={theirs} theirsName="Camarade" />);

    expect(
      screen.getByText("Face à Camarade, sur 3 épreuves comparables : devant 2 fois, derrière 1 fois."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/hors bilan/)).not.toBeInTheDocument();
  });

  it("mentions ties, drops zero counts and uses the singular for one race", () => {
    const mine = [participation(1, 10, "2026-03-01", "01:05:00")];
    const theirs = [participation(11, 10, "2026-03-01", "01:05:00")];

    render(<AthleteComparisonResult mine={mine} theirs={theirs} theirsName="Camarade" />);

    expect(screen.getByText("Face à Camarade, sur 1 épreuve comparable : à égalité 1 fois.")).toBeInTheDocument();
  });

  it("says how many displayed races are left out of the tally", () => {
    const mine = [
      { ...participation(1, 10, "2026-03-01", "01:00:00"), is_relay: true },
      participation(2, 20, "2026-04-01", "01:00:00"),
    ];
    const theirs = [participation(11, 10, "2026-03-01", "01:05:00"), participation(12, 20, "2026-04-01", "01:05:00")];

    render(<AthleteComparisonResult mine={mine} theirs={theirs} theirsName="Camarade" />);

    expect(screen.getByText(/sur 1 épreuve comparable : devant 1 fois\./)).toBeInTheDocument();
    expect(screen.getByText(/^1 épreuve hors bilan/)).toBeInTheDocument();
  });

  it("marks each row the tally leaves out with its reason (#1563)", () => {
    const mine = [
      { ...participation(1, 10, "2026-03-01", "01:00:00"), is_relay: true },
      { ...participation(2, 20, "2026-04-01", "01:00:00"), status: "DNF" },
      participation(3, 30, "2026-05-01", "01:00:00"),
    ];
    const theirs = [
      participation(11, 10, "2026-03-01", "01:05:00"),
      participation(12, 20, "2026-04-01", "01:05:00"),
      participation(13, 30, "2026-05-01", "01:05:00"),
    ];

    render(<AthleteComparisonResult mine={mine} theirs={theirs} theirsName="Camarade" />);

    expect(screen.getByText(/sur 1 épreuve comparable : devant 1 fois\./)).toBeInTheDocument();
    expect(within(screen.getByRole("group", { name: /Épreuve 10/ })).getByText("Hors bilan : relais")).toBeInTheDocument();
    expect(within(screen.getByRole("group", { name: /Épreuve 20/ })).getByText("Hors bilan : non classé")).toBeInTheDocument();
    expect(within(screen.getByRole("group", { name: /Épreuve 30/ })).queryByText(/hors bilan/i)).not.toBeInTheDocument();
  });

  it("names the teammate when only their result is left out (#1563)", () => {
    const mine = [participation(1, 10, "2026-03-01", "01:00:00")];
    const theirs = [{ ...participation(11, 10, "2026-03-01", "01:05:00"), status: "DSQ" }];

    render(<AthleteComparisonResult mine={mine} theirs={theirs} theirsName="Camarade" />);

    expect(screen.getByText("Hors bilan : non classé (Camarade)")).toBeInTheDocument();
  });

  it("shows only the exclusion note when every shared time is excluded", () => {
    const mine = [{ ...participation(1, 10, "2026-03-01", "01:00:00"), is_relay: true }];
    const theirs = [participation(11, 10, "2026-03-01", "01:05:00")];

    render(<AthleteComparisonResult mine={mine} theirs={theirs} theirsName="Camarade" />);

    expect(screen.getByText("Épreuve 10")).toBeInTheDocument();
    expect(screen.queryByText(/épreuves? comparables?/)).not.toBeInTheDocument();
    expect(screen.getByText(/^1 épreuve hors bilan/)).toBeInTheDocument();
  });

  it("shows no line and keeps the current message without any usable time", () => {
    const mine = [participation(1, 10, "2026-03-01", null)];
    const theirs = [participation(11, 10, "2026-03-01", "01:05:00")];

    render(<AthleteComparisonResult mine={mine} theirs={theirs} theirsName="Camarade" />);

    expect(screen.getByText(/aucun temps\s+exploitable/)).toBeInTheDocument();
    expect(screen.queryByText(/épreuves? comparables?/)).not.toBeInTheDocument();
  });
});

describe("AthleteComparisonChart, teammate load failure (#1028)", () => {
  const camarade = { id: 7, nom: "Martin", prenom: "Lea", club: "TCN" };

  beforeEach(() => {
    searchAthletes.mockReset().mockResolvedValue([camarade]);
    getAthlete.mockReset();
  });

  async function choisirCamarade() {
    render(<AthleteComparisonChart mine={[]} />);
    await userEvent.type(screen.getByLabelText(/chercher un athlète à comparer/i), "Lea");
    await userEvent.click(await screen.findByRole("button", { name: /Lea Martin/ }));
  }

  it("offers retry and change after the load fails", async () => {
    getAthlete.mockRejectedValueOnce(new Error("réveil")).mockResolvedValueOnce({ participations: [] });
    await choisirCamarade();

    expect(await screen.findByText(/impossible de charger.*pour l.instant/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /réessayer/i }));

    expect(await screen.findByText(/comparaison avec lea martin/i)).toBeInTheDocument();
    expect(getAthlete).toHaveBeenCalledTimes(2);
  });

  it("brings the search back when changing after a failure", async () => {
    getAthlete.mockRejectedValue(new Error("réveil"));
    await choisirCamarade();

    await userEvent.click(await screen.findByRole("button", { name: /changer/i }));

    // Le bouton disparaît sous le doigt : le focus revient au champ, pas au <body>.
    expect(screen.getByLabelText(/chercher un athlète à comparer/i)).toHaveFocus();
  });

  it("announces the failure and keeps the focus in place on retry", async () => {
    getAthlete.mockRejectedValueOnce(new Error("réveil")).mockReturnValueOnce(new Promise(() => {}));
    await choisirCamarade();

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/impossible de charger les résultats de lea martin/i),
    );
    const reessayer = screen.getByRole("button", { name: /réessayer/i });
    expect(reessayer).toHaveClass("tcn-cible-tactile");
    await userEvent.click(reessayer);

    expect(document.activeElement).not.toBe(document.body);
  });

  it("lets the user change while loading and ignores the late answer", async () => {
    let repondre: (v: { participations: Participation[] }) => void = () => {};
    getAthlete.mockReturnValue(new Promise((resolve) => (repondre = resolve)));
    await choisirCamarade();

    await userEvent.click(screen.getByRole("button", { name: /changer/i }));
    repondre({ participations: [] });

    expect(await screen.findByLabelText(/chercher un athlète à comparer/i)).toBeInTheDocument();
    expect(screen.queryByText(/comparaison avec/i)).not.toBeInTheDocument();
  });
});
