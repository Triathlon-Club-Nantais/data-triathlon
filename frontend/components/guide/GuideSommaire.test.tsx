import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { GuideSommaire } from "./GuideSommaire";
import type { GuideSection } from "./types";

const sections: GuideSection[] = [
  { id: "dashboard", titre: "Tableau de bord", etapes: ["a"], casUsage: "x", captures: [{ src: "/a.png", alt: "a" }] },
  { id: "club", titre: "Espace club", etapes: ["a"], casUsage: "x", captures: [{ src: "/b.png", alt: "b" }] },
];

describe("GuideSommaire", () => {
  it("rend un lien d'ancre par section, dans l'ordre fourni", () => {
    render(<GuideSommaire sections={sections} />);
    const liens = screen.getAllByRole("link");
    expect(liens).toHaveLength(2);
    expect(liens[0]).toHaveAttribute("href", "#dashboard");
    expect(liens[0]).toHaveTextContent("Tableau de bord");
    expect(liens[1]).toHaveAttribute("href", "#club");
    expect(liens[1]).toHaveTextContent("Espace club");
  });
});
