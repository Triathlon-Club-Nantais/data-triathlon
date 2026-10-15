import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CourseBrief, Participation } from "@/lib/types";
import { BestTimesCard } from "./BestTimesCard";

function part(id: number, totalTime: string, course: Partial<CourseBrief> = {}): Participation {
  return {
    id,
    athlete: { id: 7, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" },
    course: {
      id: 100 + id,
      name: `Course ${id}`,
      event_date: "2026-05-16",
      event_type: "triathlon-m",
      provider: "manuel",
      source_url: "",
      is_relay: false,
      ...course,
    },
    total_time: totalTime,
    status: "finisher",
    is_relay: false,
  } as Participation;
}

describe("BestTimesCard", () => {
  it("renders nothing without a comparable time", () => {
    const { container } = render(<BestTimesCard participations={[part(1, "", {})]} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders one line linking to the participation", () => {
    render(<BestTimesCard participations={[part(1, "02:05:30")]} />);

    expect(screen.getByRole("heading", { name: "Meilleurs temps" })).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /meilleur temps sur M/ });
    expect(link).toHaveAttribute("href", "/courses/101/participations/1");
    expect(link).toHaveTextContent("Triathlon");
    expect(link).toHaveTextContent("02:05:30");
    expect(link).toHaveTextContent("Course 1");
    expect(screen.queryByText(/record/i)).not.toBeInTheDocument();
  });

  it("renders one line per discipline and format", () => {
    render(
      <BestTimesCard
        participations={[
          part(1, "02:05:30"),
          part(2, "01:58:00", { event_type: "duathlon-m" }),
          part(3, "01:05:00", { event_type: "triathlon-s" }),
          part(4, "02:01:00"),
        ]}
      />,
    );

    const links = screen.getAllByRole("link");
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "/courses/102/participations/2",
      "/courses/103/participations/3",
      "/courses/104/participations/4",
    ]);
  });
});
