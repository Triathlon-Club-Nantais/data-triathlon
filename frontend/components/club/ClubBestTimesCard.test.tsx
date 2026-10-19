import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { ClubBestTime } from "@/lib/types";
import { ClubBestTimesCard } from "./ClubBestTimesCard";

function line(id: number, over: Partial<ClubBestTime> = {}): ClubBestTime {
  return {
    participation_id: id,
    course_id: 100 + id,
    athlete_id: 7,
    athlete_name: "Alice DUPONT",
    event_name: `Course ${id}`,
    event_type: "triathlon-m",
    event_date: "2026-05-16",
    gender: "F",
    total_time: "02:05:30",
    ...over,
  };
}

describe("ClubBestTimesCard", () => {
  it("renders nothing when the club has no comparable time", () => {
    const { container } = render(<ClubBestTimesCard seasonLines={[]} allLines={[]} seasonLabel="Saison 2026 — 2027" />);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders one line per format and gender, linking to the participation", () => {
    render(
      <ClubBestTimesCard
        seasonLines={[line(1), line(2, { gender: "M", athlete_name: "Jean MARTIN", total_time: "01:58:00" })]}
        allLines={[line(1)]}
        seasonLabel="Saison 2026 — 2027"
      />,
    );

    expect(screen.getByRole("heading", { name: "Meilleurs temps du club" })).toBeInTheDocument();
    const links = screen.getAllByRole("link", { name: /meilleur temps sur M/ });
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "/courses/101/participations/1",
      "/courses/102/participations/2",
    ]);
    expect(links[0]).toHaveTextContent("Triathlon");
    expect(links[0]).toHaveTextContent("Femmes");
    expect(links[0]).toHaveTextContent("Alice DUPONT");
    expect(links[0]).toHaveTextContent("Course 1");
    expect(links[0]).toHaveTextContent("02:05:30");
    expect(links[1]).toHaveTextContent("Hommes");
    expect(screen.queryByText(/record/i)).not.toBeInTheDocument();
  });

  it("opens on all seasons when the current season has no time yet, and says so in its tab", async () => {
    render(<ClubBestTimesCard seasonLines={[]} allLines={[line(1)]} seasonLabel="Saison 2026 — 2027" />);

    expect(screen.getByRole("tab", { name: "Toutes les saisons" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("link", { name: /meilleur temps sur M/ })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Saison 2026 — 2027" }));

    expect(screen.getByText(/Aucun temps comparable sur cette saison/)).toBeInTheDocument();
  });
});
