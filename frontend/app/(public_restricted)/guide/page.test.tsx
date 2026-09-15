import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import GuidePage from "./page";

describe("GuidePage", () => {
  it("rend le sommaire et les 6 sections membres", () => {
    render(<GuidePage />);
    expect(screen.getByRole("heading", { name: /guide/i, level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Sommaire du guide" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Tableau de bord" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Espace club" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Résultats" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Comparaison" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ajouter une épreuve" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Bénévolat" })).toBeInTheDocument();
  });

  it("expose la section « club » sous une ancre atteignable directement", () => {
    const { container } = render(<GuidePage />);
    expect(container.querySelector("#club")).not.toBeNull();
  });
});
