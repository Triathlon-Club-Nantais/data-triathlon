import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CourseChallengesNote } from "./CourseChallengesNote";

describe("CourseChallengesNote", () => {
  it("ne rend rien sans challenge", () => {
    const { container } = render(<CourseChallengesNote challenges={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("nomme les challenges et leur effectif", () => {
    render(<CourseChallengesNote challenges={[{ id: 7, name: "START CHALLENGE", ranked_count: 52 }]} />);
    expect(screen.getByText(/Cette épreuve compte pour/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "START CHALLENGE" })).toHaveAttribute("href", "/challenges/7");
    expect(screen.getByText(/52 classés/)).toBeInTheDocument();
  });

  it("accorde « classé » au singulier", () => {
    render(<CourseChallengesNote challenges={[{ id: 7, name: "START CHALLENGE", ranked_count: 1 }]} />);
    expect(screen.getByText(/\(1 classé\)/)).toBeInTheDocument();
  });
});
