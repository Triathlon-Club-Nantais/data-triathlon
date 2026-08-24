import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DisciplineBar } from "./DisciplineBar";

const TROIS = [
  { name: "Triathlon", color: "var(--tcn-orange)", count: 300, pct: 75 },
  { name: "Duathlon", color: "var(--tcn-orange-300)", count: 96, pct: 24 },
  { name: "Aquathlon", color: "var(--tcn-orange-deeper)", count: 4, pct: 1 },
];

describe("DisciplineBar", () => {
  it("récapitule la répartition pour un lecteur d'écran", () => {
    render(<DisciplineBar disciplines={TROIS} />);
    const barre = screen.getByRole("img");
    expect(barre).toHaveAccessibleName(
      "Répartition des dossards par type d'épreuve : Triathlon 75,0 %, Duathlon 24,0 %, Aquathlon 1,0 %.",
    );
  });

  it("écrit le nom de la famille dans les segments assez larges", () => {
    render(<DisciplineBar disciplines={TROIS} />);
    // 75 % et 24 % portent leur nom ; 1 % ne peut rien porter et reste à la légende.
    expect(screen.getByText("Triathlon")).toBeInTheDocument();
    expect(screen.getByText("Duathlon")).toBeInTheDocument();
    expect(screen.queryByText("Aquathlon")).not.toBeInTheDocument();
  });

  it("sépare les segments d'un filet, sans rogner leur largeur", () => {
    const { container } = render(<DisciplineBar disciplines={TROIS} />);
    const segments = [...container.querySelectorAll("[data-segment]")] as HTMLElement[];
    expect(segments.map((s) => s.style.width)).toEqual(["75%", "24%", "1%"]);
    expect(segments[0].style.outline).toContain("var(--tcn-surface)");
  });

  it("ne rend rien quand il n'y a aucune discipline", () => {
    const { container } = render(<DisciplineBar disciplines={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
