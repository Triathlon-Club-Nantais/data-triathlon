import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AthleteChallenge } from "@/lib/types";
import { AthleteChallenges } from "./AthleteChallenges";

const CHALLENGE: AthleteChallenge = {
  id: 7,
  name: "MEDOC 2026 - START CHALLENGE (XS - M - L)",
  event_date: "2026-05-13",
  rank_overall: 1,
  ranked_count: 52,
  total_time: "06:50:33",
  courses: [{ id: 284, name: "MEDOC 2026 - XS" }],
};

describe("AthleteChallenges", () => {
  it("ne rend rien sans challenge", () => {
    const { container } = render(<AthleteChallenges challenges={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("affiche le rang, l'effectif, le temps cumulé et les liens", () => {
    render(<AthleteChallenges challenges={[CHALLENGE]} />);
    expect(screen.getByRole("heading", { name: "Challenges" })).toBeInTheDocument();
    expect(screen.getByText(/1er \/ 52/)).toBeInTheDocument();
    expect(screen.getByText(/06:50:33/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: CHALLENGE.name })).toHaveAttribute("href", "/challenges/7");
    expect(screen.getByRole("link", { name: "MEDOC 2026 - XS" })).toHaveAttribute("href", "/courses/284");
  });

  it("n'affiche ni rang ni temps quand la ligne n'en a pas", () => {
    render(<AthleteChallenges challenges={[{ ...CHALLENGE, rank_overall: null, total_time: null }]} />);
    expect(screen.queryByText(/\/ 52/)).not.toBeInTheDocument();
  });
});
