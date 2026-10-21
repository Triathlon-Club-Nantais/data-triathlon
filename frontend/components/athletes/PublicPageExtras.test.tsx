import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Participation, SeasonGoal } from "@/lib/types";
import { PublicGoal, PublicLinks, PinnedResult } from "./PublicPageExtras";

describe("PublicLinks", () => {
  it("renders each link as a new-tab nofollow anchor with the server label", () => {
    render(<PublicLinks links={[{ url: "https://www.strava.com/athletes/1", label: "Strava" }]} />);
    const a = screen.getByRole("link", { name: "Strava" });
    expect(a).toHaveAttribute("href", "https://www.strava.com/athletes/1");
    expect(a).toHaveAttribute("target", "_blank");
    expect(a).toHaveAttribute("rel", "noopener nofollow ugc");
  });
  it("renders nothing without links", () => {
    const { container } = render(<PublicLinks links={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("PublicGoal", () => {
  it("shows the goal label and progress", () => {
    const goal = { id: 1, season: 2026, kind: "count", event_type: null, target: 3, best_time: null, count: 1,
      reached: false, course_id: null, race_name: null, race_date: null, major: false, public: true,
      outcome: "upcoming" } as SeasonGoal;
    render(<PublicGoal goal={goal} />);
    expect(screen.getByText("Objectif de la saison")).toBeInTheDocument();
    expect(screen.getByText("3 épreuves")).toBeInTheDocument();
    expect(screen.getByText("1 sur 3")).toBeInTheDocument();
  });
});

describe("PinnedResult", () => {
  it("links to the participation detail page", () => {
    const p = { id: 9, course: { id: 4, name: "Triathlon de Nantes", event_date: "2026-05-16", event_type: "triathlon-m" },
      total_time: "01:59:00", rank_overall: 12 } as Participation;
    render(<PinnedResult participation={p} />);
    expect(screen.getByText("Résultat épinglé")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Triathlon de Nantes/ })).toHaveAttribute("href", "/courses/4/participations/9");
  });
});
