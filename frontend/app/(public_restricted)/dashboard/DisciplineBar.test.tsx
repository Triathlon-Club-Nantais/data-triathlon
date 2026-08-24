import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DisciplineBar } from "./DisciplineBar";

const TROIS = [
  { name: "Triathlon", color: "var(--tcn-orange)", ink: "var(--tcn-ink)", count: 300, pct: 75 },
  { name: "Duathlon", color: "var(--tcn-orange-300)", ink: "var(--tcn-ink)", count: 96, pct: 24 },
  {
    name: "Aquathlon",
    color: "var(--tcn-orange-deeper)",
    ink: "var(--tcn-surface)",
    count: 4,
    pct: 1,
  },
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

  it("ne nomme les segments qu'à partir de sm: — sous ce seuil, la légende s'en charge (#480)", () => {
    // 12 % (LABEL_THRESHOLD) est une part de la largeur réelle, pas une
    // largeur en px : sur iPhone SE, 12 % d'une barre de 287px ne laissent
    // que 22px de texte, soit un fragment tronqué et centré (illisible comme
    // troncature). La légende sous la barre nomme déjà chaque famille avec
    // son pourcentage (spec § 5.2) : sous `sm:`, le nom du segment se masque.
    render(<DisciplineBar disciplines={TROIS} />);
    expect(screen.getByText("Triathlon")).toHaveClass("max-sm:hidden");
    expect(screen.getByText("Duathlon")).toHaveClass("max-sm:hidden");
  });

  it("sépare les segments d'un filet, sans rogner leur largeur", () => {
    const { container } = render(<DisciplineBar disciplines={TROIS} />);
    const segments = [...container.querySelectorAll("[data-segment]")] as HTMLElement[];
    expect(segments.map((s) => s.style.width)).toEqual(["75%", "24%", "1%"]);
    expect(segments[0].style.outline).toContain("var(--tcn-surface)");
  });

  it("écrit le libellé dans l'encre de la famille, pas toujours en blanc (#480)", () => {
    // Triathlon (fond clair) veut de l'encre --tcn-ink ; Duathlon --tcn-ink
    // aussi ; --tcn-surface (blanc) n'y tient pas 4,5:1 (lib/sport-colors.ts).
    render(<DisciplineBar disciplines={TROIS} />);
    expect(screen.getByText("Triathlon")).toHaveStyle({ color: "var(--tcn-ink)" });
    expect(screen.getByText("Duathlon")).toHaveStyle({ color: "var(--tcn-ink)" });
  });

  it("ne rend rien quand il n'y a aucune discipline", () => {
    const { container } = render(<DisciplineBar disciplines={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
