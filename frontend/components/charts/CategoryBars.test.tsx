import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CategoryBars } from "./CategoryBars";

describe("CategoryBars", () => {
  it("affiche une barre par catégorie", () => {
    render(
      <CategoryBars
        categories={[
          { name: "S1", count: 284 },
          { name: "S2", count: 216 },
        ]}
        total={1000}
      />,
    );
    expect(screen.getAllByText(/^S[12]$/).length).toBe(2);
  });

  it("rapporte chaque barre au total fourni, pas à la somme des catégories affichées", () => {
    // 284/1000 = 28,4 % ; les rapporter aux 500 affichés donnerait 56,8 %.
    render(<CategoryBars categories={[{ name: "S1", count: 284 }]} total={1000} />);
    expect(screen.getByText("28,4%")).toBeInTheDocument();
  });

  it("affiche un état vide quand aucune catégorie n'est renseignée", () => {
    render(<CategoryBars categories={[]} total={0} />);
    expect(screen.getByText("Catégories non renseignées")).toBeInTheDocument();
  });

  it("n'échoue pas quand le total est nul", () => {
    const { container } = render(
      <CategoryBars categories={[{ name: "S1", count: 0 }]} total={0} />,
    );
    expect(container.textContent).not.toContain("NaN");
    expect(screen.getByText("0,0%")).toBeInTheDocument();
  });

  it("donne une couleur distincte à chaque catégorie", () => {
    const { container } = render(
      <CategoryBars
        categories={[
          { name: "S1", count: 1 },
          { name: "S2", count: 1 },
        ]}
        total={2}
      />,
    );
    const fills = [...container.querySelectorAll("[style*='border-radius: 999px'] > div")].map(
      (bar) => (bar as HTMLElement).style.background,
    );
    expect(fills[0]).not.toBe(fills[1]);
  });
});
